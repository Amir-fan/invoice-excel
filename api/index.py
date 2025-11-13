# Vercel serverless function entry point
# CRITICAL: All imports must be inside try/except to prevent crashes
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

handler = None

# Try importing step by step with detailed error messages
try:
    log("Step 1: Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI imported")
    
    try:
        log("Step 2: Importing app.py...")
        # Try importing the real app
        from app import app
        log("✓ app.py imported successfully")
        
        handler = app
        log("✓ Handler set to FastAPI app")
        
    except Exception as app_error:
        # If importing app fails, create detailed error handler
        error_msg = str(app_error)
        error_tb = traceback.format_exc()
        
        log("=" * 50)
        log(f"ERROR importing app.py: {error_msg}")
        log(error_tb)
        log("=" * 50)
        
        # Create error app that shows the exact error
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def show_error(path: str = None):
            """Show detailed error information."""
            log(f"Error handler called for path: {path}")
            
            # Try to get more details about the error
            import_details = {
                "error": error_msg,
                "error_type": type(app_error).__name__,
                "traceback": error_tb.split("\n"),
            }
            
            # Try to identify which specific import failed
            if "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
                import_details["diagnosis"] = "Missing dependency or module not found"
            elif "SyntaxError" in error_msg:
                import_details["diagnosis"] = "Syntax error in Python code"
            elif "AttributeError" in error_msg:
                import_details["diagnosis"] = "Missing attribute or function"
            else:
                import_details["diagnosis"] = "Unknown import error"
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "details": import_details,
                    "path": path,
                    "python_path": sys.path[:5] if sys.path else [],
                    "parent_dir": parent_dir,
                    "help": "Check the 'error' and 'traceback' fields above for details"
                }
            )
        
        handler = error_app
        log("✓ Error handler created")
        
except Exception as fatal_error:
    # If even FastAPI import fails
    error_msg = str(fatal_error)
    error_tb = traceback.format_exc()
    
    log("=" * 50)
    log(f"FATAL ERROR: {error_msg}")
    log(error_tb)
    log("=" * 50)
    
    # This should never happen, but just in case
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
                    "message": error_msg,
                    "traceback": error_tb.split("\n"),
                    "help": "FastAPI import failed - check requirements.txt"
                }
            )
        
        handler = fatal_app
        log("✓ Fatal error handler created")
    except:
        log("CRITICAL: Cannot create any handler")
        handler = None

# Ensure handler is always defined
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

log("=" * 50)
log("Handler initialization complete")
log(f"Handler type: {type(handler)}")
log(f"Handler is None: {handler is None}")
log("=" * 50)

# Final check - raise error if handler is still None
if handler is None:
    raise RuntimeError("Handler is None - this will crash Vercel!")
