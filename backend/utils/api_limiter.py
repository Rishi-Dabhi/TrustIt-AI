"""
Utility for handling API rate limiting, quotas, and exponential backoff.
This prevents hitting rate limits and quota limits by properly spacing API calls
and implementing backoff when errors occur.
"""
import time
import asyncio
import random
from typing import Callable, Any, Dict, Optional
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_limiter")

class APILimiter:
    """
    Controls API request pacing to avoid hitting rate limits and quota limits.
    Uses a token bucket algorithm and exponential backoff.
    """
    def __init__(
        self, 
        name: str = "gemini",
        base_delay: float = 1.0,  # Base delay in seconds between API calls
        max_retries: int = 3,  # Maximum number of retries for a failed call
        max_backoff: float = 60.0,  # Maximum backoff time in seconds
        daily_quota: Optional[int] = None  # Daily quota limit if known
    ):
        self.name = name
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self.daily_quota = daily_quota
        
        # Time of last API call
        self.last_call_time = 0
        
        # Counters for monitoring
        self.daily_call_count = 0
        self.error_count = 0
        self.success_count = 0
        
        # Cooldown state
        self.is_cooling_down = False
        self.cooldown_until = 0
        
        logger.info(f"Initialized API limiter for {name} with {base_delay}s delay")
    
    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff time with jitter"""
        base = min(self.max_backoff, self.base_delay * (2 ** retry_count))
        jitter = random.uniform(0, 0.1 * base)  # 10% jitter
        return base + jitter
    
    def should_wait(self) -> float:
        """
        Determine if we should wait before making an API call, and for how long.
        Returns the number of seconds to wait.
        """
        now = time.time()
        
        # Check if we're in a cooldown period
        if self.is_cooling_down and now < self.cooldown_until:
            wait_time = self.cooldown_until - now
            logger.warning(f"{self.name} API in cooldown. Waiting {wait_time:.1f}s")
            return wait_time
        elif self.is_cooling_down:
            # Reset cooldown if it's expired
            logger.info(f"{self.name} API cooldown period ended")
            self.is_cooling_down = False
        
        # Check if we need to wait to respect the base delay
        time_since_last_call = now - self.last_call_time
        if time_since_last_call < self.base_delay:
            wait_time = self.base_delay - time_since_last_call
            return wait_time
        
        # No need to wait
        return 0
    
    def set_cooldown(self, seconds: float) -> None:
        """Set a cooldown period after hitting a rate limit"""
        self.is_cooling_down = True
        self.cooldown_until = time.time() + seconds
        logger.warning(f"Setting {self.name} API cooldown for {seconds:.1f}s")
    
    def check_quota(self) -> bool:
        """Check if we've exceeded our daily quota"""
        if self.daily_quota and self.daily_call_count >= self.daily_quota:
            logger.error(f"{self.name} API daily quota of {self.daily_quota} exceeded!")
            return False
        return True
    
    def record_call(self, success: bool = True) -> None:
        """Record an API call and update the last call time"""
        self.last_call_time = time.time()
        self.daily_call_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def _extract_retry_after(self, error_str: str) -> Optional[float]:
        """Extract retry delay from error message, particularly for Google API errors"""
        # Try to extract retry_delay from Google API error format
        retry_delay_match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_str)
        if retry_delay_match:
            return float(retry_delay_match.group(1))
        
        # Try other common formats
        retry_after_match = re.search(r'retry-after:\s*(\d+)', error_str, re.IGNORECASE)
        if retry_after_match:
            return float(retry_after_match.group(1))
            
        # Try extracting just seconds value
        seconds_match = re.search(r'seconds:\s*(\d+)', error_str)
        if seconds_match:
            return float(seconds_match.group(1))
            
        return None
    
    async def execute_with_limit_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function with rate limiting and exponential backoff.
        If the function fails with a rate limit error, it will retry.
        """
        if not self.check_quota():
            raise Exception(f"{self.name} API daily quota exceeded")
        
        # Print detailed diagnostic information
        logger.info(f"===== {self.name} API ASYNC CALL START =====")
        logger.info(f"Function: {func.__name__ if hasattr(func, '__name__') else str(func)}")
        logger.info(f"Rate limit settings: delay={self.base_delay}s, retries={self.max_retries}")
        
        retry_count = 0
        while retry_count <= self.max_retries:
            # Check if we need to wait due to rate limiting or backoff
            wait_time = self.should_wait()
            if wait_time > 0:
                logger.info(f"🕒 {self.name} API: Waiting {wait_time:.1f}s before async call (time since last call: {time.time() - self.last_call_time:.1f}s)")
                await asyncio.sleep(wait_time)
            
            try:
                start_time = time.time()
                logger.info(f"📞 Calling {self.name} API (async)...")
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"✅ {self.name} API async call success in {elapsed:.2f}s")
                self.record_call(success=True)
                logger.info(f"===== {self.name} API ASYNC CALL END =====")
                return result
            
            except Exception as e:
                error_str = str(e).lower()
                elapsed = time.time() - start_time
                self.record_call(success=False)
                logger.error(f"❌ {self.name} API async call failed in {elapsed:.2f}s: {str(e)}")
                
                # Check if this is a rate limit or quota error
                if any(term in error_str for term in ["429", "exceeded", "quota", "rate limit", "capacity"]):
                    retry_count += 1
                    logger.warning(f"⚠️ {self.name} API rate limited (attempt {retry_count}/{self.max_retries}): {str(e)}")
                    
                    # Extract retry delay
                    retry_after = self._extract_retry_after(str(e))
                    
                    # If we couldn't extract, use exponential backoff
                    if retry_after is None:
                        retry_after = self._calculate_backoff(retry_count)
                        logger.info(f"Using calculated backoff: {retry_after:.1f}s")
                    else:
                        # Add a small buffer to the retry time to be safe
                        retry_after = retry_after + 2.0
                        logger.info(f"Using extracted retry delay: {retry_after:.1f}s (includes +2s buffer)")
                    
                    # Set cooldown
                    self.set_cooldown(retry_after)
                    
                    if retry_count <= self.max_retries:
                        logger.warning(f"🔄 {self.name} API rate limited. Retrying in {retry_after:.1f}s (Attempt {retry_count}/{self.max_retries})")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error(f"❌❌ {self.name} API rate limited. Max retries ({self.max_retries}) exceeded.")
                
                # Re-raise the exception if not retrying
                logger.error(f"===== {self.name} API ASYNC CALL END (WITH ERROR) =====")
                raise
    
    def execute_with_limit(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a synchronous function with rate limiting and exponential backoff.
        If the function fails with a rate limit error, it will retry.
        """
        if not self.check_quota():
            raise Exception(f"{self.name} API daily quota exceeded")
        
        # Print detailed diagnostic information
        logger.info(f"===== {self.name} API CALL START =====")
        logger.info(f"Function: {func.__name__ if hasattr(func, '__name__') else str(func)}")
        logger.info(f"Rate limit settings: delay={self.base_delay}s, retries={self.max_retries}")
        
        retry_count = 0
        while retry_count <= self.max_retries:
            # Check if we need to wait due to rate limiting or backoff
            wait_time = self.should_wait()
            if wait_time > 0:
                logger.info(f"🕒 {self.name} API: Waiting {wait_time:.1f}s before call (time since last call: {time.time() - self.last_call_time:.1f}s)")
                time.sleep(wait_time)
            
            try:
                start_time = time.time()
                logger.info(f"📞 Calling {self.name} API...")
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"✅ {self.name} API call success in {elapsed:.2f}s")
                self.record_call(success=True)
                logger.info(f"===== {self.name} API CALL END =====")
                return result
            
            except Exception as e:
                error_str = str(e).lower()
                elapsed = time.time() - start_time
                self.record_call(success=False)
                logger.error(f"❌ {self.name} API call failed in {elapsed:.2f}s: {str(e)}")
                
                # Check if this is a rate limit or quota error
                if any(term in error_str for term in ["429", "exceeded", "quota", "rate limit", "capacity"]):
                    retry_count += 1
                    logger.warning(f"⚠️ {self.name} API rate limited (attempt {retry_count}/{self.max_retries}): {str(e)}")
                    
                    # Extract retry delay
                    retry_after = self._extract_retry_after(str(e))
                    
                    # If we couldn't extract, use exponential backoff
                    if retry_after is None:
                        retry_after = self._calculate_backoff(retry_count)
                        logger.info(f"Using calculated backoff: {retry_after:.1f}s")
                    else:
                        # Add a small buffer to the retry time to be safe
                        retry_after = retry_after + 2.0
                        logger.info(f"Using extracted retry delay: {retry_after:.1f}s (includes +2s buffer)")
                    
                    # Set cooldown
                    self.set_cooldown(retry_after)
                    
                    if retry_count <= self.max_retries:
                        logger.warning(f"🔄 {self.name} API rate limited. Retrying in {retry_after:.1f}s (Attempt {retry_count}/{self.max_retries})")
                        time.sleep(retry_after)
                        continue
                    else:
                        logger.error(f"❌❌ {self.name} API rate limited. Max retries ({self.max_retries}) exceeded.")
                
                # Re-raise the exception if not retrying
                logger.error(f"===== {self.name} API CALL END (WITH ERROR) =====")
                raise

# Create a global instance to share across the application
gemini_limiter = APILimiter(name="gemini", base_delay=10.0, max_retries=5, max_backoff=120.0) 