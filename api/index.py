# Vercel serverless function entry point
import sys
import os
import traceback

# Log to stderr which Vercel captures
import sys as sys_module
def log(msg):
    """Log to stderr which Vercel captures."""
    print(msg, file=sys_module.stderr, flush=True)
    print(msg, flush=True)

log("=" * 50)
log("Starting api/index.py handler...")
log(f"Python version: {sys.version}")
log(f"Current directory: {os.getcwd()}")
log(f"Python path: {sys.path[:3]}")

# Add parent directory to path so we can import app
parent_dir = None
try:
    current_file = os.path.abspath(__file__)
    parent_dir = os.path.dirname(os.path.dirname(current_file))
    log(f"Parent directory: {parent_dir}")
    
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        log(f"Added {parent_dir} to sys.path")
except Exception as e:
    log(f"ERROR setting up path: {e}")
    traceback.print_exc()

# Enable debug mode if needed
os.environ.setdefault("DEBUG", "false")
log(f"DEBUG mode: {os.getenv('DEBUG')}")

handler = None

# Try to import dependencies step by step
try:
    log("Step 1: Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI imported successfully")
    
    log("Step 2: Importing dotenv...")
    from dotenv import load_dotenv
    load_dotenv()
    log("✓ dotenv loaded successfully")
    
    log("Step 3: Importing utils...")
    from utils import (
        pdf_to_image, image_to_bytes, create_temp_file, 
        cleanup_temp_file, is_pdf_file, is_image_file, check_pdf_dependencies,
        get_pdf_installation_instructions
    )
    log("✓ utils imported successfully")
    
    log("Step 4: Importing ai...")
    from ai import extract_invoice_data_from_image, extract_invoice_data_from_text
    log("✓ ai imported successfully")
    
    log("Step 5: Importing mapping...")
    from mapping import create_invoice_rows, ARABIC_HEADERS
    log("✓ mapping imported successfully")
    
    log("Step 6: Importing app...")
    from app import app
    log("✓ app imported successfully")
    
    # Import Mangum for Vercel
    log("Step 7: Importing Mangum...")
    try:
        from mangum import Mangum
        log("✓ Mangum imported successfully")
        handler = Mangum(app, lifespan="off")
        log("✓ Mangum handler created successfully")
    except ImportError as e:
        log(f"WARNING: Mangum not available: {e}")
        # Fallback: use app directly
        handler = app
        log("Using app directly as handler")
        
except Exception as e:
    error_msg = str(e)
    traceback_str = traceback.format_exc()
    
    log("=" * 50)
    log(f"ERROR: Failed during import: {error_msg}")
    log(f"Traceback:\n{traceback_str}")
    log("=" * 50)
    
    # Create error handler that will definitely work
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        error_app = FastAPI()
        
        @error_app.get("/")
        @error_app.post("/upload")
        @error_app.get("/health")
        @error_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def error_handler(path: str = None):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to initialize application",
                    "message": error_msg,
                    "traceback": traceback_str.split("\n"),
                    "path": path,
                    "python_path": sys.path[:5],
                    "parent_dir": parent_dir
                }
            )
        
        try:
            from mangum import Mangum
            handler = Mangum(error_app, lifespan="off")
        except ImportError:
            handler = error_app
            
    except Exception as e2:
        log(f"CRITICAL: Cannot even create error handler: {e2}")
        # Ultimate fallback - return a dict that Vercel can handle
        def handler(event, context):
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": str({
                    "error": "Critical failure",
                    "message": f"Import error: {error_msg}",
                    "fastapi_error": str(e2),
                    "traceback": traceback_str.split("\n")[-20:]
                })
            }

if handler is None:
    log("CRITICAL: Handler is None!")
    # Create absolute minimum handler
    def handler(event, context):
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Handler not initialized"}'
        }

log("=" * 50)
log("Handler initialization complete!")
log("=" * 50)
