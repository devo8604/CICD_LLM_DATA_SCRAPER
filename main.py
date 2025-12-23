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

# Add src directory to Python path to ensure imports work correctly
# This is necessary to run main.py directly from the project root
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import structlog  # noqa: E402

from src.core.config import AppConfig  # noqa: E402
from src.llm.mlx_manager import handle_mlx_command  # noqa: E402
from src.pipeline.cli import parse_arguments  # noqa: E402
from src.pipeline.di_container import setup_container  # noqa: E402
from src.pipeline.orchestration_service import OrchestrationService  # noqa: E402
from src.pipeline.preflight import run_preflight_checks  # noqa: E402
from src.pipeline.quickstart import run_quickstart_wizard  # noqa: E402
from src.pipeline.realtime_status import show_realtime_status  # noqa: E402
from src.ui.pipeline_tui import PipelineTUIApp  # noqa: E402
from src.utils.patches import apply_patches  # noqa: E402
from src.utils.reset_utils import reset_all, reset_database, reset_logs, reset_repos  # noqa: E402
from src.utils.status_utils import show_stats, show_status  # noqa: E402


def _run_preflight_check(args, config: AppConfig, command: str) -> None:
    """Run preflight check if not skipped."""
    if hasattr(args, "skip_preflight") and not args.skip_preflight:
        run_preflight_checks(config, Path(args.data_dir), command)


def _handle_reset_command(args, config: AppConfig) -> None:
    """Handle reset command."""
    # Compute paths from config.model.* instead of uppercase properties
    data_dir = Path(config.model.pipeline.base_dir) / config.model.pipeline.data_dir
    db_path = data_dir / "pipeline.db"
    logs_dir = Path(config.model.logging.log_file_prefix).parent if "/" in config.model.logging.log_file_prefix else Path("logs")
    repos_dir = data_dir / config.model.pipeline.repos_dir_name

    if args.reset_command == "db":
        reset_database(str(db_path))
    elif args.reset_command == "logs":
        reset_logs(str(logs_dir))
    elif args.reset_command == "repos":
        reset_repos(str(repos_dir))
    elif args.reset_command == "all":
        reset_all(str(db_path), str(logs_dir), str(repos_dir))
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
