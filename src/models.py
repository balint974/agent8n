from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel

class MCPEnvVar(BaseModel):
    key: str
    value: str

class MCPServer(BaseModel):
    name: str
    type: str = "stdio"  # stdio, http, sse
    command: str = ""      # For stdio
    args: List[str] = []   # For stdio
    url: str = ""          # For http/sse
    env: List[MCPEnvVar] = []

class SkillFile(BaseModel):
    filename: str
    content: str

class Skill(BaseModel):
    name: str
    description: str = ""
    files: List[SkillFile] = []

class AgentConfig(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""

class UnifiedConfig(BaseModel):
    # We keep legacy dicts for backward compatibility or extra raw settings
    common_settings: Dict[str, Any] = {}
    claude_settings: Dict[str, Any] = {}
    gemini_settings: Dict[str, Any] = {}
    codex_settings: Dict[str, Any] = {}

    # Structured High-Level Configs
    mcp_servers: List[MCPServer] = []
    skills: List[Skill] = []
    custom_agents: List[AgentConfig] = []

    projects: List[str] = []
