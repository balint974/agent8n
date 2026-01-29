import os
import json
from typing import List, Dict, Any
from pathlib import Path
from .models import UnifiedConfig, Skill

class ConfigManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            self.config_path = os.path.expanduser("~/.unified-agent-config.json")
        else:
            self.config_path = config_path

    def load(self) -> UnifiedConfig:
        if not os.path.exists(self.config_path):
            return UnifiedConfig()

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            return UnifiedConfig(**data)
        except Exception as e:
            print(f"Error loading config: {e}")
            return UnifiedConfig()

    def save(self, config: UnifiedConfig):
        with open(self.config_path, 'w') as f:
            # Handle Pydantic v1 vs v2
            if hasattr(config, 'model_dump'):
                data = config.model_dump()
            else:
                data = config.dict()
            json.dump(data, f, indent=2)

    def deploy(self, config: UnifiedConfig):
        # Targets: Global (Home) + Projects
        targets = [Path.home()] + [Path(p) for p in config.projects]

        # Agent configurations
        agents = {
            "claude": {
                "dir_name": ".claude",
                "settings": config.claude_settings,
                "config_file": "settings.json"
            },
            "gemini": {
                "dir_name": ".gemini",
                "settings": config.gemini_settings,
                "config_file": "settings.json"
            },
            "codex": {
                "dir_name": ".codex",
                "settings": config.codex_settings,
                "config_file": "settings.json"
            }
        }

        deployment_log = []

        for target in targets:
            # Expand user path if needed (e.g. for projects added with ~)
            target = Path(os.path.expanduser(str(target)))

            if not target.exists():
                msg = f"Skipping target {target}: Does not exist."
                print(msg)
                deployment_log.append(msg)
                continue

            for agent_name, agent_data in agents.items():
                agent_dir = target / agent_data["dir_name"]
                skills_dir = agent_dir / "skills"

                try:
                    # Create directories
                    os.makedirs(skills_dir, exist_ok=True)

                    # 1. Write Settings
                    # Merge common with specific
                    merged_settings = config.common_settings.copy()
                    merged_settings.update(agent_data["settings"])

                    settings_path = agent_dir / agent_data["config_file"]

                    with open(settings_path, 'w') as f:
                        json.dump(merged_settings, f, indent=2)

                    deployment_log.append(f"Updated settings for {agent_name} at {target}")

                    # 2. Write Skills
                    for skill in config.skills:
                        skill_file_content = f"""---
name: {skill.name}
description: {skill.description}
---

{skill.content}
"""
                        # Sanitize filename
                        safe_name = "".join([c for c in skill.name if c.isalnum() or c in ('-', '_')]).strip()
                        if not safe_name:
                            safe_name = "unnamed_skill"

                        skill_path = skills_dir / f"{safe_name}.md"

                        with open(skill_path, 'w') as f:
                            f.write(skill_file_content)

                    deployment_log.append(f"Deployed {len(config.skills)} skills for {agent_name} at {target}")

                except Exception as e:
                    msg = f"Error deploying to {agent_name} at {target}: {str(e)}"
                    print(msg)
                    deployment_log.append(msg)

        return deployment_log
