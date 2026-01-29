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

    def deploy(self, config: UnifiedConfig, agent_filter: List[str] = None, include_types: List[str] = None):
        targets = [Path.home()] + [Path(p) for p in config.projects]

        # Define agent paths and formats based on user requirements
        # Note: Project-based paths will be relative to the project root (target)

        # Global paths mapping (relative to home/target)
        # Copilot: .copilot/ (Global is ~/.copilot, Project is .copilot)
        # Gemini: .gemini/
        # Claude: .claude/

        # We need specific file logic per agent now, so the generic dict is less useful but still good for iteration

        agents_meta = {
            "claude": {
                "root": ".claude",
                "mcp_file": ".claude.json", # Note: User specified ~/.claude.json for Global. For project, usually .claude/mcp.json or similar? sticking to root relative.
                "agents_dir": ".claude/agents",
                "skills_dir": ".claude/skills",
                "mcp_format": "json"
            },
            "gemini": {
                "root": ".gemini",
                "mcp_file": ".gemini/settings.json",
                "agents_file": ".gemini/AGENT.md",
                "skills_dir": ".gemini/skills", # Keeping dir for content
                "mcp_format": "json"
            },
            "codex": {
                "root": ".copilot", # Renamed from .codex as per user instruction
                "mcp_file": ".mcp.json", # User specified ~/.mcp.json for Copilot Global
                "agents_dir": ".copilot/agents",
                "skills_dir": ".copilot/skills",
                "mcp_format": "json" # User specified JSON for .mcp.json
            }
        }

        # Filter agents
        active_agents = [a for a in agents_meta.keys() if not agent_filter or a in agent_filter]

        # Filter types
        if include_types is None:
            include_types = ["mcp", "agents", "skills"]

        deployment_log = []

        for target in targets:
            target = Path(os.path.expanduser(str(target)))
            if not target.exists():
                deployment_log.append(f"Skipping target {target}: Does not exist.")
                continue

            # Helper to handle global vs project path nuances
            is_global = target == Path.home()

            for agent_name in active_agents:
                meta = agents_meta[agent_name]

                # --- MCP Deployment ---
                if "mcp" in include_types:
                    # Determine MCP file path
                    # For Claude Global: ~/.claude.json. For Project: target/.claude.json? (Assuming symmetry or standard)
                    # For Copilot Global: ~/.mcp.json. For Project: target/.mcp.json?

                    if is_global and agent_name == "claude":
                        mcp_path = target / ".claude.json"
                    elif is_global and agent_name == "codex":
                        mcp_path = target / ".mcp.json"
                    else:
                        # Fallback/Standard project paths
                        mcp_path = target / meta["mcp_file"]

                    try:
                        # Read Existing
                        current_data = {}
                        if mcp_path.exists():
                            try:
                                with open(mcp_path, 'r') as f:
                                    current_data = json.load(f)
                            except: pass

                        # Merge MCPs
                        mcp_config = self._convert_mcp_to_json_structure(config.mcp_servers)
                        if "mcpServers" not in current_data:
                            current_data["mcpServers"] = {}
                        current_data["mcpServers"].update(mcp_config)

                        # Write
                        # Ensure parent dir exists (if file is in a subdir)
                        if mcp_path.parent != target:
                            os.makedirs(mcp_path.parent, exist_ok=True)

                        with open(mcp_path, 'w') as f:
                            json.dump(current_data, f, indent=2)

                        deployment_log.append(f"Updated MCPs for {agent_name} at {mcp_path}")
                    except Exception as e:
                        deployment_log.append(f"Error deploying MCP for {agent_name}: {e}")

                # --- Agents Deployment ---
                if "agents" in include_types:
                    try:
                        if agent_name == "gemini":
                            # Single file: AGENT.md
                            agent_path = target / meta["agents_file"]
                            os.makedirs(agent_path.parent, exist_ok=True)

                            # Concatenate all agents instructions
                            content = ""
                            for agent in config.custom_agents:
                                content += f"# {agent.name}\n\n{agent.system_prompt}\n\n"

                            with open(agent_path, 'w') as f:
                                f.write(content)
                            deployment_log.append(f"Updated Agents for {agent_name} at {agent_path}")

                        elif agent_name in ["claude", "codex"]:
                            # Directory of files
                            # Claude: agents/{name}.json (assumed format based on previous step thought process)
                            # Codex: agents/{name}.agent.md

                            agents_dir = target / meta["agents_dir"]
                            os.makedirs(agents_dir, exist_ok=True)

                            for agent in config.custom_agents:
                                safe_name = "".join([c for c in agent.name if c.isalnum() or c in ('-', '_')]).strip()
                                if not safe_name: continue

                                if agent_name == "codex":
                                    # Markdown format
                                    file_path = agents_dir / f"{safe_name}.agent.md"
                                    content = f"---\nname: {agent.name}\ndescription: {agent.description}\n---\n\n{agent.system_prompt}"
                                    with open(file_path, 'w') as f:
                                        f.write(content)
                                else:
                                    # Claude JSON format
                                    file_path = agents_dir / f"{safe_name}.json"
                                    content = {
                                        "name": agent.name,
                                        "description": agent.description,
                                        "instructions": agent.system_prompt
                                    }
                                    with open(file_path, 'w') as f:
                                        json.dump(content, f, indent=2)

                            deployment_log.append(f"Updated Agents for {agent_name} at {agents_dir}")

                    except Exception as e:
                        deployment_log.append(f"Error deploying Agents for {agent_name}: {e}")

                # --- Skills Deployment ---
                if "skills" in include_types:
                    try:
                        skills_base_dir = target / meta["skills_dir"]
                        os.makedirs(skills_base_dir, exist_ok=True)

                        for skill in config.skills:
                            safe_skill_name = "".join([c for c in skill.name if c.isalnum() or c in ('-', '_')]).strip()
                            if not safe_skill_name: continue

                            if skill.files:
                                skill_subdir = skills_base_dir / safe_skill_name
                                os.makedirs(skill_subdir, exist_ok=True)

                                with open(skill_subdir / "SKILL.md", 'w') as f:
                                    f.write(f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n")

                                for sfile in skill.files:
                                    file_path = skill_subdir / sfile.filename
                                    file_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(file_path, 'w') as f:
                                        f.write(sfile.content)

                        deployment_log.append(f"Updated Skills for {agent_name} at {skills_base_dir}")
                    except Exception as e:
                        deployment_log.append(f"Error deploying Skills for {agent_name}: {e}")

        return deployment_log

    def scan_configurations(self, config: UnifiedConfig) -> Dict[str, Any]:
        # Update scanning to look at new paths
        scan_results = {}

        locations = [
            ("Global Claude", Path.home() / ".claude", "json"),
            ("Global Gemini", Path.home() / ".gemini", "json"),
            ("Global Codex", Path.home() / ".copilot", "json") # Changed to .copilot
        ]

        for proj in config.projects:
            path = Path(os.path.expanduser(proj))
            locations.append((f"Project: {path.name}", path / ".claude", "json"))
            locations.append((f"Project: {path.name}", path / ".gemini", "json"))
            locations.append((f"Project: {path.name}", path / ".copilot", "json"))

        for name, path, fmt in locations:
            if not path.exists(): continue

            found = {"mcps": [], "agents": [], "skills": []}

            # simplified scan logic for now, similar to before but generalized
            # Note: Real implementation would need to parse specific new file formats (md, etc)
            # Keeping basic functionality intact for now.

            # Check for skills
            skills_dir = path / "skills"
            if skills_dir.exists():
                for item in skills_dir.iterdir():
                    if item.is_dir():
                        found["skills"].append({"name": item.name, "files": []})

            if found["skills"]:
                scan_results[name] = found

        return scan_results

    def import_items(self, config: UnifiedConfig, items: Dict[str, Any]):
        # Same implementation as before
        for mcp in items.get("mcps", []):
            name = mcp["name"]
            raw_conf = mcp["config"]
            new_mcp = MCPServer(name=name)
            if "type" in raw_conf: new_mcp.type = raw_conf["type"]
            if "command" in raw_conf: new_mcp.command = raw_conf["command"]
            if "args" in raw_conf: new_mcp.args = raw_conf["args"]
            if "url" in raw_conf: new_mcp.url = raw_conf["url"]
            if "env" in raw_conf and isinstance(raw_conf["env"], dict):
                new_mcp.env = [MCPEnvVar(key=k, value=v) for k,v in raw_conf["env"].items()]
            existing_idx = next((i for i, x in enumerate(config.mcp_servers) if x.name == name), -1)
            if existing_idx >= 0: config.mcp_servers[existing_idx] = new_mcp
            else: config.mcp_servers.append(new_mcp)

        for agent in items.get("agents", []):
            name = agent["name"]
            raw_conf = agent["config"]
            new_agent = AgentConfig(name=name)
            new_agent.description = raw_conf.get("description", "")
            new_agent.system_prompt = raw_conf.get("instructions", "")
            existing_idx = next((i for i, x in enumerate(config.custom_agents) if x.name == name), -1)
            if existing_idx >= 0: config.custom_agents[existing_idx] = new_agent
            else: config.custom_agents.append(new_agent)

        for skill in items.get("skills", []):
            name = skill["name"]
            new_skill = Skill(name=name)
            new_skill.description = skill.get("description", "")
            new_skill.files = [SkillFile(**f) for f in skill.get("files", [])]
            existing_idx = next((i for i, x in enumerate(config.skills) if x.name == name), -1)
            if existing_idx >= 0: config.skills[existing_idx] = new_skill
            else: config.skills.append(new_skill)

        return config
