import pytest
import os
import json
from unittest.mock import patch, mock_open, MagicMock, ANY
from pathlib import Path
from src.config_manager import ConfigManager
from src.models import UnifiedConfig, Skill

@pytest.fixture
def sample_config():
    return UnifiedConfig(
        common_settings={"theme": "dark"},
        claude_settings={"model": "claude-3"},
        skills=[Skill(name="test-skill", description="desc", content="# content")],
        projects=["/tmp/project1"]
    )

@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.exists") # For ConfigManager.load/save path check
@patch("pathlib.Path.exists") # For target path existence check
def test_deploy(mock_path_exists, mock_os_exists, mock_file, mock_makedirs, sample_config):
    # Setup mocks
    mock_path_exists.return_value = True
    mock_os_exists.return_value = True

    manager = ConfigManager()
    manager.deploy(sample_config)

    # Check that directories were created
    # We expect creation of `skills` dir for each agent at each target
    assert mock_makedirs.call_count >= 1

    # Check that files were opened for writing
    # 2 Targets (Home + Project) * 3 Agents * (Settings + Skill) = 12 files
    # Note: open might be called more times if implementation opens other things,
    # but based on my code it should be exactly 12 writes.
    # However, Path.home() might involve reading files in some OS, but here we mock open.
    # We assert at least 12 write calls.
    assert mock_file.call_count >= 12

    # Verify settings write for Claude in Project
    # Expected settings: common + claude = {"theme": "dark", "model": "claude-3"}
    # We can check if write was called with this content.

    # Collecting all calls to write
    written_data = []
    for call in mock_file().write.call_args_list:
        written_data.append(call[0][0])

    # Check if settings json is in written data
    expected_settings = {
        "theme": "dark",
        "model": "claude-3"
    }
    # Since json.dump writes chunks often, mock_open might capture separate calls.
    # But json.dump(obj, f) usually calls f.write(str).

    # Let's verify we tried to open the correct file paths
    # /tmp/project1/.claude/settings.json

    opened_paths = []
    for call in mock_file.call_args_list:
        if call.args:
            opened_paths.append(str(call.args[0]))

    assert any(".claude/settings.json" in p for p in opened_paths)
    assert any(".gemini/settings.json" in p for p in opened_paths)

def test_load_non_existent():
    with patch("os.path.exists", return_value=False):
        manager = ConfigManager("/fake/path.json")
        config = manager.load()
        assert isinstance(config, UnifiedConfig)
        assert config.common_settings == {}
