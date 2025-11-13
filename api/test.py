# Minimal test handler - no complex imports
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mangum import Mangum

app = FastAPI()

@app.get("/")
@app.get("/{path:path}")
async def test(path: str = None):
    return JSONResponse(content={"status": "ok", "path": path})

handler = Mangum(app, lifespan="off")

