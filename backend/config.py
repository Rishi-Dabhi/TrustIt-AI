import os
from dotenv import load_dotenv

def load_config():
    """Load environment variables and API keys"""
    load_dotenv()
    print("Loading environment variables...")
    
    config = {
        "google_api_key": "",
        "portia_api_key": "",
        "tavily_api_key": ""
    }
    
    # Validate required keys
    missing_keys = [k for k, v in config.items() if not v]
    if missing_keys:
        raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")
    
    print("All required API keys found.")
    return config 