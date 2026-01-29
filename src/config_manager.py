import os
import json
import toml
from typing import List, Dict, Any, Optional
from pathlib import Path
from .models import UnifiedConfig, Skill, MCPServer, AgentConfig, MCPEnvVar, SkillFile

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

    def deploy(self, config: UnifiedConfig, agent_filter: List[str] = None):
        targets = [Path.home()] + [Path(p) for p in config.projects]

        all_agents = {
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

        # Filter agents if filter provided
        agents = {}
        if agent_filter:
            for name, data in all_agents.items():
                if name in agent_filter:
                    agents[name] = data
        else:
            agents = all_agents

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

                        # Inject Custom Agents
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
                        with open(settings_path, 'w') as f:
                            for k, v in merged_settings.items():
                                if isinstance(v, (str, int, float, bool)):
                                    f.write(f'{k} = "{v}"\n')
                            f.write(self._convert_mcp_to_toml_structure(config.mcp_servers))

                    deployment_log.append(f"Updated settings for {agent_name} at {target}")

                    # 3. Write Skills
                    for skill in config.skills:
                        safe_skill_name = "".join([c for c in skill.name if c.isalnum() or c in ('-', '_')]).strip()
                        if not safe_skill_name: continue

                        if skill.files:
                            skill_subdir = skills_dir / safe_skill_name
                            os.makedirs(skill_subdir, exist_ok=True)

                            # SKILL.md
                            with open(skill_subdir / "SKILL.md", 'w') as f:
                                f.write(f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n")

                            for sfile in skill.files:
                                file_path = skill_subdir / sfile.filename
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(file_path, 'w') as f:
                                    f.write(sfile.content)

                    deployment_log.append(f"Deployed {len(config.skills)} skills for {agent_name} at {target}")

                except Exception as e:
                    msg = f"Error deploying to {agent_name} at {target}: {str(e)}"
                    print(msg)
                    deployment_log.append(msg)

        return deployment_log

    def scan_configurations(self, config: UnifiedConfig) -> Dict[str, Any]:
        """
        Scans global locations and project paths for existing configurations.
        Returns a dictionary structure:
        {
            "Global Claude": { "path": "...", "mcps": [...], "agents": [...], "skills": [...] },
            "Project X": { ... }
        }
        """
        scan_results = {}

        # Define search locations
        locations = [
            ("Global Claude", Path.home() / ".claude", "json"),
            ("Global Gemini", Path.home() / ".gemini", "json"),
            ("Global Codex", Path.home() / ".codex", "toml")
        ]

        # Add projects
        for proj in config.projects:
            path = Path(os.path.expanduser(proj))
            locations.append((f"Project: {path.name}", path / ".claude", "json"))
            locations.append((f"Project: {path.name}", path / ".gemini", "json"))
            locations.append((f"Project: {path.name}", path / ".codex", "toml"))

        for name, path, fmt in locations:
            if not path.exists():
                continue

            found_items = {"mcps": [], "agents": [], "skills": []}

            # Read Config File
            config_file = path / ("settings.json" if fmt == "json" else "config.toml")
            if config_file.exists():
                try:
                    if fmt == "json":
                        with open(config_file, 'r') as f:
                            data = json.load(f)
                            # Extract MCPs
                            if "mcpServers" in data:
                                for m_name, m_conf in data["mcpServers"].items():
                                    found_items["mcps"].append({
                                        "name": m_name,
                                        "config": m_conf
                                    })
                            # Extract Agents
                            if "agents" in data:
                                for a_name, a_conf in data["agents"].items():
                                    found_items["agents"].append({
                                        "name": a_name,
                                        "config": a_conf
                                    })

                    elif fmt == "toml":
                        with open(config_file, 'r') as f:
                            data = toml.load(f)
                            if "mcp_servers" in data:
                                for m_name, m_conf in data["mcp_servers"].items():
                                    found_items["mcps"].append({
                                        "name": m_name,
                                        "config": m_conf
                                    })
                except Exception as e:
                    print(f"Error reading {config_file}: {e}")

            # Read Skills
            skills_dir = path / "skills"
            if skills_dir.exists():
                for item in skills_dir.iterdir():
                    if item.is_dir():
                        # Multi-file skill
                        skill_name = item.name
                        # Check for SKILL.md
                        skill_md = item / "SKILL.md"
                        desc = ""
                        files = []

                        # Read metadata
                        if skill_md.exists():
                            # naive parse of frontmatter for description could go here
                            pass

                        # List files
                        for subfile in item.glob("**/*"):
                            if subfile.is_file():
                                try:
                                    with open(subfile, 'r') as f:
                                        content = f.read()
                                    files.append({
                                        "filename": str(subfile.relative_to(item)),
                                        "content": content
                                    })
                                except: pass

                        if files:
                            found_items["skills"].append({
                                "name": skill_name,
                                "description": desc,
                                "files": files
                            })

                    elif item.is_file() and item.suffix == ".md":
                        # Single file skill (legacy/simple)
                        try:
                            with open(item, 'r') as f:
                                content = f.read()
                            found_items["skills"].append({
                                "name": item.stem,
                                "description": "Imported from single file",
                                "files": [{"filename": item.name, "content": content}]
                            })
                        except: pass

            if found_items["mcps"] or found_items["agents"] or found_items["skills"]:
                scan_results[name] = found_items

        return scan_results

    def import_items(self, config: UnifiedConfig, items: Dict[str, Any]):
        """
        Merges items into the config.
        items structure: { "mcps": [ {name, config} ], "agents": [...], "skills": [...] }
        """

        # Import MCPs
        for mcp in items.get("mcps", []):
            name = mcp["name"]
            raw_conf = mcp["config"]

            # Normalize to MCPServer model
            new_mcp = MCPServer(name=name)

            if "type" in raw_conf:
                new_mcp.type = raw_conf["type"]

            if "command" in raw_conf:
                new_mcp.command = raw_conf["command"]

            if "args" in raw_conf:
                new_mcp.args = raw_conf["args"]

            if "url" in raw_conf:
                new_mcp.url = raw_conf["url"]

            if "env" in raw_conf and isinstance(raw_conf["env"], dict):
                new_mcp.env = [MCPEnvVar(key=k, value=v) for k,v in raw_conf["env"].items()]

            # Check for duplicates (overwrite if exists)
            existing_idx = next((i for i, x in enumerate(config.mcp_servers) if x.name == name), -1)
            if existing_idx >= 0:
                config.mcp_servers[existing_idx] = new_mcp
            else:
                config.mcp_servers.append(new_mcp)

        # Import Agents
        for agent in items.get("agents", []):
            name = agent["name"]
            raw_conf = agent["config"]

            new_agent = AgentConfig(name=name)
            new_agent.description = raw_conf.get("description", "")
            new_agent.system_prompt = raw_conf.get("instructions", "")

            existing_idx = next((i for i, x in enumerate(config.custom_agents) if x.name == name), -1)
            if existing_idx >= 0:
                config.custom_agents[existing_idx] = new_agent
            else:
                config.custom_agents.append(new_agent)

        # Import Skills
        for skill in items.get("skills", []):
            name = skill["name"]

            new_skill = Skill(name=name)
            new_skill.description = skill.get("description", "")
            new_skill.files = [SkillFile(**f) for f in skill.get("files", [])]

            existing_idx = next((i for i, x in enumerate(config.skills) if x.name == name), -1)
            if existing_idx >= 0:
                config.skills[existing_idx] = new_skill
            else:
                config.skills.append(new_skill)

        return config
