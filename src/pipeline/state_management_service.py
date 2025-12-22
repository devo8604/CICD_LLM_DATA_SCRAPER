"""Service layer for state management operations."""

import logging
from typing import Any

from src.core.config import AppConfig
from src.data.db_manager import DBManager

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class StateManagementService:
    """Handles pipeline state persistence and retrieval."""

    def __init__(self, db_manager: DBManager, config: AppConfig):
        self.db_manager = db_manager
        self.config = config
        self.state = self.load_state()

    def load_state(self) -> dict[str, Any]:
        """Load current pipeline state from database."""
        state = self.db_manager.get_state()
        return {
            "current_repo_name": state.get("current_repo_name"),
            "processed_repos_count": state.get("processed_repos_count", 0),
            "current_file_path_in_repo": state.get("current_file_path_in_repo"),
            "processed_files_count_in_repo": state.get("processed_files_count_in_repo", 0),
        }

    def save_state(self):
        """Save current pipeline state to database."""
        self.db_manager.save_state(self.state)

    def reset_state(self):
        """Reset pipeline state to initial values."""
        self.state = {
            "current_repo_name": None,
            "processed_repos_count": 0,
            "current_file_path_in_repo": None,
            "processed_files_count_in_repo": 0,
        }
        self.save_state()
