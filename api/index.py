# Vercel serverless function entry point
# Following Vercel's FastAPI documentation: https://vercel.com/docs/frameworks/backend/fastapi
import sys
import os
import traceback

# Set up logging to stderr (Vercel captures this)
def log(msg):
    """Log to stderr - Vercel captures this."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except:
        pass

log("=" * 50)
log("Starting api/index.py")
log(f"Python: {sys.version_info}")

# Add parent directory to path
try:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    log(f"Parent dir: {parent_dir}")
except Exception as e:
    log(f"Error setting path: {e}")

# Disable .env loading - Vercel uses environment variables directly
os.environ.setdefault("DEBUG", "false")

# Initialize handler as None - we'll set it below
handler = None

# Try to import and create handler with comprehensive error handling
try:
    log("Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI imported")
    
    # Try importing the real app
    try:
        log("Importing app.py...")
        from app import app
        log("✓ app.py imported")
        
        # Vercel natively supports FastAPI - just export the app
        handler = app
        log("✓ Handler set to FastAPI app")
        
    except Exception as app_error:
        # If importing app fails, create error handler
        log(f"ERROR importing app: {app_error}")
        log(traceback.format_exc())
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def show_error(path: str = None):
            """Show detailed error information."""
            error_msg = str(app_error)
            error_tb = traceback.format_exc()
            
            log(f"Error handler called for path: {path}")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "message": error_msg,
                    "traceback": error_tb.split("\n"),
                    "path": path,
                    "python_path": sys.path[:5] if sys.path else []
                }
            )
        
        handler = error_app
        log("✓ Error handler created")
        
except Exception as fatal_error:
    # If even FastAPI import fails, try to create minimal handler
    log(f"FATAL ERROR: {fatal_error}")
    log(traceback.format_exc())
    
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        fatal_app = FastAPI()
        
        @fatal_app.get("/")
        @fatal_app.api_route("/{path:path}", methods=["GET", "POST"])
        async def fatal_handler(path: str = None):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Fatal initialization error",
                    "message": str(fatal_error),
                    "traceback": traceback.format_exc().split("\n")
                }
            )
        
        handler = fatal_app
        log("✓ Fatal error handler created")
        
    except Exception as e2:
        log(f"CRITICAL: Cannot create any handler: {e2}")
        handler = None

# CRITICAL: Make sure handler is ALWAYS defined
# If it's None, Vercel will crash
if handler is None:
    log("CRITICAL: Handler is None - creating emergency handler")
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        emergency_app = FastAPI()
        
        @emergency_app.get("/")
        async def emergency():
            return JSONResponse(
                status_code=500,
                content={"error": "Handler initialization completely failed"}
            )
        
        handler = emergency_app
        log("✓ Emergency handler created")
    except:
        log("ABSOLUTE FAILURE - Cannot create emergency handler")
        # This will crash Vercel, but we've tried everything
        handler = None

log("=" * 50)
log("Handler initialization complete")
log(f"Handler type: {type(handler)}")
log("=" * 50)

# Verify handler exists
if handler is None:
    raise RuntimeError("Handler is None - this will crash Vercel!")
