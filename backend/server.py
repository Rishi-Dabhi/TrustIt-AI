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
from .main import process_content, process_content_with_portia  # Import both processing methods
from .config import load_config
from .services.search_service import SearchService
from .utils import tavily_limiter, gemini_limiter

# Log rate limiter configuration on startup
logger.info(f"==== TrustIt-AI Server Starting ====")
logger.info(f"Tavily API Rate Limiter: delay={tavily_limiter.base_delay}s, retries={tavily_limiter.max_retries}")
logger.info(f"Gemini API Rate Limiter: delay={gemini_limiter.base_delay}s, retries={gemini_limiter.max_retries}")

app = FastAPI()

# Configure CORS - Update to allow Vercel domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ContentRequest(BaseModel):
    content: str
    use_portia: bool = True  # Default to using Portia pipeline
    sessionId: Optional[str] = None  # Optional session ID for real-time updates via Pusher

@app.post("/api/process")
async def process_text(request: ContentRequest) -> Dict[str, Any]:
    try:
        # Load configuration
        config = load_config()
        
        # Choose which processing method to use based on request
        if request.use_portia:
            logger.info(f"Processing content with Portia: '{request.content[:50]}...', Session ID: {request.sessionId or 'None'}")
            result = await process_content_with_portia(request.content, config, request.sessionId)
        else:
            logger.info(f"Processing content with original pipeline: '{request.content[:50]}...'")
            result = await process_content(request.content, config)
            
        logger.info(f"Processing completed with method: {'Portia' if request.use_portia else 'Original'}")
        return result
    except Exception as e:
        logger.error(f"Error processing content: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# Add an info endpoint to get information about the API
@app.get("/api/info")
async def get_info():
    return {
        "name": "TrustIt-AI API",
        "version": "1.0.0",
        "features": [
            "Fact checking",
            "Portia integration",
            "Multi-agent workflow"
        ],
        "endpoints": [
            {
                "path": "/api/process",
                "method": "POST",
                "description": "Process content for fact-checking",
                "parameters": {
                    "content": "Text content to fact-check",
                    "use_portia": "Boolean flag to use Portia (default: true)"
                }
            },
            {
                "path": "/api/info",
                "method": "GET",
                "description": "Get information about the API"
            }
        ]
    }

# Add a root endpoint for Vercel health checks
@app.get("/")
async def root():
    return {"status": "ok", "message": "TrustIt-AI API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 