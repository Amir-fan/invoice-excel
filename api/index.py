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
log("Initializing handler...")
log(f"Python: {sys.version}")
log(f"Parent dir: {parent_dir}")
log(f"Current dir: {os.getcwd()}")

handler = None

# Try to import everything step by step
try:
    log("Step 1: Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI OK")
    
    log("Step 2: Importing Mangum...")
    from mangum import Mangum
    log("✓ Mangum OK")
    
    log("Step 3: Importing utils...")
    from utils import (
        pdf_to_image, image_to_bytes, create_temp_file, 
        cleanup_temp_file, is_pdf_file, is_image_file
    )
    log("✓ utils OK")
    
    log("Step 4: Importing ai...")
    from ai import extract_invoice_data_from_image, extract_invoice_data_from_text
    log("✓ ai OK")
    
    log("Step 5: Importing mapping...")
    from mapping import create_invoice_rows, ARABIC_HEADERS
    log("✓ mapping OK")
    
    log("Step 6: Importing app...")
    from app import app
    log("✓ app OK")
    
    log("Step 7: Creating Mangum handler...")
    handler = Mangum(app, lifespan="off")
    log("✓ Handler created successfully!")
    
except Exception as e:
    error_msg = str(e)
    error_tb = traceback.format_exc()
    
    log("=" * 50)
    log(f"ERROR: {error_msg}")
    log(error_tb)
    log("=" * 50)
    
    # Create error handler that shows the error
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from mangum import Mangum
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def show_error(path: str = None):
            log(f"Error handler called for path: {path}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "message": error_msg,
                    "traceback": error_tb.split("\n"),
                    "path": path,
                    "parent_dir": parent_dir,
                    "current_dir": os.getcwd(),
                    "python_path": sys.path[:5]
                }
            )
        
        handler = Mangum(error_app, lifespan="off")
        log("✓ Error handler created")
        
    except Exception as e2:
        log(f"CRITICAL: Cannot create error handler: {e2}")
        log(traceback.format_exc())
        handler = None

if handler is None:
    log("CRITICAL: Handler is None - Vercel will crash!")
    # This is bad - we need at least something
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from mangum import Mangum
        
        final_app = FastAPI()
        
        @final_app.get("/")
        async def final_fallback():
            return JSONResponse(
                status_code=500,
                content={"error": "Handler initialization completely failed"}
            )
        
        handler = Mangum(final_app, lifespan="off")
        log("✓ Created final fallback handler")
    except:
        log("ABSOLUTE FAILURE - Cannot create any handler")
        # This will crash Vercel, but at least we tried
        handler = None

log("=" * 50)
log("Handler initialization complete")
log("=" * 50)
