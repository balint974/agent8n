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
            if hasattr(config, 'model_dump'):
                data = config.model_dump()
            else:
                data = config.dict()
            json.dump(data, f, indent=2)

    def _convert_mcp_to_json_structure(self, mcp_list):
        mcp_dict = {}
        for mcp in mcp_list:
            server_config = {
                "type": mcp.type
            }
            if mcp.type == "stdio":
                server_config["command"] = mcp.command
                server_config["args"] = mcp.args
                if mcp.env:
                    server_config["env"] = {e.key: e.value for e in mcp.env}
            elif mcp.type in ["http", "sse"]:
                server_config["url"] = mcp.url

            mcp_dict[mcp.name] = server_config
        return mcp_dict

    def _convert_mcp_to_toml_structure(self, mcp_list):
        # Rough TOML conversion for Codex
        # [mcp_servers.name]
        # command = "..."
        toml_str = ""
        for mcp in mcp_list:
            toml_str += f"\n[mcp_servers.{mcp.name}]\n"
            if mcp.type == "stdio":
                toml_str += f'command = "{mcp.command}"\n'
                args_str = ", ".join([f'"{a}"' for a in mcp.args])
                toml_str += f'args = [{args_str}]\n'
                if mcp.env:
                    toml_str += f'[mcp_servers.{mcp.name}.env]\n'
                    for e in mcp.env:
                        toml_str += f'{e.key} = "{e.value}"\n'
            elif mcp.type in ["http", "sse"]:
                toml_str += f'url = "{mcp.url}"\n'
        return toml_str

    def deploy(self, config: UnifiedConfig):
        targets = [Path.home()] + [Path(p) for p in config.projects]

        agents = {
            "claude": {
                "dir_name": ".claude",
                "settings": config.claude_settings,
                "config_file": "settings.json",
                "format": "json"
            },
            "gemini": {
                "dir_name": ".gemini",
                "settings": config.gemini_settings,
                "config_file": "settings.json",
                "format": "json"
            },
            "codex": {
                "dir_name": ".codex",
                "settings": config.codex_settings,
                "config_file": "config.toml",
                "format": "toml"
            }
        }

        deployment_log = []

        for target in targets:
            target = Path(os.path.expanduser(str(target)))

            if not target.exists():
                deployment_log.append(f"Skipping target {target}: Does not exist.")
                continue

            for agent_name, agent_data in agents.items():
                agent_dir = target / agent_data["dir_name"]
                skills_dir = agent_dir / "skills"

                try:
                    os.makedirs(skills_dir, exist_ok=True)

                    # 1. Prepare Settings
                    merged_settings = config.common_settings.copy()
                    merged_settings.update(agent_data["settings"])

                    # Inject MCP Servers
                    if agent_data["format"] == "json":
                        mcp_json = self._convert_mcp_to_json_structure(config.mcp_servers)
                        if "mcpServers" not in merged_settings:
                            merged_settings["mcpServers"] = {}
                        merged_settings["mcpServers"].update(mcp_json)

                        # Inject Custom Agents (simplistic injection for now)
                        if config.custom_agents:
                             if "agents" not in merged_settings:
                                 merged_settings["agents"] = {}
                             for agent in config.custom_agents:
                                 merged_settings["agents"][agent.name] = {
                                     "description": agent.description,
                                     "instructions": agent.system_prompt
                                 }

                    settings_path = agent_dir / agent_data["config_file"]

                    # 2. Write Settings File
                    if agent_data["format"] == "json":
                        with open(settings_path, 'w') as f:
                            json.dump(merged_settings, f, indent=2)
                    elif agent_data["format"] == "toml":
                        # Basic TOML writer for Codex
                        with open(settings_path, 'w') as f:
                            # Dump generic settings as simplistic KV pairs (imperfect but functional for now)
                            for k, v in merged_settings.items():
                                if isinstance(v, (str, int, float, bool)):
                                    f.write(f'{k} = "{v}"\n')
                            # Append MCP TOML
                            f.write(self._convert_mcp_to_toml_structure(config.mcp_servers))

                    deployment_log.append(f"Updated settings for {agent_name} at {target}")

                    # 3. Write Skills
                    for skill in config.skills:
                        # New Multi-file logic
                        safe_skill_name = "".join([c for c in skill.name if c.isalnum() or c in ('-', '_')]).strip()
                        if not safe_skill_name: continue

                        # If skill has files, use directory structure
                        if skill.files:
                            skill_subdir = skills_dir / safe_skill_name
                            os.makedirs(skill_subdir, exist_ok=True)

                            # Create SKILL.md (Metadata/Instructions)
                            with open(skill_subdir / "SKILL.md", 'w') as f:
                                f.write(f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n")
                                # If there's content in the top-level (legacy), verify if we should put it here or if files cover it.
                                # The current model doesn't have top-level content field anymore in this updated logic,
                                # but we haven't removed it from frontend yet. We'll assume 'files' is the primary source.

                            for sfile in skill.files:
                                file_path = skill_subdir / sfile.filename
                                # Ensure subdirectory creation if filename has path
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(file_path, 'w') as f:
                                    f.write(sfile.content)
                        else:
                            # Fallback logic if needed, or skip empty skills
                            pass

                    deployment_log.append(f"Deployed {len(config.skills)} skills for {agent_name} at {target}")

                except Exception as e:
                    msg = f"Error deploying to {agent_name} at {target}: {str(e)}"
                    print(msg)
                    deployment_log.append(msg)

        return deployment_log
