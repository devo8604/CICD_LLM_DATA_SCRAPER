"""State management for pipeline progress tracking."""

import sqlite3
import json
import logging
from pathlib import Path


class StateManager:
    """Manages pipeline state persistence using SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize state manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None
        self._connect_db()
        self._create_tables()

    def _connect_db(self) -> None:
        """Establish database connection."""
        try:
            logging.info("Attempting to connect to database from StateManager...")
            self.conn = sqlite3.connect(str(self.db_path))
            self.cursor = self.conn.cursor()
            logging.info(f"StateManager connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.critical(f"Error connecting to database {self.db_path}: {e}")
            raise

    def _create_tables(self) -> None:
        """Create pipeline_state table if it doesn't exist."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        self.conn.commit()
        logging.debug("Ensured pipeline_state table exists.")

    def get_state(self) -> dict[str, any]:
        """
        Retrieve pipeline state from database.

        Returns:
            Dictionary containing all state key-value pairs
        """
        state: dict[str, any] = {}
        self.cursor.execute("SELECT key, value FROM pipeline_state")
        rows = self.cursor.fetchall()
        for key, value in rows:
            try:
                state[key] = json.loads(value)
            except json.JSONDecodeError:
                state[key] = value
        return state

    def save_state(self, state_dict: dict[str, any]) -> None:
        """
        Save pipeline state to database.

        Args:
            state_dict: Dictionary of state key-value pairs to save
        """
        for key, value in state_dict.items():
            value_to_store = (
                json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            )
            self.cursor.execute(
                "INSERT OR REPLACE INTO pipeline_state (key, value) VALUES (?, ?)",
                (key, value_to_store),
            )
        self.conn.commit()
        logging.debug("Pipeline state saved to database.")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logging.debug("StateManager database connection closed.")
            except Exception:
                # Suppress errors during close (already closed or other issue)
                pass
            finally:
                self.conn = None
