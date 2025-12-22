"""State management for pipeline progress tracking."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class StateManager:
    """Manages pipeline state persistence using SQLite with thread-safe connections."""

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize state manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._local = threading.local()
        self._initialize_database()

    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(str(self.db_path), timeout=30.0)
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")

        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise
        else:
            self._local.connection.commit()

    def _initialize_database(self) -> None:
        """Create pipeline_state table if it doesn't exist."""
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
        logger.debug("Ensured pipeline_state table exists")

    def get_state(self) -> dict[str, any]:
        """
        Retrieve pipeline state from database.

        Returns:
            Dictionary containing all state key-value pairs
        """
        state: dict[str, any] = {}
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM pipeline_state")
            rows = cursor.fetchall()
            for key, value in rows:
                try:
                    state[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    state[key] = value
        return state

    def save_state(self, state_dict: dict[str, any]) -> None:
        """
        Save pipeline state to database.

        Args:
            state_dict: Dictionary of state key-value pairs to save
        """
        with self.get_connection() as conn:
            for key, value in state_dict.items():
                value_to_store = json.dumps(value)
                conn.execute(
                    "INSERT OR REPLACE INTO pipeline_state (key, value) VALUES (?, ?)",
                    (key, value_to_store),
                )
        logger.debug("Pipeline state saved to database")

    def close(self) -> None:
        """Close thread-local database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            try:
                self._local.connection.close()
                logger.debug("StateManager database connection closed")
            except Exception:
                pass
            finally:
                self._local.connection = None