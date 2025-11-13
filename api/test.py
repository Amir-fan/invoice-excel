# Minimal test - just to verify Vercel Python works
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
@app.get("/{path:path}")
async def test(path: str = None):
    return JSONResponse(content={"status": "ok", "test": True, "path": path})

# Export for Vercel
handler = app
