from unittest.mock import MagicMock, patch

import pytest

from src.core.config_utils import (
    _convert_value,
    handle_config_command,
    init_config,
    set_config,
    show_config,
    validate_config,
)


class TestConfigUtils:
    @pytest.fixture
    def mock_console(self):
        with patch("src.core.config_utils.console") as mock:
            yield mock

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.config_loader.config_data = {"key": "value"}
        config.config_loader.config_paths = [MagicMock(exists=lambda: True, __str__=lambda x: "config.yaml")]
        return config

    def test_convert_value(self):
        assert _convert_value("true") is True
        assert _convert_value("False") is False
        assert _convert_value("123") == 123
        assert _convert_value("12.34") == 12.34
        assert _convert_value("a,b,c") == ["a", "b", "c"]
        assert _convert_value("string") == "string"

    def test_show_config_yaml(self, mock_console, mock_config):
        show_config(mock_config, "yaml")
        mock_console.print.assert_called()
        # Verify that Panel was printed
        assert mock_console.print.call_count >= 1

    def test_show_config_json(self, mock_console, mock_config):
        show_config(mock_config, "json")
        mock_console.print.assert_called()

    def test_show_config_no_data(self, mock_console, mock_config):
        mock_config.config_loader.config_data = {}
        show_config(mock_config)
        assert mock_console.print.call_count >= 2
        mock_console.print.assert_any_call("[yellow]No configuration file loaded. Using defaults.[/yellow]")

    def test_set_config(self, mock_console, mock_config):
        set_config(mock_config, "section.key", "new_value")
        mock_config.config_loader.set.assert_called_with("section.key", "new_value")
        mock_config.config_loader.save.assert_called()
        mock_console.print.assert_called()

    def test_set_config_save_error(self, mock_console, mock_config):
        mock_config.config_loader.save.side_effect = Exception("Save failed")
        set_config(mock_config, "key", "value")
        mock_console.print.assert_called_with("[red]Error saving configuration:[/red] Save failed")

    def test_validate_config_valid(self, mock_console, mock_config):
        mock_config.config_loader.validate.return_value = (True, [])
        validate_config(mock_config)
        mock_console.print.assert_called()

    def test_validate_config_invalid(self, mock_console, mock_config):
        mock_config.config_loader.validate.return_value = (
            False,
            ["Error 1", "Error 2"],
        )
        validate_config(mock_config)
        assert mock_console.print.call_count >= 2

    @patch("shutil.copy")
    @patch("pathlib.Path.exists")
    def test_init_config_success(self, mock_exists, mock_copy, mock_console):
        # First call checks destination (False), second checks example (True)
        mock_exists.side_effect = [False, True]

        init_config("new_config.yaml")

        mock_copy.assert_called_once()
        mock_console.print.assert_called()

    @patch("pathlib.Path.exists")
    def test_init_config_exists(self, mock_exists, mock_console):
        mock_exists.return_value = True
        init_config("existing.yaml")
        mock_console.print.assert_any_call("[yellow]Configuration file already exists:[/yellow] existing.yaml")

    @patch("pathlib.Path.exists")
    def test_init_config_missing_example(self, mock_exists, mock_console):
        # Destination doesn't exist, example doesn't exist
        mock_exists.side_effect = [False, False]
        init_config("new.yaml")
        mock_console.print.assert_called_with("[red]Error:[/red] config.example.yaml not found")

    def test_handle_config_command(self, mock_config):
        args = MagicMock()

        args.config_command = "show"
        args.format = "yaml"
        with patch("src.core.config_utils.show_config") as mock_show:
            handle_config_command(mock_config, args)
            mock_show.assert_called_with(mock_config, "yaml")

        args.config_command = "set"
        args.key = "k"
        args.value = "v"
        with patch("src.core.config_utils.set_config") as mock_set:
            handle_config_command(mock_config, args)
            mock_set.assert_called_with(mock_config, "k", "v")

        args.config_command = "validate"
        with patch("src.core.config_utils.validate_config") as mock_validate:
            handle_config_command(mock_config, args)
            mock_validate.assert_called_with(mock_config)

        args.config_command = "init"
        args.path = "p"
        with patch("src.core.config_utils.init_config") as mock_init:
            handle_config_command(mock_config, args)
            mock_init.assert_called_with("p")
