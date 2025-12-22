"""Pre-flight validation checks before running pipeline commands."""

import shutil
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich.text import Text

from src.core.config import AppConfig
from src.core.utils import get_battery_status


class PreflightCheck:
    """Represents a single pre-flight validation check."""

    def __init__(
        self,
        name: str,
        status: str = "pending",
        message: str = "",
        severity: str = "error",
    ):
        """
        Initialize a preflight check.

        Args:
            name: Name of the check
            status: Status ('pending', 'pass', 'warning', 'fail')
            message: Detailed message about the check result
            severity: Severity level ('error', 'warning', 'info')
        """
        self.name = name
        self.status = status
        self.message = message
        self.severity = severity


class PreflightValidator:
    """Run pre-flight validation checks before pipeline execution."""

    def __init__(self, config: AppConfig, data_dir: Path, command: str = "prepare"):
        """
        Initialize pre-flight validator.

        Args:
            config: Application configuration
            data_dir: Data directory path
            command: Command being executed ('prepare', 'scrape', 'retry', etc.)
        """
        self.config = config
        self.data_dir = data_dir
        self.command = command
        self.console = Console()
        self.checks: list[PreflightCheck] = []

    def run_all_checks(self) -> bool:
        """
        Run all pre-flight checks.

        Returns:
            True if all critical checks pass, False otherwise
        """
        self.checks = []

        # Run checks based on command
        if self.command in ["prepare", "retry"]:
            self._check_llm_availability()
            self._check_disk_space()
            self._check_battery_level()
            self._check_database_size()
            self._check_data_dir_writable()
            self._check_config_valid()

        if self.command == "scrape":
            self._check_repos_txt()
            self._check_disk_space()
            self._check_data_dir_writable()

        if self.command == "export":
            self._check_database_exists()
            self._check_database_size()
            self._check_disk_space()

        # Display results
        self._display_results()

        # Check if any critical failures
        critical_failures = [c for c in self.checks if c.status == "fail" and c.severity == "error"]

        return len(critical_failures) == 0

    def _check_llm_availability(self):
        """Check if LLM backend is available."""
        check = PreflightCheck(name="LLM Backend", severity="error")

        if self.config.model.use_mlx:
            # Check MLX availability
            from src.llm.mlx_utils import is_mlx_available

            if is_mlx_available():
                check.status = "pass"
                check.message = "MLX library is installed and available"
            else:
                check.status = "fail"
                check.message = "MLX library not found. Please install with 'pip install mlx'"
        else:
            # Check llama.cpp server connectivity
            try:
                # Use a shorter timeout for health checks (configured timeout / 2, minimum 5 seconds)
                # Handle case where config attribute might be mocked
                try:
                    configured_timeout = self.config.model.llm.request_timeout
                    health_check_timeout = max(5.0, configured_timeout / 2)
                except (AttributeError, TypeError):
                    # Fallback to default timeout if config attribute is not available (e.g. in tests)
                    health_check_timeout = 5.0
                timeout = httpx.Timeout(health_check_timeout, connect=10.0)
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(f"{self.config.model.llm.base_url}/health")
                    if response.status_code == 200:
                        check.status = "pass"
                        check.message = f"Server reachable at {self.config.model.llm.base_url}"
                    else:
                        check.status = "fail"
                        check.message = f"Server returned status {response.status_code}"
            except httpx.ConnectError:
                check.status = "fail"
                check.message = f"Cannot connect to {self.config.model.llm.base_url}. Is llama.cpp server running?"
            except Exception as e:
                check.status = "fail"
                check.message = f"Error checking LLM server: {str(e)}"

        self.checks.append(check)

    def _check_disk_space(self, min_gb: float = 1.0):
        """
        Check available disk space.

        Args:
            min_gb: Minimum required disk space in GB
        """
        check = PreflightCheck(name="Disk Space", severity="warning")

        try:
            stat = shutil.disk_usage(self.data_dir.parent if self.data_dir.exists() else Path.cwd())
            free_gb = stat.free / (1024**3)

            if free_gb >= min_gb:
                check.status = "pass"
                check.message = f"{free_gb:.2f} GB available"
            else:
                check.status = "warning"
                check.message = f"Only {free_gb:.2f} GB free (recommended: ≥{min_gb} GB)"
                check.severity = "warning"

        except Exception as e:
            check.status = "warning"
            check.message = f"Could not check disk space: {str(e)}"
            check.severity = "warning"

        self.checks.append(check)

    def _check_battery_level(self):
        """Check battery level on macOS."""
        if sys.platform != "darwin":
            return  # Skip on non-macOS

        check = PreflightCheck(name="Battery Level", severity="warning")

        battery = get_battery_status()
        if battery is None:
            check.status = "pass"
            check.message = "Battery status unavailable (desktop or non-macOS)"
        else:
            percent = battery.get("percent", 100)
            plugged = battery.get("plugged", True)

            if plugged:
                check.status = "pass"
                check.message = f"{percent}% (charging)"
            elif percent >= self.config.model.battery.low_threshold:
                check.status = "pass"
                check.message = f"{percent}% (sufficient)"
            else:
                check.status = "warning"
                check.message = (
                    f"{percent}% (below {self.config.model.battery.low_threshold}% threshold, will pause during processing)"
                )

        self.checks.append(check)

    def _check_database_size(self):
        """Check database file size."""
        check = PreflightCheck(name="Database Size", severity="info")

        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        db_path = self.data_dir / "pipeline.db"

        if not db_path.exists():
            check.status = "pass"
            check.message = "Database will be created"
        else:
            try:
                size_bytes = db_path.stat().st_size
                size_mb = size_bytes / (1024**2)

                if size_mb < 100:
                    check.status = "pass"
                    check.message = f"{size_mb:.2f} MB"
                elif size_mb < 500:
                    check.status = "pass"
                    check.message = f"{size_mb:.2f} MB (moderate size)"
                else:
                    check.status = "warning"
                    check.message = f"{size_mb:.2f} MB (large database, consider archiving)"
                    check.severity = "warning"

            except Exception as e:
                check.status = "warning"
                check.message = f"Could not check size: {str(e)}"
                check.severity = "warning"

        self.checks.append(check)

    def _check_database_exists(self):
        """Check if database exists (for export command)."""
        check = PreflightCheck(name="Database Exists", severity="error")

        # Compute db_path as data_dir / "pipeline.db" based on the original config logic
        db_path = self.data_dir / "pipeline.db"

        if db_path.exists():
            check.status = "pass"
            check.message = f"Found at {db_path}"
        else:
            check.status = "fail"
            check.message = "Database not found. Run 'prepare' first to generate data."

        self.checks.append(check)

    def _check_data_dir_writable(self):
        """Check if data directory is writable."""
        check = PreflightCheck(name="Data Directory", severity="error")

        try:
            # Create directory if it doesn't exist
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Test write permission
            test_file = self.data_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()

            check.status = "pass"
            check.message = f"Writable at {self.data_dir}"

        except PermissionError:
            check.status = "fail"
            check.message = f"No write permission for {self.data_dir}"
        except Exception as e:
            check.status = "fail"
            check.message = f"Error accessing directory: {str(e)}"

        self.checks.append(check)

    def _check_repos_txt(self):
        """Check if repos.txt exists and is valid."""
        check = PreflightCheck(name="repos.txt", severity="error")

        repos_file = Path(self.config.model.base_dir) / "repos.txt"

        if not repos_file.exists():
            check.status = "fail"
            check.message = "File not found. Create repos.txt with repository URLs."
        else:
            try:
                with open(repos_file, encoding="utf-8", errors="replace") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

                if len(lines) == 0:
                    check.status = "fail"
                    check.message = "File is empty. Add repository URLs."
                else:
                    check.status = "pass"
                    check.message = f"Found {len(lines)} repositor{'y' if len(lines) == 1 else 'ies'}"

            except Exception as e:
                check.status = "fail"
                check.message = f"Error reading file: {str(e)}"

        self.checks.append(check)

    def _check_config_valid(self):
        """Check if configuration is valid."""
        check = PreflightCheck(name="Configuration", severity="warning")

        if hasattr(self.config, "config_loader"):
            is_valid, errors = self.config.config_loader.validate()

            if is_valid:
                check.status = "pass"
                check.message = "Configuration is valid"
            else:
                check.status = "warning"
                check.message = f"{len(errors)} validation error(s): {errors[0]}"
                check.severity = "warning"
        else:
            check.status = "pass"
            check.message = "Using default configuration"

        self.checks.append(check)

    def _display_results(self):
        """Display pre-flight check results."""
        # Create results table
        table = Table(
            title="[bold cyan]Pre-Flight Checks[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Check", style="cyan", width=20)
        table.add_column("Status", width=10)
        table.add_column("Details", style="dim")

        for check in self.checks:
            # Determine status icon and color
            if check.status == "pass":
                status_text = "[green]✓ PASS[/green]"
            elif check.status == "warning":
                status_text = "[yellow]⚠ WARN[/yellow]"
            elif check.status == "fail":
                status_text = "[red]✗ FAIL[/red]"
            else:
                status_text = "[dim]⋯ PEND[/dim]"

            table.add_row(check.name, status_text, check.message)

        self.console.print(table)

        # Summary
        passed = sum(1 for c in self.checks if c.status == "pass")
        warnings = sum(1 for c in self.checks if c.status == "warning")
        failed = sum(1 for c in self.checks if c.status == "fail")

        summary = Text()
        summary.append("\nSummary: ")
        summary.append(f"{passed} passed", style="green")
        summary.append(", ")
        summary.append(f"{warnings} warnings", style="yellow" if warnings > 0 else "dim")
        summary.append(", ")
        summary.append(f"{failed} failed", style="red" if failed > 0 else "dim")

        self.console.print(summary)

        # Display errors if any
        critical_failures = [c for c in self.checks if c.status == "fail" and c.severity == "error"]

        if critical_failures:
            self.console.print("\n[bold red]Critical issues detected:[/bold red]")
            for check in critical_failures:
                self.console.print(f"  • {check.name}: {check.message}")

            self.console.print("\n[yellow]Pipeline cannot start until critical issues are resolved.[/yellow]")
        elif warnings > 0:
            self.console.print("\n[yellow]Warnings detected but pipeline can proceed.[/yellow]")
        else:
            self.console.print("\n[green]All checks passed! Pipeline ready to run.[/green]")


def run_preflight_checks(config: AppConfig, data_dir: Path, command: str = "prepare") -> bool:
    """
    Run pre-flight validation checks.

    Args:
        config: Application configuration
        data_dir: Data directory path
        command: Command being executed

    Returns:
        True if all critical checks pass, False otherwise
    """
    validator = PreflightValidator(config, data_dir, command)
    return validator.run_all_checks()
