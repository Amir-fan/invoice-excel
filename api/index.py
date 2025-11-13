# Vercel serverless function entry point
import sys
import os
import traceback

# Add parent directory to path so we can import app
try:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Enable debug mode if needed
    os.environ.setdefault("DEBUG", "false")
    
    # Import the FastAPI app
    from app import app
    
    # Vercel expects a handler that can be called
    # For FastAPI on Vercel, we need to use mangum to convert ASGI to Lambda/HTTP
    try:
        from mangum import Mangum
        # Create Mangum adapter with lifespan disabled for Vercel
        handler = Mangum(app, lifespan="off")
    except ImportError as e:
        print(f"WARNING: Mangum not available: {e}")
        # If mangum is not available, try using the app directly
        # Some Vercel configurations support FastAPI directly
        handler = app
        
except Exception as e:
    # If import fails, create a simple error handler that will show the error
    error_msg = str(e)
    traceback_str = traceback.format_exc()
    
    # Log the error for debugging
    print(f"ERROR: Failed to import app: {error_msg}")
    print(f"Traceback:\n{traceback_str}")
    
    # Create a simple FastAPI app to show the error
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def error_handler(path: str = None):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to initialize application",
                    "message": error_msg,
                    "traceback": traceback_str,
                    "path": path
                }
            )
        
        # Try to wrap with Mangum if available
        try:
            from mangum import Mangum
            handler = Mangum(error_app, lifespan="off")
        except ImportError:
            handler = error_app
    except Exception as e2:
        # If even FastAPI import fails, create a minimal handler
        def handler(event, context):
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "error": "Critical failure",
                    "message": f"Import error: {error_msg}, FastAPI error: {str(e2)}",
                    "traceback": traceback_str
                }
            }
