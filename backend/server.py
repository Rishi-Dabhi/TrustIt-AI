from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import traceback
import logging

# Configure logging to see rate limiting in action
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server")

# Use relative imports
from .main import process_content
from .config import load_config
from .services.search_service import SearchService
from .utils import tavily_limiter, gemini_limiter

# Log rate limiter configuration on startup
logger.info(f"==== TrustIt-AI Server Starting ====")
logger.info(f"Tavily API Rate Limiter: delay={tavily_limiter.base_delay}s, retries={tavily_limiter.max_retries}")
logger.info(f"Gemini API Rate Limiter: delay={gemini_limiter.base_delay}s, retries={gemini_limiter.max_retries}")

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ContentRequest(BaseModel):
    content: str

@app.post("/api/process")
async def process_text(request: ContentRequest) -> Dict[str, Any]:
    try:
        # Load configuration
        config = load_config()
        
        # Process the content
        result = await process_content(request.content, config)
        print(f"--- [SERVER] Returning result: {result}")
        return result
    except Exception as e:
        print("Error processing content:", str(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 