# Vercel serverless function entry point
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI app
from app import app

# Vercel expects a handler that can be called
# For FastAPI on Vercel, we need to use mangum to convert ASGI to Lambda/HTTP
try:
    from mangum import Mangum
    handler = Mangum(app)
except ImportError:
    # Fallback if mangum is not available - Vercel might handle FastAPI directly
    handler = app
