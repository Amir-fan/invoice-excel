"""
Vercel entrypoint for the FastAPI app.

Primary path:
    from app import app as handler

If that import fails (e.g. due to a missing dependency or runtime error
inside app.py, ai.py, mapping.py, or utils.py), we fall back to a tiny
ASGI app (no external dependencies) that returns the error as JSON.
This avoids the generic FUNCTION_INVOCATION_FAILED page and makes the
real problem visible in the browser.
"""

import json
from typing import Callable, Awaitable, Dict, Any

try:
    # Normal path: use the main FastAPI app defined in app.py
    from app import app as handler  # type: ignore

except Exception as import_error:
    # Fallback: minimal ASGI app that surfaces the import error
    async def handler(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:  # type: ignore
        if scope.get("type") != "http":
            # Only handle HTTP requests
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"text/plain; charset=utf-8"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Unsupported scope type",
                }
            )
            return

        path = scope.get("path", "/")
        body_dict = {
            "error": "Failed to import main FastAPI app",
            "detail": str(import_error),
            "path": path,
        }
        body_bytes = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body_bytes,
            }
        )
