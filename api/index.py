"""
Vercel entrypoint for the FastAPI app.

Primary path:
    from app import app
    handler = app

If that import fails (e.g. due to a missing dependency or runtime error
inside app.py, ai.py, mapping.py, or utils.py), we fall back to a tiny
FastAPI app that simply returns the error message as JSON. This prevents
Vercel from showing only a generic FUNCTION_INVOCATION_FAILED page and
lets us see the real problem in the browser.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

try:
    # Normal path: use the main app
    from app import app as fastapi_app

    handler = fastapi_app

except Exception as import_error:
    # Fallback: minimal app that surfaces the import error
    app = FastAPI(title="Invoice2Excel Error Fallback")

    @app.get("/{full_path:path}")
    async def fallback(full_path: str):
        # Show the underlying import error as JSON so it's visible on Vercel
        return JSONResponse(
            {
                "error": "Failed to import main FastAPI app",
                "detail": str(import_error),
                "path": full_path,
            },
            status_code=500,
        )

    handler = app
