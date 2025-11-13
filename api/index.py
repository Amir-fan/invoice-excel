# Vercel serverless function entry point
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
log("Starting handler initialization...")
log(f"Parent dir: {parent_dir}")
log(f"Current dir: {os.getcwd()}")

handler = None

try:
    log("Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI imported")
    
    log("Creating debug app...")
    debug_app = FastAPI()
    
    @debug_app.get("/")
    @debug_app.post("/upload")
    @debug_app.get("/health")
    @debug_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def request_handler(path: str = None):
        """Handle request - lazy load the real app."""
        log(f"Request received for path: {path}")
        
        # Try to import and use the real app
        try:
            log("Attempting to import real app...")
            from app import app as real_app
            log("✓ Real app imported")
            
            # Import Mangum
            from mangum import Mangum
            real_handler = Mangum(real_app, lifespan="off")
            
            # Note: We can't actually call the real handler from here easily
            # Instead, let's try to import it once at module level
            # But for now, return error info
            return JSONResponse(
                status_code=200,
                content={
                    "status": "debug_mode",
                    "message": "Debug handler is working. Real app imported successfully.",
                    "path": path
                }
            )
        except Exception as e:
            error_msg = str(e)
            error_tb = traceback.format_exc()
            log(f"ERROR importing real app: {error_msg}")
            log(error_tb)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to import real application",
                    "message": error_msg,
                    "traceback": error_tb.split("\n"),
                    "path": path
                }
            )
    
    log("Importing Mangum...")
    from mangum import Mangum
    handler = Mangum(debug_app, lifespan="off")
    log("✓ Handler created with debug app")
    
except Exception as e:
    error_msg = str(e)
    error_tb = traceback.format_exc()
    log(f"FATAL ERROR during initialization: {error_msg}")
    log(error_tb)
    
    # Create minimal error handler
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from mangum import Mangum
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.api_route("/{path:path}", methods=["GET", "POST"])
        async def fatal_error_handler(path: str = None):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Fatal initialization error",
                    "message": error_msg,
                    "traceback": error_tb.split("\n")
                }
            )
        
        handler = Mangum(error_app, lifespan="off")
        log("✓ Error handler created")
    except Exception as e2:
        log(f"CRITICAL: Cannot even create error handler: {e2}")
        # Last resort - but this won't work with ASGI
        handler = None

if handler is None:
    log("CRITICAL: Handler is None!")

log("=" * 50)
log("Handler initialization complete!")
log("=" * 50)
