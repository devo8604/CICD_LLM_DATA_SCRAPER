#!/usr/bin/env python3.14

"""LLM Data Pipeline - Main entry point."""

import asyncio
import os
import sys
from pathlib import Path

from src.config import AppConfig
from src.cli import parse_arguments
from src.log_manager import LogManager
from src.logging_config import configure_scrape_logging, configure_tqdm_logging
from src.data_pipeline import DataPipeline
from src.llm_client import LLMClient
from src.db_manager import DBManager
from src.file_manager import FileManager


def main() -> None:
    """Main entry point for the LLM Data Pipeline."""
    # Load configuration
    config = AppConfig()

    # Parse command-line arguments
    args = parse_arguments()

    # Setup logging
    logs_dir = Path.cwd() / "logs"
    log_manager = LogManager(logs_dir, config)
    log_manager.cleanup_old_logs(args.max_log_files)
    log_file_path = log_manager.create_log_file()
    
    if args.command == "scrape":
        configure_scrape_logging(log_file_path)
    elif args.command == "prepare":
        configure_tqdm_logging(log_file_path)
    elif args.command == "retry":
        configure_tqdm_logging(log_file_path)

    # Create data directory
    data_dir = Path.cwd() / args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize dependencies
    llm_client = LLMClient(
        base_url=config.LLM_BASE_URL,
        model_name=config.LLM_MODEL_NAME,
        max_retries=config.LLM_MAX_RETRIES,
        retry_delay=config.LLM_RETRY_DELAY,
    )
    db_manager = DBManager(data_dir / config.DB_PATH)
    file_manager = FileManager(
        repos_dir=str(Path(config.BASE_DIR) / config.REPOS_DIR_NAME),
        max_file_size=args.max_file_size,
    )

    # Create pipeline
    pipeline = DataPipeline(
        llm_client=llm_client,
        db_manager=db_manager,
        file_manager=file_manager,
        base_dir=config.BASE_DIR,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        data_dir=args.data_dir,
    )

    # Execute command
    try:
        if args.command == "scrape":
            asyncio.run(pipeline.scrape())
        elif args.command == "prepare":
            asyncio.run(pipeline.prepare())
        elif args.command == "retry":
            asyncio.run(pipeline.retry_failed_files())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting gracefully...")
        sys.exit(0)
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
