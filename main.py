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
from src.pipeline_factory import PipelineFactory


def main() -> None:
    """Main entry point for the LLM Data Pipeline."""
    # Load configuration
    config = AppConfig()

    # Parse command-line arguments
    args = parse_arguments()

    # Setup logging
    logs_dir = Path.cwd() / "logs"
    log_manager = LogManager(logs_dir, config)
    log_manager.cleanup_old_logs(
        args.max_log_files if hasattr(args, "max_log_files") else config.MAX_LOG_FILES
    )
    log_file_path = log_manager.create_log_file()

    if args.command == "scrape":
        configure_scrape_logging(log_file_path)
    elif args.command in ["prepare", "retry", "export"]:
        configure_tqdm_logging(log_file_path)

    # Create data directory
    data_dir = Path.cwd() / (
        args.data_dir if hasattr(args, "data_dir") else config.DATA_DIR
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    # Execute command
    try:
        if args.command in ["scrape", "prepare", "retry", "export"]:
            # Initialize pipeline using factory only for pipeline commands
            factory = PipelineFactory(config)
            repos_dir = str(Path(config.BASE_DIR) / config.REPOS_DIR_NAME)

            # Use lazy LLM initialization for scrape and export (they don't need LLM)
            lazy_llm = args.command in ["scrape", "export"]

            pipeline = factory.create_data_pipeline(
                data_dir=data_dir,
                repos_dir=repos_dir,
                max_tokens=getattr(args, "max_tokens", config.DEFAULT_MAX_TOKENS),
                temperature=getattr(args, "temperature", config.DEFAULT_TEMPERATURE),
                lazy_llm=lazy_llm,
            )

            if args.command == "scrape":
                asyncio.run(pipeline.scrape())
            elif args.command == "prepare":
                asyncio.run(pipeline.prepare())
            elif args.command == "retry":
                asyncio.run(pipeline.retry_failed_files())
            elif args.command == "export":
                pipeline.export_data(
                    getattr(args, "template", "alpaca-jsonl"),
                    getattr(args, "output_file", "output.jsonl"),
                )

            pipeline.close()  # Close the pipeline after use
        elif args.command == "mlx":
            # Handle MLX management commands (no pipeline needed)
            from src.mlx_manager import MLXModelManager

            manager = MLXModelManager(config)

            if args.mlx_command == "list":
                models = manager.list_local_models()
                if models:
                    print(f"Found {len(models)} locally cached MLX model(s):\n")
                    for i, model in enumerate(models, 1):
                        print(f"{i:2d}. {model['name']}")
                        print(f"    Path: {model['path']}")
                        print(f"    Size: {model['size']}")
                        print()
                else:
                    print("No locally cached MLX models found.")
            elif args.mlx_command == "download":
                manager.download_model(args.model_name)
            elif args.mlx_command == "remove":
                manager.remove_model(args.model_name)
            elif args.mlx_command == "info":
                info = manager.get_model_info(args.model_name)
                if info:
                    print(f"Model: {info['name']}")
                    print(f"Cached: {'Yes' if info.get('cached', False) else 'No'}")
                    if info.get("path"):
                        print(f"Path: {info['path']}")
                    if info.get("size"):
                        print(f"Size: {info['size']}")
                    if info.get("file_count"):
                        print(f"Number of files: {info['file_count']}")
                else:
                    print(f"Could not get information for model: {args.model_name}")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting gracefully...")
        sys.exit(0)


if __name__ == "__main__":
    main()
