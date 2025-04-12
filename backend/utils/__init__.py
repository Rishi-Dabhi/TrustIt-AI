"""
Utils package for TrustIt-AI backend.
"""
from .environment import setup_environment
from .personality_loader import PersonalityLoader
from .api_limiter import APILimiter, gemini_limiter

# Create a default instance for Tavily with higher delay to ensure rate limits are respected
tavily_limiter = APILimiter(name="tavily", base_delay=2.0, max_retries=5, max_backoff=120.0)  # 2s delay between requests

__all__ = ['setup_environment', 'PersonalityLoader', 'APILimiter', 'gemini_limiter', 'tavily_limiter'] 