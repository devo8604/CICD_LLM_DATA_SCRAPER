"""
Text User Interface for the LLM Data Pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

import structlog
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, Label, ProgressBar

from src.core.config import AppConfig
from src.core.logging_config import TuiLoggingHandler
from src.ui.progress_tracker import get_progress_tracker
from src.ui.screens.command_palette import CommandPalette
from src.ui.screens.config_screen import ConfigScreen
from src.ui.tui_widgets import (
    BatteryWidget,
    DatabaseSizeWidget,
    DiskUsageWidget,
    GPUWidget,
    LogPanel,
    MemoryWidget,
    ProcessStatusWidget,
    ProgressTrackingWidget,
    StatsWidget,
    SwapWidget,
    TerminationDialog,
)
from src.utils.patches import apply_patches

# Apply runtime patches immediately
apply_patches()

logger = structlog.get_logger(__name__)


class PipelineTUIApp(App):
    """Main TUI application for the LLM Data Pipeline."""

    CSS_PATH = "pipeline_tui.tcss"
    BINDINGS = [
        ("escape", "quit", "Quit"),
        ("q", "force_quit", "Force Quit"),
        ("r", "refresh", "Refresh"),
        ("s", "scrape", "Scrape Repos"),
        ("p", "prepare", "Prepare Data"),
        ("e", "export", "Export Data"),
        ("c", "toggle_command_palette", "Commands"),
        ("g", "show_config", "Config"),
    ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events including ESC to ensure immediate response."""
        if event.key == "escape":
            await self.action_quit()
            event.prevent_default()
            event.stop()

    def __init__(self, config: AppConfig, data_dir: Path):
        super().__init__()
        self.config = config
        self.data_dir = data_dir
        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        self.db_path = Path(config.model.pipeline.data_dir) / "pipeline.db"
        self._orchestrator = None
        self._processing_task = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()

        # Main content grid
        with Grid(id="main-container"):
            # System metrics panel (top left)
            with Vertical(id="system-panel", classes="panel"):
                yield Label("System Metrics", classes="panel-title")
                yield BatteryWidget()
                yield DiskUsageWidget(str(self.data_dir))
                yield MemoryWidget()
                yield SwapWidget()
                yield GPUWidget()

            # Pipeline Stats panel (top right)
            with Vertical(id="status-panel", classes="panel"):
                yield Label("Pipeline Statistics", classes="panel-title")
                yield StatsWidget(self.config, self.data_dir)

            # Progress panel (middle, spans both columns)
            with Horizontal(id="progress-panel", classes="panel"):
                # Left Column: Detailed Progress Text
                with Vertical(id="progress-text-col"):
                    yield Label("Processing Details", classes="panel-title")
                    yield ProgressTrackingWidget(self.config, self.data_dir)

                # Right Column: Status, DB Info, and Progress Bars
                with Vertical(id="progress-visual-col"):
                    yield Label("Status & Resources", classes="panel-title")
                    yield ProcessStatusWidget()
                    yield DatabaseSizeWidget(self.db_path)

                    yield Label("Current File Progress:", classes="progress-label")
                    progress_bar = ProgressBar(total=100, show_eta=False)
                    progress_bar.id = "main-progress"
                    yield progress_bar

                    yield Label("Repository Progress:", classes="progress-label")
                    repo_progress_bar = ProgressBar(total=100, show_eta=False)
                    repo_progress_bar.id = "repo-progress"
                    yield repo_progress_bar

            # Log panel (bottom, spans both columns)
            with ScrollableContainer(id="log-panel", classes="panel"):
                yield Label("System Log", classes="panel-title")
                log_panel = LogPanel()
                log_panel.id = "log-widget"
                yield log_panel

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Set up periodic updates for progress bar
        self.set_interval(0.5, self.update_progress_bar)

        # Set model name in progress tracker
        tracker = get_progress_tracker()
        model_name = self.config.model.mlx.model_name if self.config.model.use_mlx else self.config.model.llm.model_name
        tracker.set_model_name(model_name)
        tracker.set_backend(self.config.backend)

        # Initial layout adjustment
        self.call_later(self.adjust_layout, self.size.width)

        try:
            bottom_log_widget = self.query_one("#log-widget", LogPanel)
            
            # Clear existing handlers from root logger to avoid duplicate/hidden output
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # Define pre-chain for TUI
            pre_chain = [
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            ]

            # Use ProcessorFormatter to render structlog events for the TUI
            tui_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=True),
                foreign_pre_chain=pre_chain,
            )

            # Add TUI logging handler to the root logger
            tui_handler = TuiLoggingHandler(bottom_log_widget.log_message)
            tui_handler.setLevel(logging.INFO)
            tui_handler.setFormatter(tui_formatter)
            root_logger.addHandler(tui_handler)

            bottom_log_widget.log_message("📋 [bold blue]TUI Dashboard Started[/bold blue]", "success")
            bottom_log_widget.log_message(
                "💡 Use [yellow]q[/yellow] to quit, [yellow]r[/yellow] to refresh",
                "info",
            )
            logger.info("TUI Dashboard Started")
        except Exception:
            pass

    def on_resize(self, event: events.Resize) -> None:
        """Handle resize events to adjust layout."""
        self.adjust_layout(event.size.width)

    def adjust_layout(self, width: int) -> None:
        """Adjust layout based on width."""
        try:
            container = self.query_one("#main-container")
            if width < 100:
                container.add_class("narrow-mode")
            else:
                container.remove_class("narrow-mode")
        except Exception:
            pass

    def _update_status_to_processing(self) -> None:
        """Update status to Processing when file processing starts."""
        try:
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Processing"
        except Exception:
            pass

    def log_to_all_panels(self, message: str, level: str = "info") -> None:
        """Log a message to both top and bottom log panels."""
        try:
            bottom_log_widget = self.query_one("#log-widget", LogPanel)
            bottom_log_widget.log_message(message, level)
        except Exception:
            pass

    def update_progress_bar(self) -> None:
        """Update the progress bars from progress tracker summary."""
        try:
            tracker = get_progress_tracker()
            summary = tracker.get_progress_summary()

            # Update Main Progress (Current File)
            try:
                progress_bar = self.query_one("#main-progress", ProgressBar)
                file_progress = summary.get("current_file_progress", 0.0)
                progress_bar.update(total=100, progress=file_progress)
            except Exception:
                pass

            # Update Repo Progress (Overall Progress)
            try:
                repo_progress_bar = self.query_one("#repo-progress", ProgressBar)
                overall_progress = summary.get("overall_progress", 0.0)
                repo_progress_bar.update(total=100, progress=overall_progress)
            except Exception:
                pass

        except Exception as e:
            logger.error("Progress bar update error", error=str(e))

    def _update_repo_progress(self, completed: int, total: int) -> None:
        """Update the repository scraping progress bar."""
        try:
            repo_progress_bar = self.query_one("#repo-progress", ProgressBar)
            progress = (completed / total) * 100 if total > 0 else 0
            repo_progress_bar.update(total=100, progress=progress)
        except Exception as e:
            logger.error("Repo progress update error", error=str(e))

    def action_refresh(self) -> None:
        """Refresh all data."""
        try:
            log_widget = self.query_one("#log-widget", LogPanel)
            log_widget.log_message("Refresh triggered", "info")
            logger.info("Dashboard refresh triggered")
        except Exception:
            pass

    async def _run_scrape(self) -> None:
        """Background task to run the scrape process."""
        try:
            # Define progress callback to update UI with repo cloning status
            def scraping_progress_callback(url, status, index, total):
                # Schedule the progress bar update on the main thread
                self.call_from_thread(self._update_repo_progress, index, total)

            loop = asyncio.get_event_loop()
            future = loop.create_future()

            def worker():
                try:
                    orchestrator = self._get_orchestrator()
                    orchestrator.scrape(scraping_progress_callback)
                    loop.call_soon_threadsafe(future.set_result, None)
                except Exception as e:
                    loop.call_soon_threadsafe(future.set_exception, e)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            await future

            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Ready"
        except Exception as e:
            logger.error("Scraping failed", error=str(e))
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Error"

    def action_scrape(self) -> None:
        """Initiate scraping process."""
        try:
            if self._processing_task is not None and not getattr(self._processing_task, "finished", True):
                self.query_one("#log-widget", LogPanel).log_message("Processing already in progress!", "warning")
                return

            logger.info("Initiating repository scraping")
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Processing"
            self._processing_task = self.run_worker(self._run_scrape(), exclusive=True)
        except Exception as e:
            logger.error("Failed to start scraping", error=str(e))

    def _get_orchestrator(self) -> Any:
        """Get or create the orchestrator."""
        if self._orchestrator is None:
            from src.pipeline.di_container import setup_container
            from src.pipeline.orchestration_service import OrchestrationService
            container = setup_container(self.config)
            self._orchestrator = container.get(OrchestrationService)
        return self._orchestrator

    async def _run_prepare(self) -> None:
        """Background task to run the prepare process."""
        try:
            orchestrator = self._get_orchestrator()
            
            self._cancellation_event = threading.Event()

            def processing_started_callback():
                self.call_later(self._update_status_to_processing)

            loop = asyncio.get_event_loop()
            future = loop.create_future()

            def worker():
                try:
                    orchestrator.prepare(processing_started_callback, self._cancellation_event)
                    loop.call_soon_threadsafe(future.set_result, None)
                except Exception as e:
                    loop.call_soon_threadsafe(future.set_exception, e)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()

            try:
                await future
            except asyncio.CancelledError:
                self._cancellation_event.set()
                raise

            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Ready"
        except Exception as e:
            logger.error("Preparation failed", error=str(e), exc_info=True)
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Error"

    def action_prepare(self) -> None:
        """Initiate prepare process."""
        try:
            if self._processing_task is not None and not getattr(self._processing_task, "finished", True):
                self.query_one("#log-widget", LogPanel).log_message("Processing already in progress!", "warning")
                return

            logger.info("Initiating data preparation")
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Initializing..."
            self._processing_task = self.run_worker(self._run_prepare(), exclusive=True)

            def ensure_processing_status():
                try:
                    sw = self.query_one(ProcessStatusWidget)
                    if sw.status_text == "Initializing...":
                        sw.status_text = "Processing"
                except Exception:
                    pass
            self.set_timer(0.5, ensure_processing_status)
        except Exception as e:
            logger.error("Failed to start preparation", error=str(e))

    def action_export(self) -> None:
        """Initiate export process."""
        try:
            logger.info("Initiating data export")
            log_widget = self.query_one("#log-widget", LogPanel)
            log_widget.log_message("Export started", "info")
        except Exception:
            pass

    async def action_quit(self) -> None:
        """Quit the application gracefully."""
        logger.info("Graceful shutdown initiated")
        await self.push_screen(TerminationDialog(self))
        self.run_worker(self._perform_shutdown(), exclusive=False)

    async def _perform_shutdown(self) -> None:
        """Perform graceful shutdown tasks."""
        logger.info("Performing shutdown tasks")
        try:
            status_widget = self.query_one(ProcessStatusWidget)
            status_widget.status_text = "Terminating..."
        except Exception:
            pass

        if hasattr(self, "_cancellation_event"):
            self._cancellation_event.set()

        if self._processing_task:
            try:
                self._processing_task.cancel()
            except Exception:
                pass

        await asyncio.sleep(1.0)
        logger.info("Application exiting")
        self.exit()

    def action_force_quit(self) -> None:
        """Force quit the application."""
        import sys
        logger.warning("Force quit initiated")
        if self._processing_task:
            try:
                self._processing_task.cancel()
            except Exception:
                pass
        sys.exit(0)

    def action_toggle_command_palette(self) -> None:
        """Open the command palette."""
        def handle_action(action_name: str | None) -> None:
            if action_name:
                method_name = f"action_{action_name}"
                if hasattr(self, method_name):
                    method = getattr(self, method_name)
                    if asyncio.iscoroutinefunction(method):
                        self.run_worker(method())
                    else:
                        method()
                elif action_name == "toggle_dark":
                    self.dark = not self.dark
        self.push_screen(CommandPalette(), handle_action)

    def action_reload_prompts(self) -> None:
        """Reload all prompts from the prompts directory."""
        try:
            from src.llm.prompt_utils import get_prompt_manager
            pm = get_prompt_manager(theme=self.config.model.pipeline.prompt_theme)
            pm.load_prompts()
            self.query_one("#log-widget", LogPanel).log_message("✅ Prompts reloaded", "success")
        except Exception as e:
            logger.error("Prompt reload failed", error=str(e))

    def action_show_config(self) -> None:
        """Show configuration screen."""
        self.push_screen(ConfigScreen(self.config))

    def on_unmount(self) -> None:
        """Clean up when app is unmounted."""
        if self._orchestrator is not None:
            try:
                self._orchestrator.close()
            except Exception:
                pass


def run_tui(config: AppConfig, data_dir: Path):
    """Run the Textual TUI application."""
    app = PipelineTUIApp(config, data_dir)
    app.run()