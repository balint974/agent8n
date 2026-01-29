from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .models import UnifiedConfig
from .config_manager import ConfigManager
import os

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

config_manager = ConfigManager()

@app.get("/")
async def read_root():
    return FileResponse('src/static/index.html')

@app.get("/api/config")
async def get_config():
    return config_manager.load()

@app.post("/api/config")
async def update_config(config: UnifiedConfig):
    config_manager.save(config)
    return {"status": "success"}

@app.post("/api/deploy")
async def deploy_config():
    config = config_manager.load()
    try:
        log = config_manager.deploy(config)
        return {"status": "deployed", "log": log}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
