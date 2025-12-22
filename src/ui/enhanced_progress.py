"""Enhanced progress bars with rich context and statistics."""

import time
from dataclasses import dataclass, field
from datetime import timedelta

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from src.core.utils import get_battery_status


@dataclass
class ProcessingStats:
    """Statistics for processing progress."""

    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    qa_pairs_generated: int = 0
    tokens_used: int = 0
    start_time: float = field(default_factory=time.time)
    current_file: str = ""
    current_repo: str = ""

    @property
    def total_files(self) -> int:
        """Total files attempted."""
        return self.files_processed + self.files_skipped + self.files_failed

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.files_processed / self.total_files) * 100

    @property
    def elapsed_time(self) -> float:
        """Elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def elapsed_timedelta(self) -> timedelta:
        """Elapsed time as timedelta."""
        return timedelta(seconds=int(self.elapsed_time))

    def estimated_cost(self, model_pricing: dict | None = None) -> float:
        """
        Estimate API cost based on tokens used.

        Args:
            model_pricing: Dict with 'input_price' and 'output_price' per 1M tokens

        Returns:
            Estimated cost in dollars
        """
        if model_pricing is None:
            # Default pricing (rough estimate for common models)
            model_pricing = {
                "input_price": 0.15,  # per 1M tokens
                "output_price": 0.60,  # per 1M tokens
            }

        # Rough estimate: assume 30% input, 70% output
        input_tokens = self.tokens_used * 0.3
        output_tokens = self.tokens_used * 0.7

        input_cost = (input_tokens / 1_000_000) * model_pricing["input_price"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output_price"]

        return input_cost + output_cost


class EnhancedProgressDisplay:
    """Enhanced progress display with rich context."""

    def __init__(self, total_repos: int = 0, show_battery: bool = True):
        """
        Initialize enhanced progress display.

        Args:
            total_repos: Total number of repositories to process
            show_battery: Whether to show battery status
        """
        self.console = Console()
        self.stats = ProcessingStats()
        self.total_repos = total_repos
        self.show_battery = show_battery

        # Create Rich progress bars
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=False,
        )

        self.repo_task = self.progress.add_task("[cyan]Repositories", total=total_repos)
        self.file_task = self.progress.add_task("[green]Files", total=0)

        self.live: Live | None = None
        self.last_battery_check = 0
        self.battery_info = {"percent": 100, "plugged": True}

    def _get_stats_table(self) -> Table:
        """Create a table with current statistics."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="right")
        table.add_column(style="bold")

        # Files statistics
        table.add_row("Processed:", f"{self.stats.files_processed}")
        table.add_row("Skipped:", f"{self.stats.files_skipped}")
        table.add_row("Failed:", f"[red]{self.stats.files_failed}[/red]")

        # Q&A pairs
        table.add_row("", "")
        table.add_row("Q&A Pairs:", f"[green]{self.stats.qa_pairs_generated}[/green]")

        # Token usage and cost
        if self.stats.tokens_used > 0:
            table.add_row("", "")
            table.add_row("Tokens:", f"{self.stats.tokens_used:,}")
            cost = self.stats.estimated_cost()
            table.add_row("Est. Cost:", f"${cost:.4f}")

        # Success rate
        table.add_row("", "")
        success_rate = self.stats.success_rate
        color = "green" if success_rate >= 90 else "yellow" if success_rate >= 70 else "red"
        table.add_row("Success Rate:", f"[{color}]{success_rate:.1f}%[/{color}]")

        # Time
        table.add_row("", "")
        table.add_row("Elapsed:", str(self.stats.elapsed_timedelta))

        return table

    def _get_current_status(self) -> Text:
        """Get current processing status text."""
        status = Text()

        if self.stats.current_repo:
            status.append("Repository: ", style="dim")
            status.append(f"{self.stats.current_repo}\n", style="cyan")

        if self.stats.current_file:
            status.append("Current File: ", style="dim")
            # Truncate long filenames
            filename = self.stats.current_file
            if len(filename) > 60:
                filename = "..." + filename[-57:]
            status.append(filename, style="yellow")

        return status

    def _get_battery_display(self) -> Text | None:
        """Get battery status display."""
        if not self.show_battery:
            return None

        # Check battery every 10 seconds
        current_time = time.time()
        if current_time - self.last_battery_check > 10:
            self.battery_info = get_battery_status()
            self.last_battery_check = current_time

        if self.battery_info is None:
            return None

        battery = Text()
        percent = self.battery_info.get("percent", 0)
        plugged = self.battery_info.get("plugged", False)

        # Choose color based on battery level
        if plugged:
            color = "green"
            icon = "🔌"
        elif percent > 50:
            color = "green"
            icon = "🔋"
        elif percent > 20:
            color = "yellow"
            icon = "🔋"
        else:
            color = "red"
            icon = "🪫"

        battery.append(f"{icon} Battery: ", style="dim")
        battery.append(f"{percent}%", style=color)
        if plugged:
            battery.append(" (charging)", style="dim")

        return battery

    def _create_display_panel(self) -> Panel:
        """Create the main display panel."""
        # Create layout
        content = Table.grid(padding=(0, 2))
        content.add_column(ratio=2)
        content.add_column(ratio=1)

        # Left column: Progress bars
        left_content = self.progress

        # Right column: Stats
        right_content = self._get_stats_table()

        content.add_row(left_content, right_content)

        # Add current status below
        status = self._get_current_status()
        if status.plain:
            content.add_row(status, "")

        # Add battery status if available
        battery = self._get_battery_display()
        if battery:
            content.add_row(battery, "")

        return Panel(
            content,
            title="[bold cyan]Pipeline Progress[/bold cyan]",
            border_style="blue",
            padding=(1, 2),
        )

    def start(self):
        """Start the live display."""
        self.live = Live(
            self._create_display_panel(),
            console=self.console,
            refresh_per_second=2,
        )
        self.live.start()

    def stop(self):
        """Stop the live display."""
        if self.live:
            self.live.stop()

    def update_display(self):
        """Update the display with current information."""
        if self.live:
            self.live.update(self._create_display_panel())

    def update_repo_progress(self, current: int, description: str = ""):
        """
        Update repository progress.

        Args:
            current: Current repository index
            description: Description text
        """
        self.stats.current_repo = description
        self.progress.update(
            self.repo_task,
            completed=current,
            description=f"[cyan]Repositories ({description})",
        )
        self.update_display()

    def update_file_progress(self, total: int, current: int, description: str = ""):
        """
        Update file progress.

        Args:
            total: Total files in current repo
            current: Current file index
            description: Description text
        """
        self.progress.update(
            self.file_task,
            total=total,
            completed=current,
            description=f"[green]Files in {description}",
        )
        self.update_display()

    def set_current_file(self, filename: str):
        """
        Set the current file being processed.

        Args:
            filename: Name of current file
        """
        self.stats.current_file = filename
        self.update_display()

    def record_file_processed(self, qa_count: int = 0, tokens: int = 0):
        """
        Record a successfully processed file.

        Args:
            qa_count: Number of Q&A pairs generated
            tokens: Number of tokens used
        """
        self.stats.files_processed += 1
        self.stats.qa_pairs_generated += qa_count
        self.stats.tokens_used += tokens
        self.update_display()

    def record_file_skipped(self):
        """Record a skipped file."""
        self.stats.files_skipped += 1
        self.update_display()

    def record_file_failed(self):
        """Record a failed file."""
        self.stats.files_failed += 1
        self.update_display()

    def print_summary(self):
        """Print final summary."""
        self.console.print("\n")
        summary = Table(title="[bold green]Processing Complete[/bold green]")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", justify="right", style="bold")

        summary.add_row("Total Files Attempted", str(self.stats.total_files))
        summary.add_row("Files Processed", str(self.stats.files_processed))
        summary.add_row("Files Skipped", str(self.stats.files_skipped))
        summary.add_row(
            "Files Failed",
            (f"[red]{self.stats.files_failed}[/red]" if self.stats.files_failed > 0 else "0"),
        )
        summary.add_row("", "")
        summary.add_row("Q&A Pairs Generated", f"[green]{self.stats.qa_pairs_generated}[/green]")

        if self.stats.tokens_used > 0:
            summary.add_row("", "")
            summary.add_row("Total Tokens", f"{self.stats.tokens_used:,}")
            cost = self.stats.estimated_cost()
            summary.add_row("Estimated Cost", f"${cost:.4f}")

        summary.add_row("", "")
        success_rate = self.stats.success_rate
        color = "green" if success_rate >= 90 else "yellow" if success_rate >= 70 else "red"
        summary.add_row("Success Rate", f"[{color}]{success_rate:.1f}%[/{color}]")

        summary.add_row("", "")
        summary.add_row("Total Time", str(self.stats.elapsed_timedelta))

        self.console.print(summary)
