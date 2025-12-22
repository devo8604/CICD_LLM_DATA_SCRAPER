"""Unit tests for the StateManagementService."""

from unittest.mock import MagicMock

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.state_management_service import StateManagementService


class TestStateManagementService:
    """Test cases for StateManagementService."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.config = AppConfig()
        self.db_manager = MagicMock(spec=DBManager)
        self.service = StateManagementService(db_manager=self.db_manager, config=self.config)

    def test_load_state_initial(self):
        """Test loading initial state from database."""
        mock_state = {
            "current_repo_name": "test_repo",
            "processed_repos_count": 5,
            "current_file_path_in_repo": "/path/to/file.py",
            "processed_files_count_in_repo": 10,
        }

        self.db_manager.get_state.return_value = mock_state
        service = StateManagementService(db_manager=self.db_manager, config=self.config)

        # Check that state was loaded correctly
        assert service.state["current_repo_name"] == "test_repo"
        assert service.state["processed_repos_count"] == 5
        assert service.state["current_file_path_in_repo"] == "/path/to/file.py"
        assert service.state["processed_files_count_in_repo"] == 10

    def test_load_state_with_defaults(self):
        """Test loading state with missing keys (should use defaults for missing keys only)."""
        # When keys are missing from the state, defaults should be used
        mock_state = {
            # Leave out "processed_repos_count" and "processed_files_count_in_repo" to test defaults
        }

        self.db_manager.get_state.return_value = mock_state
        service = StateManagementService(db_manager=self.db_manager, config=self.config)

        assert service.state["current_repo_name"] is None  # Missing key returns None
        assert service.state["processed_repos_count"] == 0  # Missing key gets default value
        assert service.state["current_file_path_in_repo"] is None  # Missing key returns None
        assert service.state["processed_files_count_in_repo"] == 0  # Missing key gets default value

    def test_save_state(self):
        """Test saving state to database."""
        # Modify the state
        self.service.state["current_repo_name"] = "updated_repo"
        self.service.state["processed_repos_count"] = 7

        # Save the state
        self.service.save_state()

        # Verify that save_state was called with the updated state
        self.db_manager.save_state.assert_called_once_with(self.service.state)

    def test_reset_state(self):
        """Test resetting state to initial values."""
        # Set some values first
        self.service.state["current_repo_name"] = "some_repo"
        self.service.state["processed_repos_count"] = 5
        self.service.state["current_file_path_in_repo"] = "/path/to/file"
        self.service.state["processed_files_count_in_repo"] = 3

        # Reset the state
        self.service.reset_state()

        # Check that state is reset to defaults
        assert self.service.state["current_repo_name"] is None
        assert self.service.state["processed_repos_count"] == 0
        assert self.service.state["current_file_path_in_repo"] is None
        assert self.service.state["processed_files_count_in_repo"] == 0

        # Verify that the reset state was saved to DB
        self.db_manager.save_state.assert_called()
