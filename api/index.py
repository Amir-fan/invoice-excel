# Vercel serverless function entry point
# IMPORTANT: This handler imports modules ONE AT A TIME to identify which one crashes
import sys
import os
import traceback

def log(msg):
    """Log to stderr - Vercel captures this."""
    try:
        print(msg, file=sys.stderr, flush=True)
        print(msg, flush=True)
    except:
        pass

log("=" * 50)
log("Starting api/index.py")
log(f"Python: {sys.version_info}")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
log(f"Parent dir: {parent_dir}")

os.environ.setdefault("DEBUG", "false")

handler = None

try:
    log("Step 1: Importing FastAPI...")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    log("✓ FastAPI imported")
    
    # Now try importing each dependency ONE AT A TIME
    log("Step 2: Testing imports one by one...")
    
    import_errors = []
    
    # Test utils.py
    try:
        log("  - Testing utils.py...")
        from utils import extract_number
        log("    ✓ utils.py OK")
    except Exception as e:
        log(f"    ✗ utils.py FAILED: {e}")
        import_errors.append(("utils.py", str(e), traceback.format_exc()))
    
    # Test ai.py
    try:
        log("  - Testing ai.py...")
        from ai import InvoiceData, InvoiceItem
        log("    ✓ ai.py OK")
    except Exception as e:
        log(f"    ✗ ai.py FAILED: {e}")
        import_errors.append(("ai.py", str(e), traceback.format_exc()))
    
    # Test mapping.py
    try:
        log("  - Testing mapping.py...")
        from mapping import ARABIC_HEADERS
        log("    ✓ mapping.py OK")
    except Exception as e:
        log(f"    ✗ mapping.py FAILED: {e}")
        import_errors.append(("mapping.py", str(e), traceback.format_exc()))
    
    # Now try importing app.py
    try:
        log("Step 3: Importing app.py...")
        from app import app
        log("✓ app.py imported successfully!")
        
        handler = app
        log("✓ Handler set to FastAPI app")
        
    except Exception as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        
        log("=" * 50)
        log(f"ERROR importing app.py: {error_msg}")
        log(error_tb)
        log("=" * 50)
        
        # Create error handler that shows all import errors
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
                    "app_import_error": error_msg,
                    "app_import_traceback": error_tb.split("\n"),
                    "module_import_errors": [
                        {
                            "module": mod,
                            "error": err,
                            "traceback": tb.split("\n")
                        }
                        for mod, err, tb in import_errors
                    ],
                    "path": path,
                    "python_path": sys.path[:5]
                }
            )
        
        handler = error_app
        log("✓ Error handler created")
        
except Exception as fatal_error:
    error_msg = str(fatal_error)
    error_tb = traceback.format_exc()
    
    log("=" * 50)
    log(f"FATAL ERROR: {error_msg}")
    log(error_tb)
    log("=" * 50)
    
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
                    "traceback": error_tb.split("\n")
                }
            )
        
        handler = fatal_app
        log("✓ Fatal error handler created")
    except:
        log("CRITICAL: Cannot create any handler")
        handler = None

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
        handler = None

log("=" * 50)
log("Handler initialization complete")
log(f"Handler type: {type(handler)}")
log("=" * 50)

if handler is None:
    raise RuntimeError("Handler is None - this will crash Vercel!")
