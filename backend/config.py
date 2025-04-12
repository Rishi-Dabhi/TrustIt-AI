import os
from dotenv import load_dotenv

def load_config():
    """Load environment variables and API keys"""
    load_dotenv()
    print("Loading environment variables...")
    
    config = {
        "google_api_key": "AIzaSyCgsC41ic7GwUCs58C-FrkdIf6DA95grwk",
        "portia_api_key": "prt-6TvKpajd.CN1XfJtmpxGTJhPftTj97kt86z7pAtkM",
        "tavily_api_key": "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"
    }
    
    # Validate required keys
    missing_keys = [k for k, v in config.items() if not v]
    if missing_keys:
        raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")
    
    print("All required API keys found.")
    return config 