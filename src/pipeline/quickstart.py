"""Interactive quickstart wizard for first-time setup."""

import os
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.core.config import AppConfig
from src.llm.mlx_utils import is_mlx_available


class QuickstartWizard:
    """Interactive setup wizard for new users."""

    def __init__(self, config: AppConfig | None = None):
        """Initialize the quickstart wizard."""
        self.console = Console()
        self.base_dir = Path.cwd()
        self.config_file = self.base_dir / ".cicdllm.yaml"
        self.repos_file = self.base_dir / "repos.txt"
        self.config = config if config else AppConfig()

    def run(self) -> None:
        """Run the interactive quickstart wizard."""
        self._show_welcome()

        # Step 1: Setup repos.txt
        if not self._setup_repos_file():
            return

        # Step 2: Setup configuration
        if not self._setup_config():
            return

        # Step 3: Test connectivity
        self._test_connectivity()

        # Step 4: Next steps
        self._show_next_steps()

    def _show_welcome(self) -> None:
        """Show welcome message."""
        welcome_text = """
# Welcome to LLM Data Pipeline!

This wizard will help you set up the pipeline in a few simple steps:

1. **Repository Configuration** - Specify Git repositories to process
2. **LLM Backend Setup** - Configure your LLM backend (llama.cpp or MLX)
3. **Connectivity Test** - Verify everything is working
4. **Next Steps** - Learn what to do next

Let's get started!
"""
        self.console.print(Panel(Markdown(welcome_text), title="Quickstart Wizard", border_style="cyan"))

    def _setup_repos_file(self) -> bool:
        """
        Setup repos.txt file.

        Returns:
            True if successful, False to exit wizard
        """
        self.console.print("\n[bold cyan]Step 1: Repository Configuration[/bold cyan]\n")

        if self.repos_file.exists():
            self.console.print(f"[green]✓[/green] Found existing {self.repos_file.name}")

            # Read existing repos
            with open(self.repos_file, encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

            if lines:
                self.console.print(f"  Contains {len(lines)} repository URL(s)")
                if Confirm.ask("  View repositories?", default=False):
                    for i, repo in enumerate(lines, 1):
                        self.console.print(f"  {i}. {repo}")

            if not Confirm.ask("  Add more repositories?", default=False):
                return True
        else:
            self.console.print(f"[yellow]![/yellow] No {self.repos_file.name} found")
            if not Confirm.ask("  Create repos.txt now?", default=True):
                self.console.print("\n[yellow]Cannot proceed without repos.txt. Exiting.[/yellow]")
                return False

        # Collect repositories
        repos = []
        self.console.print("\n[dim]Enter repository URLs (one at a time). Press Enter with empty input when done.[/dim]")

        while True:
            repo_url = Prompt.ask(
                f"  Repository URL #{len(repos) + 1} (or press Enter to finish)",
                default="",
            )

            if not repo_url:
                break

            # Basic validation
            if not (repo_url.startswith("http://") or repo_url.startswith("https://")):
                self.console.print("  [red]Invalid URL. Must start with http:// or https://[/red]")
                continue

            repos.append(repo_url)
            self.console.print("  [green]✓[/green] Added")

        if not repos and not self.repos_file.exists():
            self.console.print("\n[yellow]No repositories added. Cannot proceed.[/yellow]")
            return False

        # Write to file
        if repos:
            mode = "a" if self.repos_file.exists() else "w"
            with open(self.repos_file, mode, encoding="utf-8") as f:
                if mode == "a":
                    f.write("\n")
                for repo in repos:
                    f.write(f"{repo}\n")

            self.console.print(f"\n[green]✓[/green] Added {len(repos)} repository/ies to {self.repos_file.name}")

        return True

    def _setup_config(self) -> bool:
        """
        Setup configuration file.

        Returns:
            True if successful, False to exit wizard
        """
        self.console.print("\n[bold cyan]Step 2: LLM Backend Configuration[/bold cyan]\n")

        if self.config_file.exists():
            self.console.print(f"[green]✓[/green] Found existing {self.config_file.name}")
            if not Confirm.ask("  Reconfigure LLM backend?", default=False):
                # Load existing config
                self.config = AppConfig()
                return True
        else:
            self.console.print("[yellow]![/yellow] No configuration file found")

        return self._configure_llm()

    def _configure_llm(self) -> bool:
        """
        Configure LLM backend (llama.cpp or MLX).
        Used by tests.
        """
        # Detect platform
        is_apple_silicon = sys.platform == "darwin" and os.uname().machine == "arm64"

        # Show backend options
        table = Table(title="Available LLM Backends")
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Backend", style="green", width=15)
        table.add_column("Description", style="dim")
        table.add_column("Requirements", style="yellow")

        table.add_row("1", "llama.cpp", "OpenAI-compatible server", "llama-server running locally")
        table.add_row("2", "MLX", "Apple Silicon acceleration", "M1/M2/M3 Mac + mlx-lm installed")

        self.console.print(table)

        # Recommend based on platform
        if is_apple_silicon:
            self.console.print("\n[dim]Recommendation: MLX for native Apple Silicon acceleration[/dim]")
            default_choice = "2"
        else:
            self.console.print("\n[dim]Recommendation: llama.cpp for broad compatibility[/dim]")
            default_choice = "1"

        # Get user choice
        backend_choice = Prompt.ask("\nSelect backend", choices=["1", "2", "llama_cpp", "mlx"], default=default_choice)

        if backend_choice in ["1", "llama_cpp"]:
            return self._configure_llamacpp()
        else:
            return self._configure_mlx()

    def _configure_llamacpp(self) -> bool:
        """
        Configure llama.cpp backend.

        Returns:
            True if successful, False to exit
        """
        self.console.print("\n[bold]Configuring llama.cpp backend[/bold]\n")

        # Get server URL
        base_url = Prompt.ask("Server URL", default="http://localhost:11454")

        # Get model name (optional)
        model_name = Prompt.ask("Model name (optional, press Enter to skip)", default="")

        # Create config
        config_content = f"""# LLM Data Pipeline Configuration
# Generated by quickstart wizard

llm:
  backend: llama_cpp
  base_url: {base_url}
"""

        if model_name:
            config_content += f"  model_name: {model_name}\n"

        # Write config
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        self.console.print(f"\n[green]✓[/green] Configuration saved to {self.config_file.name}")

        # Update config in memory if possible
        if hasattr(self.config, "model"):
            self.config.model.llm.backend = "llama_cpp"
            self.config.model.llm.base_url = base_url
            if model_name:
                self.config.model.llm.model_name = model_name

        # Also update top-level properties for tests/backward compatibility
        self.config.LLM_BASE_URL = base_url
        if model_name:
            self.config.LLM_MODEL_NAME = model_name

        return True

    def _configure_mlx(self) -> bool:
        """
        Configure MLX backend.

        Returns:
            True if successful, False to exit
        """
        self.console.print("\n[bold]Configuring MLX backend[/bold]\n")

        # Check if MLX is installed
        if is_mlx_available():
            self.console.print("[green]✓[/green] MLX is installed")
        else:
            self.console.print("[red]✗[/red] MLX is NOT installed")
            if not Confirm.ask("  Continue anyway?", default=False):
                return False

        # Suggest models based on typical RAM
        self.console.print("\n[bold]Recommended Models by RAM:[/bold]")
        self.console.print("  8GB:  mlx-community/Qwen2.5-Coder-3B-Instruct-4bit")
        self.console.print("  16GB: mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")
        self.console.print("  32GB: mlx-community/Qwen2.5-Coder-14B-Instruct-4bit")
        self.console.print("  64GB: mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit\n")

        # Get model name
        model_name = Prompt.ask("MLX model name", default="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")

        # Get max RAM
        max_ram = IntPrompt.ask("Maximum RAM to use (GB)", default=16)

        # Create config
        config_content = f"""# LLM Data Pipeline Configuration
# Generated by quickstart wizard

llm:
  backend: mlx
  mlx_model_name: {model_name}
  mlx_max_ram_gb: {max_ram}
  mlx_quantize: true
"""

        # Write config
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        self.console.print(f"\n[green]✓[/green] Configuration saved to {self.config_file.name}")

        # Update config in memory if possible
        if hasattr(self.config, "model"):
            self.config.model.llm.backend = "mlx"
            self.config.model.mlx.model_name = model_name
            self.config.model.mlx.max_ram_gb = max_ram
            self.config.model.mlx.quantize = True
            self.config.model.use_mlx = True

        # Also update top-level properties for tests/backward compatibility
        self.config.MLX_MODEL_NAME = model_name
        self.config.MLX_MAX_RAM_GB = max_ram
        self.config.USE_MLX = True

        return True

    def _test_connectivity(self) -> None:
        """Test LLM backend connectivity."""
        self.console.print("\n[bold cyan]Step 3: Connectivity Test[/bold cyan]\n")

        if not self.config:
            self.config = AppConfig()

        if self.config.model.use_mlx:
            self._test_mlx()
        else:
            self._test_llamacpp()

    def _test_mlx(self) -> None:
        """Internal test MLX availability."""
        self.test_mlx()

    def test_mlx(self) -> None:
        """Test MLX availability."""
        if is_mlx_available():
            self.console.print("[green]✓[/green] MLX library is available")
        else:
            self.console.print("[red]✗[/red] MLX library is NOT available")

    def _test_llamacpp(self) -> None:
        """Internal test llama.cpp connectivity."""
        self.test_llamacpp()

    def test_llamacpp(self) -> None:
        """Test llama.cpp server connectivity."""
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
                    self.console.print("[green]✓[/green] llama.cpp server is reachable")
                    self.console.print(f"[dim]  URL: {self.config.model.llm.base_url}[/dim]")
                else:
                    self.console.print(f"[yellow]⚠[/yellow] Server returned status {response.status_code}")
        except httpx.ConnectError:
            self.console.print(f"[red]✗[/red] Cannot connect to {self.config.model.llm.base_url}")
            self.console.print("\n[yellow]Make sure llama.cpp server is running:[/yellow]")
            self.console.print("  llama-server -m path/to/model.gguf --port 11454")
        except Exception as e:
            self.console.print(f"[red]✗[/red] Error: {str(e)}")

    def _show_next_steps(self) -> None:
        """Show next steps to the user."""
        next_steps = """
# Setup Complete!

You're ready to start using the pipeline. Here are the recommended next steps:

## 1. Clone Repositories
```bash
python3 main.py scrape
```
This will clone all repositories listed in `repos.txt`.

## 2. Generate Q&A Pairs
```bash
python3 main.py prepare
```
This processes files and generates question-answer pairs using your LLM.

## 3. Check Status
```bash
python3 main.py status
```
View pipeline status at any time.

## 4. Export Training Data
```bash
python3 main.py export --template alpaca-jsonl --output-file training_data.jsonl
```
Export your Q&A pairs in various formats.

## Additional Commands

- `python3 main.py stats` - View detailed statistics
- `python3 main.py retry` - Retry failed files
- `python3 main.py config show` - View current configuration
- `python3 main.py --help` - See all available commands

## Need Help?

Check the README.md for detailed documentation, or visit:
https://github.com/yourusername/cicdllm

Happy training!
"""
        self.console.print(Panel(Markdown(next_steps), title="Next Steps", border_style="green"))


def run_quickstart_wizard() -> None:
    """Run the quickstart wizard."""
    wizard = QuickstartWizard()
    wizard.run()
