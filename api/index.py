# Vercel serverless function entry point
import sys
import os

# Add parent directory to path so we can import app
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    # Import the FastAPI app
    from app import app
    
    # Vercel expects a handler that can be called
    # For FastAPI on Vercel, we need to use mangum to convert ASGI to Lambda/HTTP
    try:
        from mangum import Mangum
        handler = Mangum(app, lifespan="off")
    except ImportError:
        # Fallback if mangum is not available
        # Vercel's Python runtime might handle FastAPI directly
        handler = app
        
except Exception as e:
    # If import fails, create a simple error handler
    import traceback
    error_msg = str(e)
    traceback_str = traceback.format_exc()
    
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "error": "Failed to initialize application",
                "message": error_msg,
                "traceback": traceback_str
            }
        }
