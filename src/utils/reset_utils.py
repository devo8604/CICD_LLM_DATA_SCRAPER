"""Reset utility functions for the LLM Data Pipeline."""

import logging
import shutil
from pathlib import Path

from src.utils.disk_cleanup import DiskCleanupManager


def reset_database(db_path: str | Path) -> bool:
    """
    Reset the database by deleting the database file.

    Args:
        db_path: Path to the database file

    Returns:
        True if reset was successful, False otherwise
    """
    db_path = Path(db_path)

    if db_path.exists():
        try:
            db_path.unlink()
            logging.info(f"✅ Database deleted: {db_path}")
            return True
        except Exception as e:
            logging.error(f"❌ Error deleting database {db_path}: {e}")
            return False
    else:
        logging.info(f"ℹ️  Database does not exist: {db_path}")
        return True  # Not an error if file doesn't exist


def reset_logs(logs_dir: str | Path) -> bool:
    """
    Reset all log files in the logs directory.

    Args:
        logs_dir: Path to the logs directory

    Returns:
        True if reset was successful, False otherwise
    """
    logs_dir = Path(logs_dir)

    if not logs_dir.exists():
        logging.info(f"ℹ️  Logs directory does not exist: {logs_dir}")
        return True  # Not an error if directory doesn't exist

    success = True
    log_files = list(logs_dir.glob("*.txt")) + list(logs_dir.glob("*.log"))

    if not log_files:
        logging.info(f"ℹ️  No log files found in: {logs_dir}")
        return True

    for log_file in log_files:
        try:
            log_file.unlink()
            logging.info(f"✅ Log file deleted: {log_file}")
        except Exception as e:
            logging.error(f"❌ Error deleting log file {log_file}: {e}")
            success = False

    return success


def reset_repos(repos_dir: str | Path) -> bool:
    """
    Reset all cloned repositories by deleting the repos directory.

    Args:
        repos_dir: Path to the repos directory

    Returns:
        True if reset was successful, False otherwise
    """
    repos_dir = Path(repos_dir)

    if repos_dir.exists():
        try:
            shutil.rmtree(repos_dir)
            logging.info(f"✅ Repos directory deleted: {repos_dir}")
            return True
        except Exception as e:
            logging.error(f"❌ Error deleting repos directory {repos_dir}: {e}")
            return False
    else:
        logging.info(f"ℹ️  Repos directory does not exist: {repos_dir}")
        return True  # Not an error if directory doesn't exist


def reset_all(db_path: str | Path, logs_dir: str | Path, repos_dir: str | Path) -> bool:
    """
    Reset everything (database, logs, repos).

    Args:
        db_path: Path to the database file
        logs_dir: Path to the logs directory
        repos_dir: Path to the repos directory

    Returns:
        True if all resets were successful, False otherwise
    """
    logging.warning("⚠️  Resetting all pipeline data (database, logs, repos)...")

    success_db = reset_database(db_path)
    success_logs = reset_logs(logs_dir)
    success_repos = reset_repos(repos_dir)

    if success_db and success_logs and success_repos:
        logging.info("✅ All pipeline data reset successfully!")
        return True
    else:
        logging.error("❌ Some errors occurred during reset.")
        return False


def cleanup_disk(config) -> dict:
    """
    Perform automatic disk cleanup based on configuration.

    Args:
        config: Application configuration

    Returns:
        Dictionary with cleanup statistics
    """
    cleanup_manager = DiskCleanupManager(config)
    return cleanup_manager.force_cleanup()


def handle_reset_command(args, config) -> int:
    """
    Handle reset command with subcommands.

    Args:
        args: Parsed command line arguments
        config: Application configuration

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Determine the data directory
    data_dir = Path.cwd() / (args.data_dir if hasattr(args, "data_dir") else config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Determine the database path
    db_path = data_dir / "pipeline.db"

    # Determine logs directory
    logs_dir = Path("logs")

    # Determine repos directory
    repos_dir = Path("repos")

    reset_command = getattr(args, "reset_command", None)

    if reset_command == "db":
        logging.warning("⚠️  Resetting database...")
        success = reset_database(db_path)
        return 0 if success else 1
    elif reset_command == "logs":
        logging.warning("⚠️  Resetting logs...")
        success = reset_logs(logs_dir)
        return 0 if success else 1
    elif reset_command == "repos":
        logging.warning("⚠️  Resetting repositories...")
        success = reset_repos(repos_dir)
        return 0 if success else 1
    elif reset_command == "all":
        success = reset_all(db_path, logs_dir, repos_dir)
        return 0 if success else 1
    elif reset_command == "cleanup":
        stats = cleanup_disk(config)
        logging.info(f"Disk cleanup completed: {stats}")
        return 0
    else:
        logging.error("❌ Invalid reset command. Use 'db', 'logs', 'repos', 'all', or 'cleanup'.")
        return 1
