from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class Skill(BaseModel):
    name: str
    description: str = ""
    content: str = ""  # Markdown content

class UnifiedConfig(BaseModel):
    common_settings: Dict[str, Any] = {}
    claude_settings: Dict[str, Any] = {}
    gemini_settings: Dict[str, Any] = {}
    codex_settings: Dict[str, Any] = {}
    skills: List[Skill] = []
    projects: List[str] = []
