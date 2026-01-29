from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from .models import UnifiedConfig
from .config_manager import ConfigManager
import os

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

config_manager = ConfigManager()

class DeployRequest(BaseModel):
    agent_filter: Optional[List[str]] = None

class ImportRequest(BaseModel):
    items: Dict[str, Any]

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
async def deploy_config(req: DeployRequest = None):
    # Handle optional body
    filter_list = req.agent_filter if req else None

    config = config_manager.load()
    try:
        log = config_manager.deploy(config, agent_filter=filter_list)
        return {"status": "deployed", "log": log}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scan")
async def scan_configs():
    config = config_manager.load()
    try:
        results = config_manager.scan_configurations(config)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import")
async def import_configs(req: ImportRequest):
    config = config_manager.load()
    try:
        updated_config = config_manager.import_items(config, req.items)
        config_manager.save(updated_config)
        return {"status": "imported", "config": updated_config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
