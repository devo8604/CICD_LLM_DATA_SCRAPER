"""Extended unit tests for the Quickstart Wizard."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.quickstart import QuickstartWizard


class TestQuickstartWizardExtended:
    @pytest.fixture
    def wizard(self):
        config = MagicMock(spec=AppConfig)
        return QuickstartWizard(config)

    def test_run_success(self, wizard):
        """Test full run sequence."""
        with (
            patch.object(wizard, "_show_welcome") as mock_welcome,
            patch.object(wizard, "_setup_repos_file", return_value=True) as mock_repos,
            patch.object(wizard, "_setup_config", return_value=True) as mock_config,
            patch.object(wizard, "_test_connectivity") as mock_conn,
            patch.object(wizard, "_show_next_steps") as mock_next,
        ):
            wizard.run()

            mock_welcome.assert_called_once()
            mock_repos.assert_called_once()
            mock_config.assert_called_once()
            mock_conn.assert_called_once()
            mock_next.assert_called_once()

    def test_run_abort_at_repos(self, wizard):
        """Test abort if repos setup fails."""
        with (
            patch.object(wizard, "_show_welcome"),
            patch.object(wizard, "_setup_repos_file", return_value=False) as mock_repos,
            patch.object(wizard, "_setup_config") as mock_config,
        ):
            wizard.run()

            mock_repos.assert_called_once()
            mock_config.assert_not_called()

    def test_run_abort_at_config(self, wizard):
        """Test abort if config setup fails."""
        with (
            patch.object(wizard, "_show_welcome"),
            patch.object(wizard, "_setup_repos_file", return_value=True),
            patch.object(wizard, "_setup_config", return_value=False) as mock_config,
            patch.object(wizard, "_test_connectivity") as mock_conn,
        ):
            wizard.run()

            mock_config.assert_called_once()
            mock_conn.assert_not_called()

    def test_show_welcome(self, wizard):
        wizard.console.print = MagicMock()
        wizard._show_welcome()
        wizard.console.print.assert_called()

    def test_show_next_steps(self, wizard):
        wizard.console.print = MagicMock()
        wizard._show_next_steps()
        wizard.console.print.assert_called()

    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_setup_repos_file_existing_no_add(self, mock_confirm, wizard):
        """Test existing repos.txt, user declines adding more."""
        wizard.repos_file = MagicMock()
        wizard.repos_file.exists.return_value = True
        wizard.repos_file.name = "repos.txt"

        # Mock file read
        with patch("builtins.open", mock_open(read_data="repo1\nrepo2")):
            # Confirm View? -> False, Add more? -> False
            mock_confirm.side_effect = [False, False]

            result = wizard._setup_repos_file()
            assert result is True

    @patch("src.pipeline.quickstart.Confirm.ask")
    @patch("src.pipeline.quickstart.Prompt.ask")
    def test_setup_repos_file_new_add_repo(self, mock_prompt, mock_confirm, wizard):
        """Test new repos.txt, add one repo."""
        wizard.repos_file = MagicMock()
        wizard.repos_file.exists.return_value = False
        wizard.repos_file.name = "repos.txt"

        # Create repos.txt? -> True
        mock_confirm.return_value = True

        # Repos input: "http://repo", then "" to finish
        mock_prompt.side_effect = ["http://repo.git", ""]

        with patch("builtins.open", mock_open()) as mock_file:
            result = wizard._setup_repos_file()

            assert result is True
            mock_file.assert_called_with(wizard.repos_file, "w", encoding="utf-8")
            # Verify write
            handle = mock_file()
            handle.write.assert_any_call("http://repo.git\n")

    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_setup_repos_file_new_decline(self, mock_confirm, wizard):
        """Test new repos.txt declined."""
        wizard.repos_file = MagicMock()
        wizard.repos_file.exists.return_value = False

        # Create repos.txt? -> False
        mock_confirm.return_value = False

        result = wizard._setup_repos_file()
        assert result is False

    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_setup_config_existing_keep(self, mock_confirm, wizard):
        """Test existing config, keep it."""
        wizard.config_file = MagicMock()
        wizard.config_file.exists.return_value = True

        # Reconfigure? -> False
        mock_confirm.return_value = False

        result = wizard._setup_config()
        assert result is True

    @patch("src.pipeline.quickstart.Confirm.ask")
    def test_setup_config_existing_reconfigure(self, mock_confirm, wizard):
        """Test existing config, reconfigure."""
        wizard.config_file = MagicMock()
        wizard.config_file.exists.return_value = True

        # Reconfigure? -> True
        mock_confirm.return_value = True

        with patch.object(wizard, "_configure_llm", return_value=True) as mock_llm:
            result = wizard._setup_config()
            assert result is True
            mock_llm.assert_called_once()

    def test_test_connectivity_calls(self, wizard):
        """Test _test_connectivity dispatch."""
        # Case 1: MLX
        wizard.config.model.use_mlx = True
        with patch.object(wizard, "_test_mlx") as mock_mlx:
            wizard._test_connectivity()
            mock_mlx.assert_called()

        # Case 2: LlamaCpp
        wizard.config.model.use_mlx = False
        with patch.object(wizard, "_test_llamacpp") as mock_llama:
            wizard._test_connectivity()
            mock_llama.assert_called()
