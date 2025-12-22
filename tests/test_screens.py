"""Unit tests for the TUI screens."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.ui.screens.command_palette import CommandPalette
from src.ui.screens.config_screen import ConfigScreen


class TestScreens:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.USE_MLX = True
        config.PROMPT_THEME = "devops"
        config.MLX_MODEL_NAME = "test-model"
        return config

    def test_command_palette_init(self):
        palette = CommandPalette()
        assert len(palette.all_commands) > 0
        assert any(cmd[2] == "scrape" for cmd in palette.all_commands)

    def test_config_screen_init(self, mock_config):
        screen = ConfigScreen(mock_config)
        assert screen.config == mock_config
        # Check if settings list was populated
        assert len(screen.settings_list) > 0
        # Check if MLX settings are present since USE_MLX is True
        assert any("mlx" in item[0] for item in screen.settings_list if item[0])

    def test_config_screen_get_display_name(self, mock_config):
        screen = ConfigScreen(mock_config)
        assert screen.get_display_name("llm.base_url") == "Base URL"
        assert screen.get_display_name("unknown.key") == "key"

    def test_command_palette_update_list(self):
        palette = CommandPalette()
        # We need to mock query_one because palette is not mounted
        mock_list_view = MagicMock()
        with patch.object(palette, "query_one", return_value=mock_list_view):
            palette.update_list("Scrape")
            # Should have at least one entry added to list_view
            assert mock_list_view.append.called
