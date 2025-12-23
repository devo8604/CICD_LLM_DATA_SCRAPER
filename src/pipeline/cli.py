"""Command-line interface argument parsing."""

import argparse

from src.core.config import AppConfig


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the LLM Data Pipeline.

    Returns:
        Parsed arguments namespace
    """
    config = AppConfig()

    parser = argparse.ArgumentParser(
        description="LLM Data Pipeline for Git repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full workflow - from repositories to training data
  python3 main.py scrape                    # Clone/update repositories
  python3 main.py prepare                   # Generate Q&A pairs
  python3 main.py export --template alpaca-jsonl --output-file data.jsonl

  # Check what would be processed (dry-run mode)
  python3 main.py prepare --dry-run
  python3 main.py export --dry-run --template csv --output-file out.csv

  # Retry failed files from previous run
  python3 main.py retry

  # View pipeline status and statistics
  python3 main.py status                    # Quick status overview
  python3 main.py status-realtime           # Real-time status with live updates
  python3 main.py stats                     # Detailed statistics

  # Configuration management
  python3 main.py config show               # Show current configuration
  python3 main.py config set llm.base_url http://localhost:8080

  # MLX model management (Apple Silicon)
  python3 main.py mlx list                  # List cached models
  python3 main.py mlx download MODEL_NAME   # Download a model

  # Interactive modes
  python3 main.py quickstart                # Guided setup wizard
  python3 main.py tui                       # Launch Text User Interface dashboard
  python3 main.py export --interactive      # Interactive export

For more information, visit: https://github.com/yourusername/cicdllm
        """,
    )

    # Create a parent parser for common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--max-file-size",
        type=int,
        default=config.model.pipeline.max_file_size,
        help="Maximum size of a file (in bytes) to be processed. Files larger than this will be skipped.",
    )
    parent_parser.add_argument(
        "--data-dir",
        type=str,
        default=config.model.pipeline.data_dir,
        help="Directory to store state and QA data files.",
    )
    parent_parser.add_argument(
        "--max-log-files",
        type=int,
        default=config.model.logging.max_log_files,
        help="Maximum number of log files to retain. Oldest log files will be deleted to maintain this limit.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Clone/update repos.", parents=[parent_parser])
    scrape_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually cloning/updating repositories.",
    )
    scrape_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pre-flight validation checks.",
    )

    # Prepare command
    prepare_parser = subparsers.add_parser("prepare", help="Process files and generate Q&A.", parents=[parent_parser])
    prepare_parser.add_argument(
        "--max-tokens",
        type=int,
        default=config.model.generation.default_max_tokens,
        help="Maximum number of tokens for LLM generated answers.",
    )
    prepare_parser.add_argument(
        "--temperature",
        type=float,
        default=config.model.generation.default_temperature,
        help=("Sampling temperature for LLM generated questions. Lower values make output more deterministic, higher values make it more creative. (0.0 to 1.0)"),
    )
    prepare_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what files would be processed without actually processing them.",
    )
    prepare_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pre-flight validation checks.",
    )

    # Retry command
    retry_parser = subparsers.add_parser("retry", help="Re-process failed files.", parents=[parent_parser])
    retry_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what files would be retried without actually processing them.",
    )
    retry_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pre-flight validation checks.",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export Q&A data.", parents=[parent_parser])
    export_parser.add_argument(
        "--template",
        type=str,
        choices=[
            "csv",
            "llama3",
            "mistral",
            "gemma",
            "alpaca-jsonl",
            "chatml-jsonl",
        ],
        required=True,
        help="Desired output template for fine-tuning data.",
    )
    export_parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="Path to the output JSONL file.",
    )
    export_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pre-flight validation checks.",
    )

    # Status command
    subparsers.add_parser("status", help="Show pipeline status and overview.", parents=[parent_parser])

    # Real-time status command
    status_realtime_parser = subparsers.add_parser(
        "status-realtime",
        help="Show real-time pipeline status with live updates.",
        parents=[parent_parser],
    )
    status_realtime_parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in seconds to show real-time updates (default: 30). Use 0 for infinite.",
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show detailed pipeline statistics.", parents=[parent_parser])
    stats_parser.add_argument(
        "--format",
        type=str,
        choices=["table", "json"],
        default="table",
        help="Output format for statistics.",
    )

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage pipeline configuration.", parents=[parent_parser])
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    # Config show command
    config_show_parser = config_subparsers.add_parser("show", help="Show current configuration.")
    config_show_parser.add_argument(
        "--format",
        type=str,
        choices=["yaml", "json"],
        default="yaml",
        help="Output format for configuration.",
    )

    # Config set command
    config_set_parser = config_subparsers.add_parser("set", help="Set a configuration value.")
    config_set_parser.add_argument(
        "key",
        type=str,
        help="Configuration key in dot notation (e.g., llm.base_url)",
    )
    config_set_parser.add_argument(
        "value",
        type=str,
        help="Value to set",
    )

    # Config validate command
    config_subparsers.add_parser("validate", help="Validate current configuration.")

    # Config init command
    config_init_parser = config_subparsers.add_parser("init", help="Create a default configuration file.")
    config_init_parser.add_argument(
        "--path",
        type=str,
        default=".cicdllm.yaml",
        help="Path to create config file (default: .cicdllm.yaml)",
    )

    # MLX management command
    mlx_parser = subparsers.add_parser(
        "mlx",
        help="Manage MLX models (list, download, remove).",
        parents=[parent_parser],
    )
    mlx_subparsers = mlx_parser.add_subparsers(dest="mlx_command", required=True)

    # MLX list command
    mlx_list_parser = mlx_subparsers.add_parser("list", help="List locally cached MLX models.")
    mlx_list_parser.add_argument(
        "--all",
        action="store_true",
        help="Show all available models (not just locally cached ones).",
    )

    # MLX download command
    mlx_download_parser = mlx_subparsers.add_parser("download", help="Download an MLX model.")
    mlx_download_parser.add_argument(
        "model_name",
        type=str,
        help="Name of the MLX model to download (e.g., mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit).",
    )

    # MLX remove command
    mlx_remove_parser = mlx_subparsers.add_parser("remove", help="Remove a locally cached MLX model.")
    mlx_remove_parser.add_argument("model_name", type=str, help="Name of the MLX model to remove.")

    # MLX info command
    mlx_info_parser = mlx_subparsers.add_parser("info", help="Get information about an MLX model.")
    mlx_info_parser.add_argument("model_name", type=str, help="Name of the MLX model to get info for.")

    # Quickstart wizard command
    subparsers.add_parser(
        "quickstart",
        help="Interactive setup wizard for first-time users.",
        parents=[parent_parser],
    )

    # TUI command
    subparsers.add_parser("tui", help="Launch the Text User Interface dashboard.", parents=[parent_parser])

    # Reset command
    reset_parser = subparsers.add_parser(
        "reset",
        help="Reset pipeline data (database, logs, repos).",
        parents=[parent_parser],
    )
    reset_subparsers = reset_parser.add_subparsers(dest="reset_command", required=True)

    # Reset database command
    reset_subparsers.add_parser("db", help="Reset the database (delete pipeline.db).")

    # Reset logs command
    reset_subparsers.add_parser("logs", help="Reset all log files.")

    # Reset repos command
    reset_subparsers.add_parser("repos", help="Reset all cloned repositories.")

    # Reset all command
    reset_subparsers.add_parser("all", help="Reset everything (database, logs, repos).")

    # Disk cleanup command
    reset_subparsers.add_parser("cleanup", help="Perform automatic disk cleanup of temporary files.")

    return parser.parse_args()
