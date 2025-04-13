import os
import sys

# Add the parent directory to Python path so that backend becomes a proper package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI app from the server module
from backend.server import app

if __name__ == "__main__":
    # Start the server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 