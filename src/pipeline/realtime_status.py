"""Enhanced pipeline status with real-time updates."""

import logging
import platform
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from src.core.config import AppConfig


def get_battery_level() -> tuple[int, bool] | None:
    """
    Get battery level and charging status.
    Returns (level_percent, is_charging) or None if not available.
    """
    if platform.system() != "Darwin":
        return None

    try:
        # Use a reasonable timeout for system commands (5 seconds)
        BATTERY_CMD_TIMEOUT = 5.0
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=BATTERY_CMD_TIMEOUT,
            close_fds=False,
        )
        if result.returncode == 0:
            output = result.stdout
            # Parse: "Now drawing from 'Battery Power'\n-InternalBattery-0\t100%; charged; 0:00 remaining"
            if "internalbattery" in output.lower():
                for line in output.split("\n"):
                    if "internalbattery" in line.lower():
                        # Extract percentage
                        import re

                        match = re.search(r"(\d+)%", line)
                        if match:
                            level = int(match.group(1))
                            # Determine if battery is charging - be careful not to match 'dis'charging
                            # The status comes after the percentage, like "47%; charging; 1:36 remaining"
                            # Split by semicolons and check the status part specifically
                            parts = line.split(";")
                            if len(parts) >= 2:
                                status_part = parts[1].strip().lower()
                                is_charging = status_part == "charging"
                            else:
                                # Fallback if format is unexpected
                                is_charging = "charging" in line.lower() and "discharging" not in line.lower()
                            return level, is_charging
    except Exception:
        pass
    return None


def get_disk_space(path: str = ".") -> tuple[int, int, float]:
    """
    Get disk space information.
    Returns (total_bytes, used_bytes, percent_used).
    """
    total, used, free = shutil.disk_usage(path)
    percent_used = (used / total) * 100 if total > 0 else 0
    return total, used, percent_used


