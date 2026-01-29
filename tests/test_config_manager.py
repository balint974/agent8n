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
@patch("os.path.exists")
@patch("pathlib.Path.exists")
def test_deploy_filtered(mock_path_exists, mock_os_exists, mock_file, mock_makedirs, sample_config):
    mock_path_exists.return_value = True
    mock_os_exists.return_value = True

    manager = ConfigManager()
    # Deploy ONLY to Claude
    manager.deploy(sample_config, agent_filter=["claude"])

    # Collect written files
    opened_paths = []
    for call in mock_file.call_args_list:
        if call.args:
            opened_paths.append(str(call.args[0]))

    # Verify Claude files are present
    assert any(".claude/settings.json" in p for p in opened_paths)

    # Verify Gemini/Codex files are NOT present
    assert not any(".gemini/settings.json" in p for p in opened_paths)
    assert not any(".codex/config.toml" in p for p in opened_paths)

@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists", return_value=True)
@patch("pathlib.Path.exists", return_value=True)
def test_import_logic(mock_path_exists, mock_os_exists, mock_file, mock_makedirs):
    manager = ConfigManager()
    config = UnifiedConfig()

    # Mock data to import
    items_to_import = {
        "mcps": [
            {
                "name": "imported_mcp",
                "config": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["server.py"]
                }
            }
        ],
        "agents": [
            {
                "name": "imported_agent",
                "config": {
                    "description": "desc",
                    "instructions": "prompt"
                }
            }
        ]
    }

    updated_config = manager.import_items(config, items_to_import)

    assert len(updated_config.mcp_servers) == 1
    assert updated_config.mcp_servers[0].name == "imported_mcp"
    assert updated_config.mcp_servers[0].command == "python"

    assert len(updated_config.custom_agents) == 1
    assert updated_config.custom_agents[0].name == "imported_agent"
    assert updated_config.custom_agents[0].system_prompt == "prompt"

@patch("pathlib.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='{"mcpServers": {"test": {"command": "echo"}}}')
def test_scan_configurations(mock_file, mock_path_exists):
    manager = ConfigManager()
    config = UnifiedConfig()

    with patch("json.load", return_value={"mcpServers": {"test": {"command": "echo"}}}) as mock_json:
        results = manager.scan_configurations(config)

        # We expect global claude/gemini to be found (mocked by read_data and json.load)
        # Note: logic loops through 3 global locations.
        assert "Global Claude" in results
        assert len(results["Global Claude"]["mcps"]) == 1
        assert results["Global Claude"]["mcps"][0]["name"] == "test"
