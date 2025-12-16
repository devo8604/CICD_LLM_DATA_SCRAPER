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
    parser.add_argument(
        "command",
        choices=["scrape", "prepare", "retry"],
        help="Command to execute: 'scrape' to clone/update repos, 'prepare' to process files and generate Q&A, 'retry' to re-process failed files.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=config.DEFAULT_MAX_TOKENS,
        help="Maximum number of tokens for LLM generated answers.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=config.DEFAULT_TEMPERATURE,
        help="Sampling temperature for LLM generated questions. Lower values make output more deterministic, higher values make it more creative. (0.0 to 1.0)",
    )
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
