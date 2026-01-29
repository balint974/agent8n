import pytest
import os
import json
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
def test_deploy_mcp_and_agents(mock_path_exists, mock_os_exists, mock_file, mock_makedirs, sample_config):
    # Setup mocks
    mock_path_exists.return_value = True
    mock_os_exists.return_value = True

    manager = ConfigManager()
    manager.deploy(sample_config)

    # Check that we wrote to 12 files approx (Settings for 3 agents * 2 targets + Skill files)
    # We are interested in the content written to settings.json for Claude/Gemini and config.toml for Codex

    written_content = {}
    # Helper to capture what was written to which file
    # mock_file.mock_calls is complex, let's iterate open calls and their returned file handle write calls

    # Since mock_open reuse the same mock object for all opens, we need to inspect the calls carefully
    # OR we can just check if specific strings appear in ANY write call, which is simpler for this integration test.

    all_written_text = ""
    for call in mock_file().write.call_args_list:
        if call.args:
            all_written_text += str(call.args[0])

    # 1. Verify MCP Injection in JSON (Claude/Gemini)
    assert '"mcpServers":' in all_written_text
    assert '"github":' in all_written_text
    assert '"command": "npx"' in all_written_text
    assert '"TOKEN": "123"' in all_written_text

    # 2. Verify Agent Injection in JSON
    assert '"FrontendBot":' in all_written_text
    assert '"You are a vue expert"' in all_written_text

    # 3. Verify TOML generation for Codex
    assert '[mcp_servers.github]' in all_written_text
    assert 'command = "npx"' in all_written_text

    # 4. Verify Skill file creation
    # We check if open was called with correct path
    opened_paths = []
    for call in mock_file.call_args_list:
        if call.args:
            opened_paths.append(str(call.args[0]))

    assert any("skills/test-skill/test.md" in p for p in opened_paths)
    assert any("skills/test-skill/SKILL.md" in p for p in opened_paths)

def test_load_non_existent():
    with patch("os.path.exists", return_value=False):
        manager = ConfigManager("/fake/path.json")
        config = manager.load()
        assert isinstance(config, UnifiedConfig)
        assert config.mcp_servers == []
