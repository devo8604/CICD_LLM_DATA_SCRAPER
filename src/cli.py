"""Command-line interface argument parsing."""

import argparse
from src.config import AppConfig


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the LLM Data Pipeline.

    Returns:
        Parsed arguments namespace
    """
    config = AppConfig()

    parser = argparse.ArgumentParser(
        description="LLM Data Pipeline for Git repositories."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Clone/update repos.")
    
    # Prepare command
    prepare_parser = subparsers.add_parser("prepare", help="Process files and generate Q&A.")
    prepare_parser.add_argument(
        "--max-tokens",
        type=int,
        default=config.DEFAULT_MAX_TOKENS,
        help="Maximum number of tokens for LLM generated answers.",
    )
    prepare_parser.add_argument(
        "--temperature",
        type=float,
        default=config.DEFAULT_TEMPERATURE,
        help="Sampling temperature for LLM generated questions. Lower values make output more deterministic, higher values make it more creative. (0.0 to 1.0)",
    )
    
    # Retry command
    retry_parser = subparsers.add_parser("retry", help="Re-process failed files.")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export Q&A data.")
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

    # Global arguments
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=config.MAX_FILE_SIZE,
        help="Maximum size of a file (in bytes) to be processed. Files larger than this will be skipped.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=config.DATA_DIR,
        help="Directory to store state and QA data files.",
    )
    parser.add_argument(
        "--max-log-files",
        type=int,
        default=config.MAX_LOG_FILES,
        help="Maximum number of log files to retain. Oldest log files will be deleted to maintain this limit.",
    )

    return parser.parse_args()
