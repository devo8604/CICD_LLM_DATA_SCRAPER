"""Pipeline status and statistics utilities."""

import sqlite3
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.config import AppConfig


class PipelineStatus:
    """Gather and display pipeline status information."""

    def __init__(self, config: AppConfig, data_dir: Path):
        self.config = config
        self.data_dir = data_dir
        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        self.db_path = data_dir / "pipeline.db"
        self.console = Console()

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
            last_activity = cursor.fetchone()[0]

            return {
                "total_samples": total_samples,
                "total_turns": total_turns,
                "failed_files": failed_files,
                "processed_files": processed_files,
                "last_activity": last_activity,
            }
        finally:
            conn.close()

    def get_repository_count(self) -> int:
        """Count repositories in repos directory."""
        repos_dir = Path(self.config.model.base_dir) / self.config.model.pipeline.repos_dir_name
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
        repos_file = Path(self.config.model.base_dir) / "repos.txt"
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

    def display_status(self):
        """Display pipeline status overview using Rich."""
        db_stats = self.get_database_stats()
        repo_count = self.get_repository_count()
        repos_txt_count = self.get_repos_txt_count()
        db_size = self.get_database_size()
        next_action = self.get_next_recommended_action(db_stats)

        # Create status panel
        status_text = Text()
        status_text.append("Pipeline Status Overview\n\n", style="bold cyan")

        # Repositories
        status_text.append("Repositories\n", style="bold")
        status_text.append(f"  Listed in repos.txt: {repos_txt_count}\n")
        status_text.append(f"  Cloned locally: {repo_count}\n\n")

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
        status_text.append(f"  → {next_action}\n", style="cyan")

        panel = Panel(status_text, border_style="blue", padding=(1, 2))
        self.console.print(panel)


class PipelineStatistics:
    """Gather and display detailed pipeline statistics."""

    def __init__(self, config: AppConfig, data_dir: Path):
        self.config = config
        self.data_dir = data_dir
        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        self.db_path = data_dir / "pipeline.db"
        self.console = Console()

    def get_repository_breakdown(self) -> list[tuple[str, int, int]]:
        """Get Q&A count breakdown by repository."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Extract repository from dataset_source path
            cursor.execute(
                """
                SELECT
                    CASE
                        WHEN instr(dataset_source, '/repos/') > 0
                        THEN substr(dataset_source,
                            instr(dataset_source, '/repos/') + 7,
                            instr(substr(dataset_source, instr(dataset_source, '/repos/') + 7), '/') - 1
                        )
                        ELSE 'unknown'
                    END as repo,
                    COUNT(DISTINCT ts.sample_id) as sample_count,
                    COUNT(*) as turn_count
                FROM TrainingSamples ts
                JOIN ConversationTurns ct ON ts.sample_id = ct.sample_id
                GROUP BY repo
                ORDER BY sample_count DESC
                LIMIT 20
            """
            )

            return cursor.fetchall()
        finally:
            conn.close()

    def get_quality_distribution(self) -> list[tuple[float, int]]:
        """Get distribution of quality scores."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    ROUND(sample_quality_score, 1) as score_range,
                    COUNT(*) as count
                FROM TrainingSamples
                WHERE sample_quality_score IS NOT NULL
                GROUP BY score_range
                ORDER BY score_range DESC
            """
            )

            return cursor.fetchall()
        finally:
            conn.close()

    def get_failed_files_details(self) -> list[tuple[str, str, str]]:
        """Get details of failed files."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT file_path, reason, failed_at
                FROM FailedFiles
                ORDER BY failed_at DESC
                LIMIT 10
            """
            )

            return cursor.fetchall()
        finally:
            conn.close()

    def display_statistics(self, output_format: str = "table"):
        """Display detailed statistics."""
        if output_format == "json":
            self._display_json()
        else:
            self._display_table()

    def _display_table(self):
        """Display statistics as formatted tables."""
        self.console.print("\n[bold cyan]Pipeline Statistics[/bold cyan]\n")

        # Repository breakdown
        repo_data = self.get_repository_breakdown()
        if repo_data:
            table = Table(title="Top Repositories by Q&A Pairs")
            table.add_column("Repository", style="cyan")
            table.add_column("Samples", justify="right", style="green")
            table.add_column("Turns", justify="right", style="yellow")

            for repo, samples, turns in repo_data:
                table.add_row(repo, str(samples), str(turns))

            self.console.print(table)
            self.console.print()

        # Quality distribution
        quality_data = self.get_quality_distribution()
        if quality_data:
            table = Table(title="Quality Score Distribution")
            table.add_column("Score Range", justify="center", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for score, count in quality_data:
                table.add_row(f"{score:.1f}", str(count))

            self.console.print(table)
            self.console.print()

        # Failed files
        failed_data = self.get_failed_files_details()
        if failed_data:
            table = Table(title="Recent Failed Files")
            table.add_column("File", style="red", no_wrap=False, max_width=50)
            table.add_column("Reason", style="yellow", max_width=40)
            table.add_column("Failed At", style="dim")

            for file_path, reason, failed_at in failed_data:
                # Shorten file path
                short_path = "..." + file_path[-47:] if len(file_path) > 50 else file_path
                short_reason = reason[:37] + "..." if len(reason) > 40 else reason

                try:
                    dt = datetime.fromisoformat(failed_at)
                    time_str = dt.strftime("%m-%d %H:%M")
                except Exception:
                    time_str = failed_at[:16] if failed_at else ""

                table.add_row(short_path, short_reason, time_str)

            self.console.print(table)
            self.console.print()

    def _display_json(self):
        """Display statistics as JSON."""
        import json

        stats = {
            "repositories": [
                {"repo": repo, "samples": samples, "turns": turns}
                for repo, samples, turns in self.get_repository_breakdown()
            ],
            "quality_distribution": [
                {"score": score, "count": count} for score, count in self.get_quality_distribution()
            ],
            "failed_files": [
                {"file": file_path, "reason": reason, "failed_at": failed_at}
                for file_path, reason, failed_at in self.get_failed_files_details()
            ],
        }

        self.console.print(json.dumps(stats, indent=2))


def show_status(config: AppConfig, db_manager) -> None:
    """
    Show pipeline status overview.

    Args:
        config: Application configuration
        db_manager: Database manager instance
    """
    status = PipelineStatus(config, Path(config.DATA_DIR))
    status.display_status()


def show_stats(config: AppConfig, db_manager, format_type: str = "table") -> None:
    """
    Show detailed pipeline statistics.

    Args:
        config: Application configuration
        db_manager: Database manager instance
        format_type: Output format ('table' or 'json')
    """
    stats = PipelineStatistics(config, Path(config.DATA_DIR))
    stats.display_statistics(output_format=format_type)
