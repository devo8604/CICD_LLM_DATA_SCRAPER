"""Unit tests for the Quickstart Wizard."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.quickstart import QuickstartWizard


class TestQuickstartWizard:
    """Test cases for QuickstartWizard."""

    @pytest.fixture
    def wizard(self):
        """Create a QuickstartWizard instance for testing."""
        config = MagicMock(spec=AppConfig)
        return QuickstartWizard(config)

    @patch("src.pipeline.quickstart.Prompt.ask")
    def test_configure_llm_llama_cpp(self, mock_prompt, wizard):
        """Test LLM configuration for llama.cpp."""
        # Setup mock returns
        mock_prompt.side_effect = ["llama_cpp", "http://localhost:11454", "test-model"]

        result = wizard._configure_llm()

        assert result is True
        assert wizard.config.LLM_BASE_URL == "http://localhost:11454"
        assert wizard.config.LLM_MODEL_NAME == "test-model"

    @patch("src.pipeline.quickstart.Prompt.ask")
    def test_configure_llm_mlx(self, mock_prompt, wizard):
        """Test LLM configuration for MLX."""
        # Setup mock returns
        mock_prompt.side_effect = ["mlx"]

        # Mock _configure_mlx to return True
        with patch.object(wizard, "_configure_mlx", return_value=True) as mock_mlx:
            result = wizard._configure_llm()

            assert result is True
            mock_mlx.assert_called_once()

    @patch("src.pipeline.quickstart.IntPrompt.ask")
    @patch("src.pipeline.quickstart.Prompt.ask")
    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_configure_mlx(self, mock_confirm, mock_prompt, mock_int_prompt, wizard):
        """Test MLX configuration."""
        mock_prompt.return_value = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
        mock_int_prompt.return_value = 16

        # Mock MLX installed
        with patch("src.pipeline.quickstart.is_mlx_available", return_value=True):
            result = wizard._configure_mlx()
            assert result is True
            assert wizard.config.MLX_MODEL_NAME == "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
            assert wizard.config.MLX_MAX_RAM_GB == 16

    @patch("src.pipeline.quickstart.IntPrompt.ask")
    @patch("src.pipeline.quickstart.Prompt.ask")
    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_configure_mlx_not_installed_cancel(self, mock_confirm, mock_prompt, mock_int_prompt, wizard):
        """Test MLX configuration when MLX not installed and user cancels."""
        # User chooses not to continue without MLX
        mock_confirm.return_value = False

        # Mock MLX not installed
        with patch("src.pipeline.quickstart.is_mlx_available", return_value=False):
            with patch.object(wizard.console, "print"):
                result = wizard._configure_mlx()
                assert result is False

    @patch("src.pipeline.quickstart.httpx.Client")
    def test_test_llamacpp_success(self, mock_client, wizard):
        """Test llama.cpp connectivity check - success."""
        # Create mock config
        wizard.config.LLM_BASE_URL = "http://localhost:11454"

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        with patch("src.pipeline.quickstart.Console.print") as mock_print:
            wizard.test_llamacpp()
            # Should print success message
            mock_print.assert_called()

    @patch("src.pipeline.quickstart.httpx.Client")
    def test_test_llamacpp_failure(self, mock_client, wizard):
        """Test llama.cpp connectivity check - failure."""
        import httpx

        # Mock connection error
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("src.pipeline.quickstart.Console.print") as mock_print:
            wizard.test_llamacpp()
            # Should print error message
            mock_print.assert_called()

    def test_test_mlx_available(self, wizard):
        """Test MLX availability check - MLX available."""
        wizard.config = MagicMock()
        wizard.config.USE_MLX = True
        wizard.config.MLX_MODEL_NAME = "test-model"

        # Mock MLX availability
        with patch("src.pipeline.quickstart.is_mlx_available", return_value=True):
            with patch("src.pipeline.quickstart.Console.print") as mock_print:
                wizard.test_mlx()
                mock_print.assert_called()

    def test_test_mlx_not_available(self, wizard):
        """Test MLX availability check - MLX not available."""
        wizard.config = MagicMock()
        wizard.config.USE_MLX = True

        # Mock MLX availability
        with patch("src.pipeline.quickstart.is_mlx_available", return_value=False):
            with patch("src.pipeline.quickstart.Console.print") as mock_print:
                wizard.test_mlx()
                mock_print.assert_called()


def test_run_quickstart_wizard():
    """Test run_quickstart_wizard function."""
    from src.pipeline.quickstart import run_quickstart_wizard

    with patch("src.pipeline.quickstart.QuickstartWizard") as mock_wizard_cls:
        mock_instance = mock_wizard_cls.return_value
        mock_instance.run.return_value = None

        run_quickstart_wizard()

        mock_wizard_cls.assert_called_once()
        mock_instance.run.assert_called_once()
