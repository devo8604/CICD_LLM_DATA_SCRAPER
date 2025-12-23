"""Unit tests for ConfigScreen interactions."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.core.config import AppConfig
from src.ui.screens.config_screen import ConfigScreen


class TestConfigScreenInteractions:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.model.use_mlx = False
        config.config_loader = MagicMock()
        # Mock nested model attributes that ConfigScreen accesses
        config.model.llm.base_url = "http://localhost:11434"
        return config

    @pytest.fixture
    def screen(self, mock_config):
        return ConfigScreen(mock_config)

    def test_update_config_value(self, screen, mock_config):
        """Test _update_config_value method."""
        # Test updating a known key
        key = "llm.base_url"
        new_val = "http://new-url"
        screen._update_config_value(key, new_val, "text")

        # Verify attribute set on nested config object
        assert mock_config.model.llm.base_url == new_val
        # Verify internal tracking updated
        assert screen.config_values[key] == (new_val, "text")

    def test_save_config_success(self, screen, mock_config):
        """Test action_save_config with success."""
        # Setup some changes
        screen.config_values["llm.base_url"] = ("new-url", "text")
        screen.dismiss = MagicMock()

        with patch("src.ui.screens.config_screen.ConfigScreen.app", new_callable=PropertyMock) as mock_app_prop:
            mock_app = MagicMock()
            mock_app_prop.return_value = mock_app

            # Mock logging widget
            mock_log = MagicMock()
            mock_app.query_one.return_value = mock_log

            screen.action_save_config()

            # Verify set called on loader
            mock_config.config_loader.set.assert_any_call("llm.base_url", "new-url")
            # Verify save called
            mock_config.config_loader.save.assert_called()
            # Verify screen dismissed
            screen.dismiss.assert_called()

    def test_save_config_error(self, screen, mock_config):
        """Test action_save_config handling errors."""
        mock_config.config_loader.save.side_effect = Exception("Save failed")
        screen.dismiss = MagicMock()

        with patch("src.ui.screens.config_screen.ConfigScreen.app", new_callable=PropertyMock) as mock_app_prop:
            mock_app = MagicMock()
            mock_app_prop.return_value = mock_app

            # Mock logging widget
            mock_log = MagicMock()
            mock_app.query_one.return_value = mock_log

            screen.action_save_config()

            # Verify error logged
            mock_log.log_message.assert_called_with("Error saving config: Save failed", "error")
            screen.dismiss.assert_not_called()

    def test_reset_config(self, screen):
        """Test action_reset_config."""
        # Mock methods
        screen._update_config_value = MagicMock()
        screen.update_display = MagicMock()
        screen._get_default_value_for_key = MagicMock(return_value="default")

        # Setup config_values to have at least one key
        screen.config_values = {"llm.base_url": ("current", "text")}

        with patch("src.ui.screens.config_screen.ConfigScreen.app", new_callable=PropertyMock) as mock_app_prop:
            mock_app = MagicMock()
            mock_app_prop.return_value = mock_app

            screen.action_reset_config()

            screen._update_config_value.assert_called_with("llm.base_url", "default", "text")
            screen.update_display.assert_called()

    def test_edit_value_boolean(self, screen):
        """Test toggling a boolean value via action_edit_value."""
        # Setup
        key = "llm.mlx_quantize"
        screen.current_row_index = 0
        screen.row_keys = {0: key}
        screen.config_values[key] = (False, "boolean")
        screen.settings_list.append((key, "Quantize", "boolean"))  # Ensure get_display_name works

        screen._update_config_value = MagicMock()
        screen.update_display = MagicMock()

        # Need to run async method
        import asyncio

        asyncio.run(screen.action_edit_value())

        screen._update_config_value.assert_called_with(key, True, "boolean")
        screen.update_display.assert_called()

    def test_edit_value_input_dialog(self, screen):
        """Test opening input dialog for text/int via action_edit_value."""
        key = "llm.max_retries"
        screen.current_row_index = 0
        screen.row_keys = {0: key}
        screen.config_values[key] = (3, "integer")
        screen.settings_list.append((key, "Retries", "integer"))

        with patch("src.ui.screens.config_screen.ConfigScreen.app", new_callable=PropertyMock) as mock_app_prop:
            mock_app = MagicMock()
            mock_app_prop.return_value = mock_app

            import asyncio

            asyncio.run(screen.action_edit_value())

            # Verify push_screen called
            mock_app.push_screen.assert_called()

            # Capture callback
            args, kwargs = mock_app.push_screen.call_args
            callback = args[1]

            # Test callback with valid integer
            screen._update_config_value = MagicMock()
            screen.update_display = MagicMock()

            callback("5")
            screen._update_config_value.assert_called_with(key, 5, "integer")
            screen.update_display.assert_called()

            # Test callback with invalid integer
            screen._update_config_value.reset_mock()
            mock_app.query_one.return_value = MagicMock()  # Log widget

            callback("invalid")
            screen._update_config_value.assert_not_called()

    def test_has_unsaved_changes(self, screen):
        """Test unsaved changes detection."""
        key = "test.key"
        screen.original_values[key] = "original"

        with patch.object(screen, "_get_config_attr") as mock_get:
            mock_get.return_value = "new"
            assert screen.has_unsaved_changes(key) is True

            mock_get.return_value = "original"
            assert screen.has_unsaved_changes(key) is False

    def test_get_config_attr_unknown(self, screen):
        """Test _get_config_attr with unknown key."""
        # Ensure model returns None for unknown sections to avoid MagicMock returning another Mock
        screen.config.model.unknown = None
        assert screen._get_config_attr("unknown.key") is None
