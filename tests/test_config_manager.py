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
def test_deploy_filtered_types(mock_path_exists, mock_os_exists, mock_file, mock_makedirs, sample_config):
    mock_path_exists.return_value = True
    mock_os_exists.return_value = True

    # Mock existing settings content for JSON read
    existing_json = '{"existing_key": "value"}'

    # We need side_effect for open to handle read and write
    # If mode='r', return existing_json. If mode='w', behave normally.

    file_mock = mock_open(read_data=existing_json)

    with patch("builtins.open", file_mock):
        with patch("json.load", return_value={"existing_key": "value"}):
            manager = ConfigManager()

            # Deploy ONLY MCPs to Claude
            manager.deploy(sample_config, agent_filter=["claude"], include_types=["mcp"])

            # Verify that we wrote JSON containing MCPs
            # AND that we preserved "existing_key"

            # Get the string written to file
            # mock_open writes are cumulative in mock_calls if we don't reset, but we only did one write per file presumably

            written_content = ""
            for call in file_mock.return_value.write.call_args_list:
                if call.args:
                    written_content += str(call.args[0])

            # Check for existing data preservation
            assert '"existing_key": "value"' in written_content

            # Check for MCP
            assert '"mcpServers":' in written_content
            assert '"github":' in written_content

            # Check that Agents were NOT written (since we filtered only MCP)
            assert '"agents":' not in written_content
            assert '"FrontendBot":' not in written_content

@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists", return_value=True)
@patch("pathlib.Path.exists", return_value=True)
def test_import_logic(mock_path_exists, mock_os_exists, mock_file, mock_makedirs):
    manager = ConfigManager()
    config = UnifiedConfig()

    items_to_import = {
        "mcps": [{"name": "imported_mcp", "config": {"type": "stdio"}}],
        "agents": [],
        "skills": []
    }

    updated_config = manager.import_items(config, items_to_import)
    assert len(updated_config.mcp_servers) == 1
    assert updated_config.mcp_servers[0].name == "imported_mcp"

@patch("pathlib.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='{"mcpServers": {}}')
def test_scan_configurations(mock_file, mock_path_exists):
    manager = ConfigManager()
    config = UnifiedConfig()

    with patch("json.load", return_value={"mcpServers": {"test": {}}}) as mock_json:
        results = manager.scan_configurations(config)
        assert "Global Claude" in results
