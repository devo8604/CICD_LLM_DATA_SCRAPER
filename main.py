#!/usr/bin/env python3
"""
Main entry point for the LLM Data Pipeline.

This script provides a CLI interface for processing Git repositories
and generating training data for LLMs in various formats.
"""

import logging
import os
import sys
from pathlib import Path

import structlog

# Add src directory to Python path to ensure imports work correctly
# This is necessary to run main.py directly from the project root
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from src.core.config import AppConfig
from src.llm.mlx_manager import handle_mlx_command
from src.pipeline.cli import parse_arguments
from src.pipeline.di_container import setup_container
from src.pipeline.orchestration_service import OrchestrationService
from src.pipeline.preflight import run_preflight_checks
from src.pipeline.quickstart import run_quickstart_wizard
from src.pipeline.realtime_status import show_realtime_status
from src.ui.pipeline_tui import PipelineTUIApp
from src.utils.patches import apply_patches
from src.utils.reset_utils import reset_all, reset_database, reset_logs, reset_repos
from src.utils.status_utils import show_stats, show_status


def _run_preflight_check(args, config: AppConfig, command: str) -> None:
    """Run preflight check if not skipped."""
    if hasattr(args, "skip_preflight") and not args.skip_preflight:
        run_preflight_checks(config, Path(args.data_dir), command)


def _handle_reset_command(args, config: AppConfig) -> None:
    """Handle reset command."""
    if args.reset_command == "db":
        reset_database(config.DB_PATH)
    elif args.reset_command == "logs":
        reset_logs(config.LOG_FILE_PREFIX)
    elif args.reset_command == "repos":
        reset_repos(config.REPOS_DIR_NAME)
    elif args.reset_command == "all":
        reset_all(config.DB_PATH, config.LOG_FILE_PREFIX, config.REPOS_DIR_NAME)
    else:
        logging.error(f"Unknown reset command: {args.reset_command}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the LLM Data Pipeline."""
    # Apply runtime patches
    apply_patches()

    # Initialize logging system
    from src.core.logging_config import setup_logging
    setup_logging()
    
    logger = structlog.get_logger(__name__)
    logger.info("Application starting")

    args = parse_arguments()
    config = AppConfig()
    
    # Initialize dependency injection container
    container = setup_container(config)
    orchestrator = container.get(OrchestrationService)

    # Command routing
    if args.command == "scrape":
        _run_preflight_check(args, config, "scrape")
        if not args.dry_run:
            orchestrator.scrape()
        else:
            logging.info("Dry run: Skipping repository scraping.")

    elif args.command == "prepare":
        _run_preflight_check(args, config, "prepare")
        # Note: CLI prepare currently doesn't support the same fine-grained 
        # temperature/max_tokens as TUI via orchestrator directly without 
        # updating orchestrator/preparation service.
        # For now, we use orchestrator which uses config values.
        if not args.dry_run:
            orchestrator.prepare()
        else:
            logging.info("Dry run: Skipping file processing.")

    elif args.command == "retry":
        _run_preflight_check(args, config, "prepare")
        if not args.dry_run:
            orchestrator.retry()
        else:
            logging.info("Dry run: Skipping retry.")

    elif args.command == "export":
        _run_preflight_check(args, config, "export")
        orchestrator.export(template=args.template, output_file=args.output_file)

    elif args.command == "status":
        from src.data.db_manager import DBManager
        db_manager = container.get(DBManager)
        show_status(config, db_manager)

    elif args.command == "status-realtime":
        show_realtime_status(config, Path(args.data_dir), duration=args.duration)

    elif args.command == "stats":
        from src.data.db_manager import DBManager
        db_manager = container.get(DBManager)
        show_stats(config, db_manager, format_type=args.format)

    elif args.command == "config":
        from src.core.config_utils import handle_config_command
        handle_config_command(config, args)

    elif args.command == "mlx":
        handle_mlx_command(args)

    elif args.command == "quickstart":
        run_quickstart_wizard()

    elif args.command == "tui":
        _run_preflight_check(args, config, "prepare")
        app = PipelineTUIApp(config, Path(args.data_dir))
        app.run()
        # Use os._exit to immediately terminate, avoiding C++ runtime crashes
        os._exit(0)

    elif args.command == "reset":
        _handle_reset_command(args, config)

    else:
        logging.error(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()