class RealTimeStatus:
    """Real-time pipeline status with constantly updating values."""

    def __init__(self, config: AppConfig, data_dir: Path):
        self.config = config
        self.data_dir = data_dir
        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        self.db_path = data_dir / "pipeline.db"
        self.console = Console()
        self._stop_flag = threading.Event()

        # Cache for performance
        self._last_db_check = 0
        self._cached_db_stats = None

    def get_database_stats(self) -> dict:
        """Get statistics from the database with caching."""
        current_time = time.time()
        cache_duration = 2  # 2 seconds cache

        if (current_time - self._last_db_check) < cache_duration and self._cached_db_stats:
            return self._cached_db_stats

        if not self.db_path.exists():
            self._cached_db_stats = {
                "total_samples": 0,
                "total_turns": 0,
                "failed_files": 0,
                "processed_files": 0,
                "last_activity": None,
            }
        else:
            import sqlite3

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
                last_activity = cursor.fetchone()[0]

                self._cached_db_stats = {
                    "total_samples": total_samples,
                    "total_turns": total_turns,
                    "failed_files": failed_files,
                    "processed_files": processed_files,
                    "last_activity": last_activity,
                }
            finally:
                conn.close()

        self._last_db_check = current_time
        return self._cached_db_stats

    def get_repository_count(self) -> int:
        """Count repositories in repos directory."""
        repos_dir = Path(self.config.model.pipeline.base_dir) / self.config.model.pipeline.repos_dir_name
        if not repos_dir.exists():
            return 0

        # Count directories (excluding hidden ones)
        count = 0
        for org_dir in repos_dir.iterdir():
            if org_dir.is_dir() and not org_dir.name.startswith("."):
                for repo_dir in org_dir.iterdir():
                    if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                        count += 1
        return count

    def get_database_size(self) -> str:
        """Get database file size in human-readable format."""
        if not self.db_path.exists():
            return "0 B"

        size_bytes = self.db_path.stat().st_size
        return self._format_bytes(size_bytes)

    def get_repos_txt_count(self) -> int:
        """Count repositories listed in repos.txt."""
        repos_file = Path(self.config.model.pipeline.base_dir) / "repos.txt"
        if not repos_file.exists():
            return 0

        try:
            with open(repos_file) as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                return len(lines)
        except Exception:
            return 0

    def get_next_recommended_action(self, db_stats: dict) -> str:
        """Suggest the next action based on current state."""
        repos_txt_count = self.get_repos_txt_count()
        repo_count = self.get_repository_count()

        if repos_txt_count == 0:
            return "Create repos.txt and add repository URLs"
        elif repo_count == 0:
            return "Run 'python3 main.py scrape' to clone repositories"
        elif db_stats["processed_files"] == 0:
            return "Run 'python3 main.py prepare' to generate Q&A pairs"
        elif db_stats["failed_files"] > 0:
            return f"Run 'python3 main.py retry' to retry {db_stats['failed_files']} failed files"
        elif db_stats["total_samples"] > 0:
            return "Run 'python3 main.py export' to export training data"
        else:
            return "Pipeline ready - run 'python3 main.py prepare' to process files"

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def _get_status_panel(self) -> Panel:
        """Create the main status panel with real-time values."""
        # Get current values
        battery_info = get_battery_level()
        disk_total, disk_used, disk_percent = get_disk_space(str(self.data_dir))
        db_size = self.get_database_size()
        db_stats = self.get_database_stats()

        # Format disk space
        disk_used_str = self._format_bytes(disk_used)
        disk_total_str = self._format_bytes(disk_total)

        status_text = Text()
        status_text.append("Pipeline Status Overview", style="bold cyan")
        status_text.append(f" (Updated: {datetime.now().strftime('%H:%M:%S')})\n\n", style="dim")

        # Repositories
        status_text.append("Repositories\n", style="bold")
        status_text.append(f"  Listed in repos.txt: {self.get_repos_txt_count()}\n")
        status_text.append(f"  Cloned locally: {self.get_repository_count()}\n\n")

        # Processing
        status_text.append("Processing\n", style="bold")
        status_text.append(f"  Files processed: {db_stats['processed_files']}\n")
        status_text.append("  Failed files: ", style="")
        if db_stats["failed_files"] > 0:
            status_text.append(f"{db_stats['failed_files']}\n", style="bold red")
        else:
            status_text.append(f"{db_stats['failed_files']}\n", style="green")

        # Training Data
        status_text.append("\nTraining Data\n", style="bold")
        status_text.append(f"  Q&A samples: {db_stats['total_samples']}\n")
        status_text.append(f"  Conversation turns: {db_stats['total_turns']}\n")
        status_text.append(f"  Database size: {db_size}\n")

        # System resources
        status_text.append("\nSystem Resources\n", style="bold")
        if battery_info:
            level, is_charging = battery_info
            charging_text = " (charging)" if is_charging else ""
            battery_color = "green" if level > 50 else "yellow" if level > 20 else "red"
            status_text.append("  Battery: ", style="")
            status_text.append(f"{level}%{charging_text}\n", style=battery_color)
        else:
            status_text.append("  Battery: N/A (not macOS)\n")

        status_text.append(f"  Disk usage: {disk_percent:.1f}% ({disk_used_str} / {disk_total_str})\n")

        # Last Activity
        if db_stats["last_activity"]:
            try:
                last_time = datetime.fromisoformat(db_stats["last_activity"])
                time_str = last_time.strftime("%Y-%m-%d %H:%M:%S")
                status_text.append(f"\n  Last activity: {time_str}\n")
            except Exception:
                pass

        # Next Action
        status_text.append("\n", style="")
        status_text.append("Next Step\n", style="bold green")
        next_action = self.get_next_recommended_action(db_stats)
        status_text.append(f"  → {next_action}\n", style="cyan")

        return Panel(status_text, border_style="blue", padding=(1, 2))

    def display_real_time_status(self, duration: int | None = None):
        """
        Display real-time status with live updates.

        Args:
            duration: Number of seconds to display, or None for infinite
        """
        start_time = time.time()

        with Live(self._get_status_panel(), refresh_per_second=1, console=self.console) as live:
            try:
                while not self._stop_flag.is_set():
                    # Check if duration has passed
                    if duration and (time.time() - start_time) >= duration:
                        break

                    live.update(self._get_status_panel())
                    time.sleep(1)
            except KeyboardInterrupt:
                logging.info("\nReal-time status interrupted by user.")

    def stop(self):
        """Stop the real-time updates."""
        self._stop_flag.set()


def show_realtime_status(config: AppConfig, data_dir: Path, duration: int | None = 30):
    """
    CLI entry point for real-time status display.

    Args:
        config: Application configuration
        data_dir: Data directory path
        duration: Duration in seconds to display (default 30s)
    """
    status = RealTimeStatus(config, data_dir)
    logging.info(f"Real-time status (will auto-stop in {duration}s). Press Ctrl+C to exit early.")
    status.display_real_time_status(duration=duration)
