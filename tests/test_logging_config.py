import logging
from unittest.mock import MagicMock, patch

import pytest

from src.core.logging_config import (
    LoggingSetupError,
    LogLevel,
    TqdmLoggingHandler,
    add_file_handler,
    configure_scrape_logging,
    configure_tqdm_logging,
    get_logger,
    log_exception,
    setup_logging,
)


class TestLoggingConfig:
    def test_log_level_enum(self):
        assert LogLevel.DEBUG.value == logging.DEBUG
        assert LogLevel.INFO.value == logging.INFO
        assert LogLevel.WARNING.value == logging.WARNING
        assert LogLevel.ERROR.value == logging.ERROR
        assert LogLevel.CRITICAL.value == logging.CRITICAL

    def test_tqdm_logging_handler(self):
        handler = TqdmLoggingHandler()
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "msg", (), None)

        with patch("src.core.logging_config.tqdm") as mock_tqdm:
            handler.emit(record)
            mock_tqdm.write.assert_called()

    def test_tqdm_logging_handler_error(self):
        handler = TqdmLoggingHandler()
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "msg", (), None)

        with patch("src.core.logging_config.tqdm") as mock_tqdm:
            mock_tqdm.write.side_effect = Exception("Error")
            with patch.object(handler, "handleError") as mock_handle_error:
                handler.emit(record)
                mock_handle_error.assert_called_with(record)

    def test_setup_logging(self):
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_root.handlers = []
            mock_get_logger.return_value = mock_root

            setup_logging()

            mock_root.setLevel.assert_called_with(logging.DEBUG)
            mock_root.addHandler.assert_called()

    def test_configure_scrape_logging(self):
        with (
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.handlers.RotatingFileHandler") as mock_file_handler,
        ):
            mock_root = MagicMock()
            mock_root.handlers = [MagicMock()]
            # Multiple calls to getLogger during configure_scrape_logging and setup_logging
            mock_get_logger.return_value = mock_root

            configure_scrape_logging("test.log")

            mock_root.removeHandler.assert_called()
            assert mock_root.addHandler.call_count >= 2
            mock_file_handler.assert_called()

    def test_configure_scrape_logging_error(self):
        with patch("logging.getLogger", side_effect=Exception("Setup failed")):
            with pytest.raises(LoggingSetupError):
                configure_scrape_logging("test.log")

    def test_configure_tqdm_logging(self):
        with (
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.handlers.RotatingFileHandler"),
        ):
            mock_root = MagicMock()
            mock_tqdm_logger = MagicMock()

            # Multiple calls to getLogger: configure_tqdm_logging (root, tqdm_logger), then setup_logging (root)
            mock_get_logger.side_effect = [mock_root, mock_tqdm_logger, mock_root]

            configure_tqdm_logging("test.log")

            mock_root.addHandler.assert_called()
            mock_tqdm_logger.addHandler.assert_called()

    def test_get_logger_defaults(self):
        with patch("structlog.get_logger") as mock_get_logger:
            _ = get_logger("test_logger")
            mock_get_logger.assert_called_with("test_logger")

    def test_log_exception(self):
        logger = MagicMock()
        log_exception(logger, "context")
        logger.error.assert_called_once()
        args, kwargs = logger.error.call_args
        assert "Exception in context" in args[0]
        assert kwargs.get("exc_info") is True

    def test_add_file_handler(self):
        logger = MagicMock()
        with patch("logging.handlers.RotatingFileHandler"):
            add_file_handler(logger, "test.log")
            logger.addHandler.assert_called()

    def test_add_file_handler_error(self):
        logger = MagicMock()
        with patch("logging.handlers.RotatingFileHandler", side_effect=Exception("Error")):
            with pytest.raises(LoggingSetupError):
                add_file_handler(logger, "test.log")