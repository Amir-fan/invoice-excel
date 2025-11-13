# Vercel serverless function entry point
# Minimal handler to catch all errors and show them
import sys
import os
import traceback

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Disable .env loading - Vercel uses environment variables directly
os.environ.setdefault("DEBUG", "false")

handler = None

try:
    # Import FastAPI first
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    # Import the app
    from app import app
    
    # Import Mangum for ASGI adapter
    from mangum import Mangum
    
    # Create handler
    handler = Mangum(app, lifespan="off")
    
except Exception as e:
    # If anything fails, create an error handler that shows the error
    error_msg = str(e)
    error_traceback = traceback.format_exc()
    
    # Log to stderr (Vercel captures this)
    print(f"ERROR: {error_msg}", file=sys.stderr, flush=True)
    print(error_traceback, file=sys.stderr, flush=True)
    
    # Create error app
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def show_error(path: str = None):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "message": error_msg,
                    "traceback": error_traceback.split("\n"),
                    "python_path": sys.path[:5],
                    "parent_dir": parent_dir,
                    "current_dir": os.getcwd()
                }
            )
        
        from mangum import Mangum
        handler = Mangum(error_app, lifespan="off")
    except Exception as e2:
        # Ultimate fallback
        print(f"CRITICAL: Cannot create error handler: {e2}", file=sys.stderr, flush=True)
        def handler(event, context):
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": '{"error": "Critical initialization failure"}'
            }
