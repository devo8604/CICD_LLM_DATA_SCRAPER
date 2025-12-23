"""Widget classes for the Pipeline TUI."""

import sqlite3
import time
from pathlib import Path

from textual.containers import Center, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Static,
)

from src.core.config import AppConfig
from src.pipeline.realtime_status import get_battery_level, get_disk_space
from src.ui.system_monitor import format_bytes, get_system_stats


class StatusWidget(Static):
    """Base widget for status information."""

    pass


class BatteryWidget(StatusWidget):
    """Widget to display battery information."""

    battery_info = reactive((100, False))

    def __init__(self) -> None:
        super().__init__()
        self.update_battery()

    def update_battery(self) -> None:
        """Update battery information."""
        info = get_battery_level()
        if info:
            self.battery_info = info
        else:
            self.battery_info = (0, False)

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(1.0, self.update_battery)

    def watch_battery_info(self, battery_info: tuple[int, bool]) -> None:
        """Called when battery_info changes."""
        level, charging = battery_info
        charging_text = " (charging)" if charging else ""
        charging_color = "success" if charging else "warning" if level < 30 else "info"

        if level > 0:
            self.update(f"🔋 Battery: [bold]{level}%[/bold]{charging_text}")
            self.set_class(True, charging_color)
        else:
            self.update("🔋 Battery: N/A")
            self.set_class(False, "success warning info")


class DiskUsageWidget(StatusWidget):
    """Widget to display disk usage."""

    disk_usage = reactive((0, 0, 0.0))
    disk_progress = reactive(0.0)

    def __init__(self, path: str = ".") -> None:
        super().__init__()
        self.path = path
        self.update_disk()

    def update_disk(self) -> None:
        """Update disk usage information."""
        total, used, percent = get_disk_space(self.path)
        self.disk_usage = (total, used, percent)
        self.disk_progress = percent

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(2.0, self.update_disk)

    def watch_disk_usage(self, disk_info: tuple[int, int, float]) -> None:
        """Called when disk_usage changes."""
        total, used, percent = disk_info

        total_str = format_bytes(total)
        used_str = format_bytes(used)
        self.update(f"💾 Disk: [bold]{percent:.1f}%[/bold] ({used_str} / {total_str})")

    def watch_disk_progress(self, progress: float) -> None:
        """Watch progress for styling."""
        if hasattr(self, "_progress_bar"):
            self._progress_bar.update(progress / 100.0)


class DatabaseSizeWidget(StatusWidget):
    """Widget to display database size."""

    db_size_str = reactive("0 B")
    db_size_bytes = reactive(0)

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.update_db_size()

    def update_db_size(self) -> None:
        """Update database size information."""
        if self.db_path.exists():
            size_bytes = self.db_path.stat().st_size
            self.db_size_bytes = size_bytes

            # Format to human readable
            size = size_bytes
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024.0:
                    self.db_size_str = f"{size:.2f} {unit}"
                    break
                size /= 1024.0
            else:
                self.db_size_str = f"{size:.2f} PB"
        else:
            self.db_size_str = "0 B"
            self.db_size_bytes = 0

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(5.0, self.update_db_size)

    def watch_db_size_str(self, size_str: str) -> None:
        """Called when db_size_str changes."""
        self.update(f"🗄️ DB Size: [bold]{size_str}[/bold]")


