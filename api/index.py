# Vercel serverless function entry point
# Vercel natively supports FastAPI/ASGI - no Mangum needed!
import sys
import os
import traceback

def log(msg):
    """Log message for debugging."""
    try:
        print(msg, file=sys.stderr, flush=True)
        print(msg, flush=True)
    except:
        pass

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

log("=" * 50)
log("Initializing handler...")
log(f"Python: {sys.version}")
log(f"Parent dir: {parent_dir}")

# Disable .env loading - Vercel uses environment variables directly
os.environ.setdefault("DEBUG", "false")

# Try to import the app directly - Vercel handles ASGI natively
try:
    log("Importing app...")
    from app import app
    log("✓ App imported successfully")
    
    # Vercel natively supports FastAPI - just export the app
    # No need for Mangum wrapper!
    handler = app
    log("✓ Handler set to FastAPI app")
    
except Exception as e:
    error_msg = str(e)
    error_tb = traceback.format_exc()
    
    log("=" * 50)
    log(f"ERROR: {error_msg}")
    log(error_tb)
    log("=" * 50)
    
    # Create error handler
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
                    "traceback": error_tb.split("\n"),
                    "path": path,
                    "parent_dir": parent_dir
                }
            )
        
        handler = error_app
        log("✓ Error handler created")
        
    except Exception as e2:
        log(f"CRITICAL: Cannot create error handler: {e2}")
        handler = None

if handler is None:
    log("CRITICAL: Handler is None!")

log("=" * 50)
log("Handler initialization complete")
log("=" * 50)
