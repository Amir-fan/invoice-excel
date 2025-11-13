# Vercel serverless function entry point
# Start with absolute minimum to test if Vercel Python works at all
import sys
import os
import traceback

# Write error to a file that we can read if needed
def log_error(msg):
    try:
        print(msg, file=sys.stderr, flush=True)
        print(msg, flush=True)
    except:
        pass

# Add parent directory to path
try:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    log_error(f"Parent dir: {parent_dir}")
    log_error(f"Current dir: {os.getcwd()}")
    log_error(f"Python path: {sys.path[:3]}")
except Exception as e:
    log_error(f"Error setting path: {e}")

handler = None

# Try step by step
try:
    log_error("Step 1: Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log_error("✓ FastAPI imported")
    
    log_error("Step 2: Creating error app...")
    error_app = FastAPI()
    
    @error_app.get("/")
    @error_app.post("/upload")
    @error_app.get("/health")
    @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def debug_handler(path: str = None):
        log_error(f"Request received: {path}")
        
        # Try to import the real app now, at request time
        try:
            from app import app as real_app
            from mangum import Mangum
            real_handler = Mangum(real_app, lifespan="off")
            
            # Call the real handler
            return await real_handler({}, None)
        except Exception as e:
            error_msg = str(e)
            error_tb = traceback.format_exc()
            log_error(f"Error importing real app: {error_msg}")
            log_error(error_tb)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application error",
                    "message": error_msg,
                    "traceback": error_tb.split("\n"),
                    "path": path,
                    "sys_path": sys.path[:5]
                }
            )
    
    log_error("Step 3: Importing Mangum...")
    from mangum import Mangum
    handler = Mangum(error_app, lifespan="off")
    log_error("✓ Handler created")
    
except Exception as e:
    error_msg = str(e)
    error_tb = traceback.format_exc()
    log_error(f"FATAL ERROR: {error_msg}")
    log_error(error_tb)
    
    # Ultimate fallback - return a dict
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Handler initialization failed", "message": "' + error_msg.replace('"', '\\"') + '"}'
        }

if handler is None:
    log_error("CRITICAL: Handler is None!")
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Handler not initialized"}'
        }

log_error("✓ Handler initialization complete")