class StatsWidget(Vertical):
    """Widget to display pipeline statistics."""

    stats = reactive({})

    def __init__(self, config: AppConfig, data_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.data_dir = data_dir
        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        self.db_path = Path(config.model.pipeline.data_dir) / "pipeline.db"

        # Child widgets
        self.stats_label = Label("Loading stats...")

        self.update_stats()

    def compose(self):
        yield self.stats_label

    def get_database_stats(self) -> dict:
        """Get statistics from the database."""
        if not self.db_path.exists():
            return {
                "total_samples": 0,
                "total_turns": 0,
                "failed_files": 0,
                "processed_files": 0,
                "last_activity": None,
            }

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Count training samples
            cursor.execute("SELECT COUNT(*) FROM TrainingSamples")
            total_samples = cursor.fetchone()[0]

            # Count conversation turns
            cursor.execute("SELECT COUNT(*) FROM ConversationTurns")
            total_turns = cursor.fetchone()[0]

            # Count failed files
            cursor.execute("SELECT COUNT(*) FROM FailedFiles")
            failed_files = cursor.fetchone()[0]

            # Count processed files
            cursor.execute("SELECT COUNT(*) FROM FileHashes")
            processed_files = cursor.fetchone()[0]

            # Get last processing time
            cursor.execute("SELECT MAX(last_processed) FROM FileHashes")
            result = cursor.fetchone()
            last_activity = result[0] if result and result[0] else None

            return {
                "total_samples": total_samples,
                "total_turns": total_turns,
                "failed_files": failed_files,
                "processed_files": processed_files,
                "last_activity": last_activity,
            }
        except Exception:
            return {}
        finally:
            if conn:
                conn.close()

    def update_stats(self) -> None:
        """Update statistics."""
        # Get repo counts
        repos_dir = Path(self.config.model.pipeline.base_dir) / self.config.model.pipeline.repos_dir_name
        repo_count = 0
        if repos_dir.exists():
            for org_dir in repos_dir.iterdir():
                if org_dir.is_dir() and not org_dir.name.startswith("."):
                    for repo_dir in org_dir.iterdir():
                        if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                            repo_count += 1

        repos_file = Path(self.config.model.pipeline.base_dir) / "repos.txt"
        repos_txt_count = 0
        if repos_file.exists():
            try:
                with open(repos_file, encoding="utf-8", errors="replace") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    repos_txt_count = len(lines)
            except Exception:
                repos_txt_count = 0

        # Get database stats
        db_stats = self.get_database_stats()

        self.stats = {
            "repos_txt_count": repos_txt_count,
            "repo_count": repo_count,
            **db_stats,
        }

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(3.0, self.update_stats)

    def watch_stats(self, stats: dict) -> None:
        """Called when stats change."""
        repos_txt_count = stats.get("repos_txt_count", 0)
        repo_count = stats.get("repo_count", 0)
        processed_files = stats.get("processed_files", 0)
        failed_files = stats.get("failed_files", 0)
        total_samples = stats.get("total_samples", 0)
        total_turns = stats.get("total_turns", 0)

        # Calculate average rate based on elapsed time from the tracker
        from src.ui.progress_tracker import get_progress_tracker

        tracker = get_progress_tracker()
        summary = tracker.get_progress_summary()
        elapsed_time = summary.get("elapsed_time", 0)

        if elapsed_time > 0 and processed_files > 0:
            current_rate_per_min = (processed_files / elapsed_time) * 60
        else:
            current_rate_per_min = 0.0

        failed_color = "danger" if failed_files > 0 else "success"

        content = (
            f"[bold]📦 Repositories:[/bold] {repos_txt_count} listed, {repo_count} cloned\n"
            f"[bold]📝 Files Processed:[/bold] {processed_files}\n"
            f"[bold]❌ Failed Files:[/bold] [{failed_color}]{failed_files}[/{failed_color}]\n"
            f"[bold]💡 Q&A Samples:[/bold] {total_samples}\n"
            f"[bold]💬 Conversation Turns:[/bold] {total_turns}\n"
            f"[bold]🚀 Processing Rate:[/bold] ~{current_rate_per_min:.1f} files/min\n"
        )
        self.stats_label.update(content)


class ProgressTrackingWidget(Static):
    """Widget to show comprehensive hierarchical progress tracking."""

    progress_summary = reactive({})

    def __init__(self, config: AppConfig, data_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.data_dir = data_dir

        # Get the global progress tracker
        from src.ui.progress_tracker import get_progress_tracker

        self.tracker = get_progress_tracker()

        # Update progress initially
        self._update_progress()

    def _update_progress(self) -> None:
        """Update the progress information."""
        try:
            # Get progress summary synchronously
            summary = self.tracker.get_progress_summary()
            self.progress_summary = summary
        except Exception:
            # If tracker fails, provide default values
            self.progress_summary = {
                "total_progress": 0,
                "total_repos": 0,
                "current_repo_index": 0,
                "current_repo_name": "Initialization...",
                "current_repo_files_total": 0,
                "current_repo_files_processed": 0,
                "current_file_path": "",
                "total_files": 0,
                "files_processed": 0,
            }

    def on_mount(self) -> None:
        """Start periodic updates."""
        # Schedule the update to run periodically using Textual's timer
        self.set_interval(2.0, self._update_progress)

    def _format_duration(self, seconds: float) -> str:
        """Format seconds into a human-readable duration (Wd Dh Hm Ms)."""
        if seconds < 0:
            return "00:00:00"

        if seconds < 60:
            return f"{int(seconds)}s"

        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        w, d = divmod(d, 7)

        parts = []
        if w > 0:
            parts.append(f"{w}w")
        if d > 0:
            parts.append(f"{d}d")
        if h > 0:
            parts.append(f"{h}h")
        if m > 0:
            parts.append(f"{m}m")
        if s > 0 and not w and not d:  # Only show seconds if duration is short
            parts.append(f"{s}s")

        if not parts:
            return "0s"

        return " ".join(parts[:2])  # Show only the two most significant units for clarity

    def watch_progress_summary(self, summary: dict) -> None:
        """Called when progress summary changes."""
        total_progress = summary.get("overall_progress", 0)
        total_repos = summary.get("total_repos", 0)
        current_repo_index = summary.get("current_repo_index", 0)
        current_repo_name = summary.get("current_repo_name", "Unknown")
        current_repo_files_total = summary.get("current_repo_files_total", 0)
        current_repo_files_processed = summary.get("current_repo_files_processed", 0)
        current_file_path = summary.get("current_file_path", "")
        current_file_size = summary.get("current_file_size", 0)  # Size in bytes
        total_files = summary.get("total_files", 0)
        files_processed = summary.get("files_processed", 0)
        elapsed_time = summary.get("elapsed_time", 0)
        model_name = summary.get("model_name", "Unknown")
        backend = summary.get("backend", "Unknown")

        # Calculate ETA
        eta_str = "Calculating..."
        if total_files > 0 and files_processed > 0 and elapsed_time > 0:
            rate = files_processed / elapsed_time
            remaining_files = total_files - files_processed
            if rate > 0:
                eta_seconds = remaining_files / rate
                eta_str = self._format_duration(eta_seconds)
            elif remaining_files == 0:
                eta_str = "Done"
        elif files_processed == total_files and total_files > 0:
            eta_str = "Done"
        elif total_files > 0 and files_processed == 0:
            eta_str = "Calculating..."

        elapsed_str = self._format_duration(elapsed_time)

        # Format the detailed progress string
        repo_progress = 0
        if current_repo_files_total > 0:
            repo_progress = min(100.0, (current_repo_files_processed / current_repo_files_total) * 100)

        # Format file size appropriately (B, KB, or MB)
        def format_file_size(size_bytes):
            if size_bytes >= 1024 * 1024:  # MB
                return f"{size_bytes / (1024 * 1024):.2f}MB"
            elif size_bytes >= 1024:  # KB
                return f"{size_bytes / 1024:.2f}KB"
            else:  # B
                return f"{size_bytes}B"

        # Format file path to show just the filename
        file_name = ""
        if current_file_path:
            file_name = Path(current_file_path).name

        content = (
            f"[bold]🧠 Model:[/bold] {model_name} ([bold cyan]{backend}[/bold cyan])\n"
            f"[bold]📊 Overall:[/bold] {total_progress:.1f}% ({files_processed}/{total_files} files)\n"
            f"[bold]📦 Repo:[/bold] {current_repo_index + 1}/{total_repos} - {current_repo_name}\n"
            f"[bold]📁 Repo Files:[/bold] {current_repo_files_processed}/{current_repo_files_total} "
            f"({repo_progress:.1f}%)\n"
            f"[bold]📄 Current File:[/bold] {file_name if file_name else 'Starting next...'}"
            f"{f' ({format_file_size(current_file_size)})' if current_file_size > 0 else ''}\n"
            f"[bold]⏱️ Time:[/bold] {elapsed_str} elapsed | [bold]🏁 ETA:[/bold] {eta_str}"
        )
        self.update(content)


class ProcessStatusWidget(Static):
    """Widget for overall pipeline process status."""

    status_text = reactive("Idle")
    progress_value = reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self.status_text = "Idle"
        self.progress_value = 0.0

    def watch_status_text(self, new_status: str) -> None:
        """Update the status text."""
        status_colors = {
            "Idle": "info",
            "Initializing...": "warning",  # Yellow color for initialization
            "Processing": "success",
            "Paused": "warning",
            "Terminating...": "danger",  # Red color for termination
            "Error": "danger",
        }
        color = status_colors.get(new_status, "info")
        self.update(f"[{color}][bold]Status:[/bold] {new_status}[/{color}]")

    def watch_progress_value(self, value: float) -> None:
        """Update progress visualization."""
        # This could be used to update a progress bar if needed
        pass


class MemoryWidget(StatusWidget):
    """Widget to display memory (RAM) information."""

    memory_info = reactive({})

    def __init__(self) -> None:
        super().__init__()
        self.update_memory()

    def update_memory(self) -> None:
        """Update memory information."""
        try:
            stats = get_system_stats()
            self.memory_info = stats["memory"]
        except Exception:
            self.memory_info = {
                "total": 0,
                "used": 0,
                "percent_used": 0,
                "available": 0,
            }

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(2.0, self.update_memory)

    def watch_memory_info(self, memory_info: dict) -> None:
        """Called when memory_info changes."""
        percent = memory_info.get("percent_used", 0)
        used = format_bytes(memory_info.get("used", 0))
        total = format_bytes(memory_info.get("total", 1))
        available = format_bytes(memory_info.get("available", 0))

        self.update(f"🧠 RAM: [bold]{percent:.1f}%[/bold] ({used} / {total}) [Available: {available}]")


class SwapWidget(StatusWidget):
    """Widget to display swap information."""

    swap_info = reactive({})

    def __init__(self) -> None:
        super().__init__()
        self.update_swap()

    def update_swap(self) -> None:
        """Update swap information."""
        try:
            stats = get_system_stats()
            self.swap_info = stats["swap"]
        except Exception:
            self.swap_info = {"total": 0, "used": 0, "percent_used": 0, "free": 0}

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(2.0, self.update_swap)

    def watch_swap_info(self, swap_info: dict) -> None:
        """Called when swap_info changes."""
        percent = swap_info.get("percent_used", 0)
        used_raw = swap_info.get("used", 0)
        total_raw = swap_info.get("total", 1)
        free_raw = swap_info.get("free", 0)

        used = format_bytes(used_raw)
        total = format_bytes(total_raw)
        free = format_bytes(free_raw)

        if total_raw > 0:  # Only show if swap is configured (compare raw values)
            self.update(f"💾 Swap: [bold]{percent:.1f}%[/bold] ({used} / {total}) [Free: {free}]")
        else:
            self.update("💾 Swap: Not configured")


class GPUWidget(StatusWidget):
    """Widget to display GPU information."""

    gpu_info = reactive({})

    def __init__(self) -> None:
        super().__init__()
        self.update_gpu()

    def update_gpu(self) -> None:
        """Update GPU information."""
        try:
            self.gpu_info = get_system_stats()["gpu"]
        except Exception:
            self.gpu_info = {"available": False, "type": "none", "gpus": []}

    def on_mount(self) -> None:
        """Start periodic updates."""
        self.set_interval(2.0, self.update_gpu)

    def watch_gpu_info(self, gpu_info: dict) -> None:
        """Called when gpu_info changes."""
        if gpu_info.get("available", False):
            gpus = gpu_info.get("gpus", [])
            if gpus:
                gpu = gpus[0]  # Show first GPU
                gpu_name = gpu.get("name", "Unknown")
                # Check if utilization data is available (non-zero or meaningful values exist)
                gpu_util = gpu.get("gpu_utilization", 0)
                mem_util = gpu.get("memory_utilization", 0)

                # Show utilization if available (typically for NVIDIA GPUs), otherwise just name
                if gpu_util > 0 or mem_util > 0:  # NVIDIA or similar GPU with utilization data
                    self.update(f"🎮 GPU: [bold]{gpu_util}%[/bold] ({gpu_name}) Memory: {mem_util}%")
                else:  # Apple Silicon or other GPU without detailed utilization
                    self.update(f"🎮 GPU: {gpu_name}")
            else:
                self.update("🎮 GPU: Available but no details")
        else:
            self.update("🎮 GPU: Not available")


class LogPanel(RichLog):
    """Panel to display log messages."""

    def __init__(self) -> None:
        super().__init__(max_lines=100, wrap=True, markup=True)
        self.write("📋 [bold blue]TUI Dashboard Started[/bold blue]")
        self.write("💡 Use [yellow]q[/yellow] to quit, [yellow]r[/yellow] to refresh")

    def log_message(self, message: str, level: str = "info") -> None:
        """Log a message with appropriate styling."""
        from rich.text import Text

        colors = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        }
        color = colors.get(level, "white")
        timestamp = time.strftime("%H:%M:%S")

        # message might contain ANSI codes if coming from ConsoleRenderer
        # We convert it to a Text object which handles ANSI, then wrap it in our markup
        ansi_text = Text.from_ansi(message)

        # Create final line with timestamp and color
        final_line = Text(f"[{timestamp}] ", style=color)
        final_line.append(ansi_text)

        self.write(final_line)


class InputDialog(ModalScreen[str]):
    """Modal dialog for editing configuration values."""

    def __init__(self, label: str, current_value: str, value_type: str):
        super().__init__()
        self.label_text = label
        self.current_value = current_value
        self.value_type = value_type

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(f"Edit {self.label_text}:")
            yield Input(value=self.current_value, id="dialog-input")
            with Center():
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.dismiss(self.query_one(Input).value)
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.dismiss(self.query_one(Input).value)
        elif event.key == "escape":
            self.dismiss(None)


class TerminationDialog(ModalScreen[None]):
    """Dialog shown during termination."""

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance

    def compose(self):
        with Vertical(classes="dialog termination-dialog"):
            yield Label("[bold red]TERMINATING PIPELINE[/bold red]")
            yield Label("Closing database connections...")
            yield Label("Cancelling background tasks...")
            yield Label("Saving session state...")
            yield ProgressBar(total=100, id="termination-progress")
            yield Label("Please wait, shutting down gracefully...")

    def on_mount(self) -> None:
        # Start progress animation after a short delay to ensure DOM is ready
        def start_animation():
            try:
                progress_bar = self.query_one("#termination-progress", ProgressBar)
                self.set_interval(0.1, lambda: progress_bar.advance(5))
            except Exception:
                pass

        self.set_timer(0.1, start_animation)
