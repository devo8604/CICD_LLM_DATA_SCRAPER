"""Configuration management utilities."""

import json
import shutil
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from src.core.config import AppConfig

console = Console()


def handle_config_command(config: AppConfig, args) -> None:
    """
    Handle config management subcommands.

    Args:
        config: Application configuration instance
        args: Parsed command line arguments
    """
    if args.config_command == "show":
        show_config(config, args.format)
    elif args.config_command == "set":
        set_config(config, args.key, args.value)
    elif args.config_command == "validate":
        validate_config(config)
    elif args.config_command == "init":
        init_config(args.path)


def show_config(config: AppConfig, output_format: str = "yaml") -> None:
    """
    Display current configuration.

    Args:
        config: Application configuration instance
        output_format: Output format ('yaml' or 'json')
    """
    # Get current configuration from the loader
    config_data = config.config_loader.config_data

    if not config_data:
        console.print("[yellow]No configuration file loaded. Using defaults.[/yellow]")
        console.print("\nTo create a configuration file:")
        console.print("  [cyan]python3 main.py config init[/cyan]")
        return

    if output_format == "json":
        output = json.dumps(config_data, indent=2)
        syntax = Syntax(output, "json", theme="monokai", line_numbers=False)
    else:  # yaml
        output = yaml.safe_dump(config_data, default_flow_style=False, sort_keys=False, indent=2)
        syntax = Syntax(output, "yaml", theme="monokai", line_numbers=False)

    # Find which config file is loaded
    loaded_from = "Unknown"
    for path in config.config_loader.config_paths:
        if path.exists():
            loaded_from = str(path)
            break

    panel = Panel(
        syntax,
        title="[bold cyan]Configuration[/bold cyan]",
        subtitle=f"[dim]Loaded from: {loaded_from}[/dim]",
        border_style="blue",
    )
    console.print(panel)


def set_config(config: AppConfig, key: str, value: str) -> None:
    """
    Set a configuration value.

    Args:
        config: Application configuration instance
        key: Configuration key in dot notation
        value: Value to set (will be auto-converted to appropriate type)
    """
    # Try to convert value to appropriate type
    converted_value = _convert_value(value)

    # Set the value
    config.config_loader.set(key, converted_value)

    # Find or create config file
    config_file = None
    for path in config.config_loader.config_paths:
        if path.exists():
            config_file = path
            break

    if not config_file:
        # Create default config file
        config_file = Path.cwd() / ".cicdllm.yaml"

    # Save configuration
    try:
        config.config_loader.save(config_file)
        console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [yellow]{converted_value}[/yellow]")
        console.print(f"[dim]Saved to: {config_file}[/dim]")
    except Exception as e:
        console.print(f"[red]Error saving configuration:[/red] {e}")


def _convert_value(value: str):
    """
    Convert string value to appropriate Python type.

    Args:
        value: String value to convert

    Returns:
        Converted value (int, float, bool, list, or str)
    """
    # Try boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try list (comma-separated)
    if "," in value:
        return [item.strip() for item in value.split(",")]

    # Return as string
    return value


def validate_config(config: AppConfig) -> None:
    """
    Validate current configuration.

    Args:
        config: Application configuration instance
    """
    is_valid, errors = config.config_loader.validate()

    if is_valid:
        console.print(
            Panel(
                "[green]✓ Configuration is valid[/green]",
                title="[bold green]Validation Passed[/bold green]",
                border_style="green",
            )
        )
    else:
        # Create error table
        table = Table(title="Configuration Errors", show_header=True, border_style="red")
        table.add_column("#", style="dim", width=4)
        table.add_column("Error", style="red")

        for i, error in enumerate(errors, 1):
            table.add_row(str(i), error)

        console.print(table)
        console.print(f"\n[red]✗ Found {len(errors)} error{'s' if len(errors) > 1 else ''}[/red]")


def init_config(path: str = ".cicdllm.yaml") -> None:
    """
    Create a default configuration file.

    Args:
        path: Path to create config file at
    """
    config_path = Path(path)

    # Check if file already exists
    if config_path.exists():
        console.print(f"[yellow]Configuration file already exists:[/yellow] {config_path}")
        console.print("Use [cyan]--path[/cyan] to specify a different location.")
        return

    # Copy example config
    example_config = Path(__file__).parent.parent / "config.example.yaml"

    if not example_config.exists():
        console.print("[red]Error:[/red] config.example.yaml not found")
        return

    try:
        shutil.copy(example_config, config_path)
        console.print(f"[green]✓[/green] Created configuration file: [cyan]{config_path}[/cyan]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Edit the config file to customize your settings")
        console.print("  2. View config: [cyan]python3 main.py config show[/cyan]")
        console.print("  3. Validate: [cyan]python3 main.py config validate[/cyan]")
    except Exception as e:
        console.print(f"[red]Error creating config file:[/red] {e}")
