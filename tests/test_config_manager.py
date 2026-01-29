import pytest
import os
import json
import toml
from unittest.mock import patch, mock_open, MagicMock, ANY
from pathlib import Path
from src.config_manager import ConfigManager
from src.models import UnifiedConfig, Skill, MCPServer, AgentConfig, MCPEnvVar, SkillFile

@pytest.fixture
def sample_config():
    return UnifiedConfig(
        common_settings={"theme": "dark"},
        claude_settings={"model": "claude-3"},
        skills=[
            Skill(
                name="test-skill",
                description="desc",
                files=[SkillFile(filename="test.md", content="# Content")]
            )
        ],
        mcp_servers=[
            MCPServer(name="github", type="stdio", command="npx", args=["-y", "github-mcp"], env=[MCPEnvVar(key="TOKEN", value="123")])
        ],
        custom_agents=[
            AgentConfig(name="FrontendBot", description="Vue Expert", system_prompt="You are a vue expert")
        ],
        projects=["/tmp/project1"]
    )

@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists", return_value=True)
@patch("pathlib.Path.exists", return_value=True)
def test_deploy_paths_and_formats(mock_path_exists, mock_os_exists, mock_file, mock_makedirs, sample_config):
    manager = ConfigManager()
    manager.deploy(sample_config)

    # Collect all written paths
    opened_paths = []
    for call in mock_file.call_args_list:
        if call.args:
            opened_paths.append(str(call.args[0]))

    # 1. Check Codex (Copilot) Paths
    # Agents -> .copilot/agents/*.agent.md
    assert any(".copilot/agents/FrontendBot.agent.md" in p for p in opened_paths)
    # MCP -> .mcp.json (Global) or project specific
    # Note: Logic uses .mcp.json for Global Codex and target/.mcp.json for project?
    # Let's check project path logic.
    assert any("/tmp/project1/.mcp.json" in p for p in opened_paths)

    # 2. Check Gemini Paths
    # Agents -> .gemini/AGENT.md
    assert any(".gemini/AGENT.md" in p for p in opened_paths)
    # MCP -> .gemini/settings.json
    assert any(".gemini/settings.json" in p for p in opened_paths)

    # 3. Check Claude Paths
    # Agents -> .claude/agents/*.json
    assert any(".claude/agents/FrontendBot.json" in p for p in opened_paths)
    # MCP -> .claude.json (Global) or project
    assert any("/tmp/project1/.claude.json" in p for p in opened_paths)

    # 4. Check Skills
    assert any("skills/test-skill/test.md" in p for p in opened_paths)
