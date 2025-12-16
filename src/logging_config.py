import logging
import sys
from pathlib import Path
from tqdm import tqdm


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


def configure_scrape_logging(log_file_path: str | Path) -> None:
    """
    Configure logging for the scrape command with a standard console handler.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # File handler
    file_handler = logging.FileHandler(str(log_file_path), mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info(f"Scrape logging configured. Log file: {log_file_path}")


def configure_tqdm_logging(log_file_path: str | Path) -> None:
    """
    Configure a dedicated logger for use with tqdm progress bars.
    """
    # Configure the root logger for file output
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(str(log_file_path), mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Configure the dedicated tqdm logger
    tqdm_logger = logging.getLogger("tqdm_logger")
    tqdm_logger.setLevel(logging.INFO)
    tqdm_logger.propagate = False # Prevent messages from going to the root logger
    
    # Remove old handlers from tqdm_logger if any
    for handler in tqdm_logger.handlers[:]:
        tqdm_logger.removeHandler(handler)

    tqdm_formatter = logging.Formatter("%(message)s") # Simple formatter for tqdm
    tqdm_handler = TqdmLoggingHandler(level=logging.ERROR)
    tqdm_handler.setFormatter(tqdm_formatter)
    tqdm_logger.addHandler(tqdm_handler)
    
    logging.info(f"Tqdm logging configured. Log file: {log_file_path}")
