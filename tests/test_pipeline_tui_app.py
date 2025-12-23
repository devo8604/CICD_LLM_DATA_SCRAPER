"""Unit tests for PipelineTUIApp logic."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.ui.pipeline_tui import PipelineTUIApp


class TestPipelineTUIAppLogic:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.model.pipeline.data_dir = "/data"
        config.model.use_mlx = False
        config.model.llm.model_name = "test-model"
        config.backend = "ollama"
        config.model.pipeline.prompt_theme = "default"
        return config

    @pytest.fixture
    def app(self, mock_config):
        return PipelineTUIApp(mock_config, Path("/data"))

    def test_init(self, app, mock_config):
        assert app.config == mock_config
        assert app.data_dir == Path("/data")
        assert app.db_path == Path("/data/pipeline.db")

    @patch("src.ui.pipeline_tui.get_progress_tracker")
    def test_on_mount(self, mock_tracker_getter, app):
        """Test on_mount setup."""
        mock_tracker = MagicMock()
        mock_tracker_getter.return_value = mock_tracker

        # Mock methods called in on_mount
        app.set_interval = MagicMock()
        app.call_later = MagicMock()
        app.query_one = MagicMock()

        # Mock size property
        from unittest.mock import PropertyMock

        with patch("src.ui.pipeline_tui.PipelineTUIApp.size", new_callable=PropertyMock) as mock_size_prop:
            mock_size = MagicMock()
            mock_size.width = 100
            mock_size_prop.return_value = mock_size

            app.on_mount()

            # Verify tracker setup
            mock_tracker.set_model_name.assert_called()
            mock_tracker.set_backend.assert_called()

            # Verify interval set
            app.set_interval.assert_called()

    def test_adjust_layout(self, app):
        """Test layout adjustment."""
        mock_container = MagicMock()
        app.query_one = MagicMock(return_value=mock_container)

        # Narrow
        app.adjust_layout(80)
        mock_container.add_class.assert_called_with("narrow-mode")

        # Wide
        app.adjust_layout(120)
        mock_container.remove_class.assert_called_with("narrow-mode")

    @patch("src.ui.pipeline_tui.get_progress_tracker")
    def test_update_progress_bar(self, mock_get_tracker, app):
        """Test progress bar updates."""
        mock_tracker = MagicMock()
        mock_tracker.get_progress_summary.return_value = {"current_file_progress": 50.0, "overall_progress": 30.0}
        mock_get_tracker.return_value = mock_tracker

        # Mock bars
        bar1 = MagicMock()
        bar2 = MagicMock()

        def query_side_effect(selector, type=None):
            if selector == "#main-progress":
                return bar1
            if selector == "#repo-progress":
                return bar2
            return MagicMock()

        app.query_one = MagicMock(side_effect=query_side_effect)

        app.update_progress_bar()

        bar1.update.assert_called_with(total=100, progress=50.0)
        bar2.update.assert_called_with(total=100, progress=30.0)

    def test_action_show_config(self, app):
        app.push_screen = MagicMock()
        app.action_show_config()
        app.push_screen.assert_called()

    def test_action_scrape_start(self, app):
        """Test starting scrape."""
        app.query_one = MagicMock()
        app.run_worker = MagicMock()
        app._processing_task = None

        app.action_scrape()

        app.run_worker.assert_called()
        assert app._processing_task is not None

    def test_action_scrape_already_running(self, app):
        """Test scrape when already running."""
        task = MagicMock()
        task.finished = False
        app._processing_task = task
        app.query_one = MagicMock()
        app.run_worker = MagicMock()

        app.action_scrape()

        app.run_worker.assert_not_called()

    @pytest.mark.asyncio
    async def test_action_quit(self, app):
        """Test quit action."""
        app.push_screen = AsyncMock()
        app.run_worker = MagicMock()

        await app.action_quit()

        app.push_screen.assert_called()  # Termination dialog
        app.run_worker.assert_called()  # Shutdown worker

    @pytest.mark.asyncio
    async def test_perform_shutdown(self, app):
        """Test shutdown logic."""
        app.exit = MagicMock()
        app.query_one = MagicMock()

        # Setup active task
        task = MagicMock()
        app._processing_task = task

        await app._perform_shutdown()

        task.cancel.assert_called()
        app.exit.assert_called()

    def test_get_orchestrator(self, app):
        """Test orchestrator lazy loading."""
        with patch("src.pipeline.di_container.setup_container") as mock_setup:
            mock_container = MagicMock()
            mock_setup.return_value = mock_container
            mock_orch = MagicMock()
            mock_container.get.return_value = mock_orch

            orch = app._get_orchestrator()

            assert orch == mock_orch
            assert app._orchestrator == mock_orch

            # Second call should return cached
            orch2 = app._get_orchestrator()
            assert orch2 == orch
            assert mock_setup.call_count == 1

    def test_action_toggle_command_palette(self, app):
        """Test opening command palette."""
        app.push_screen = MagicMock()
        app.action_toggle_command_palette()
        app.push_screen.assert_called()

    def test_action_refresh(self, app):
        app.query_one = MagicMock()
        app.action_refresh()
        app.query_one.assert_called()

    def test_action_force_quit(self, app):
        with pytest.raises(SystemExit):
            app.action_force_quit()

    def test_update_repo_progress(self, app):
        mock_bar = MagicMock()
        app.query_one = MagicMock(return_value=mock_bar)

        app._update_repo_progress(50, 100)

        mock_bar.update.assert_called_with(total=100, progress=50.0)

    @patch("src.llm.prompt_utils.get_prompt_manager")
    def test_action_reload_prompts(self, mock_get_pm, app):
        mock_pm = MagicMock()
        mock_get_pm.return_value = mock_pm
        app.query_one = MagicMock()

        app.action_reload_prompts()

        mock_pm.load_prompts.assert_called()
