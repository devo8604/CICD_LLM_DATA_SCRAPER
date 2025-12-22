"""Enhanced logging configuration for the application."""

import logging
import logging.handlers
import sys
from enum import Enum
from pathlib import Path

import structlog
from tqdm import tqdm


class LogLevel(Enum):
    """Enumeration for log levels."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LoggingSetupError(Exception):
    """Custom exception for logging setup errors."""

    pass


class TqdmLoggingHandler(logging.Handler):
    """A logging handler that uses tqdm.write() to avoid interfering with progress bars."""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg, file=sys.stderr)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class TuiLoggingHandler(logging.Handler):
    """A logging handler that redirects logs to the TUI LogPanel."""

    def __init__(self, log_callback, level=logging.NOTSET):
        super().__init__(level)
        self.log_callback = log_callback

    def emit(self, record):
        try:
            msg = self.format(record)
            level_name = record.levelname.lower()
            # Map standard logging levels to TUI levels
            tui_level = "info"
            if level_name == "error" or level_name == "critical":
                tui_level = "error"
            elif level_name == "warning":
                tui_level = "warning"
            elif "success" in msg.lower():
                tui_level = "success"

            self.log_callback(msg, tui_level)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


def setup_logging():
    """Setup root logging configuration with better structure."""
    # Standard library logging configuration
    pre_chain = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        foreign_pre_chain=pre_chain,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler for general application logging
    from pathlib import Path
    import os
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Create a general application log file named after the application
    app_log_file = logs_dir / "application_main.log"  # Main application log

    file_handler = logging.handlers.RotatingFileHandler(
        str(app_log_file),
        mode="a",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Structlog configuration
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def configure_scrape_logging(log_file_path: str | Path) -> None:
    """
    Configure logging for the scrape command with a standard console handler.
    """
    try:
        # Create logs directory if it doesn't exist
        from pathlib import Path
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Ensure log_file_path is in the logs directory
        log_file_path = logs_dir / Path(log_file_path).name

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        pre_chain = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
        ]

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=pre_chain,
        )

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file_path),
            mode="a",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        setup_logging()  # Ensure structlog is configured
        logging.info(f"Scrape logging configured. Log file: {log_file_path}")
    except Exception as e:
        raise LoggingSetupError(f"Failed to configure scrape logging: {e}") from e


def configure_tqdm_logging(log_file_path: str | Path) -> None:
    """
    Configure a dedicated logger for use with tqdm progress bars.
    """
    try:
        # Create logs directory if it doesn't exist
        from pathlib import Path
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Ensure log_file_path is in the logs directory
        log_file_path = logs_dir / Path(log_file_path).name

        # Configure the root logger for file output
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        pre_chain = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
        ]

        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file_path),
            mode="a",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Configure the dedicated tqdm logger
        tqdm_logger = logging.getLogger("tqdm_logger")
        tqdm_logger.setLevel(logging.INFO)
        tqdm_logger.propagate = False  # Prevent messages from going to the root logger

        # Remove old handlers from tqdm_logger if any
        for handler in tqdm_logger.handlers[:]:
            tqdm_logger.removeHandler(handler)

        tqdm_formatter = logging.Formatter("%(message)s")  # Simple formatter for tqdm
        tqdm_handler = TqdmLoggingHandler(level=logging.INFO)
        tqdm_handler.setFormatter(tqdm_formatter)
        tqdm_logger.addHandler(tqdm_handler)

        setup_logging()  # Ensure structlog is configured
        logging.info(f"Tqdm logging configured. Log file: {log_file_path}")
    except Exception as e:
        raise LoggingSetupError(f"Failed to configure tqdm logging: {e}") from e


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured structlog logger instance."""
    return structlog.get_logger(name)


def log_exception(logger: structlog.BoundLogger, context: str = "", **kwargs):
    """Log the current exception with traceback."""
    logger.error(f"Exception in {context}", exc_info=True, **kwargs)


def add_file_handler(logger: logging.Logger, log_file_path: str | Path) -> logging.handlers.RotatingFileHandler:
    """Add a rotating file handler to an existing logger."""
    try:
        # Create logs directory if it doesn't exist
        from pathlib import Path
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Ensure log_file_path is in the logs directory
        log_file_path = logs_dir / Path(log_file_path).name

        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file_path),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return file_handler
    except Exception as e:
        raise LoggingSetupError(f"Failed to add file handler: {e}") from e