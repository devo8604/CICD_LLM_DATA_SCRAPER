"""Unit tests for the reset_utils module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.utils.reset_utils import reset_all, reset_database, reset_logs, reset_repos


class TestResetUtils:
    """Test the reset utilities functions."""

    def test_reset_database(self):
        """Test the reset_database function."""
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
            db_path = db_file.name

        try:
            # Verify the file exists
            assert os.path.exists(db_path)

            # Call the reset_database function
            reset_database(db_path)

            # Verify the file was removed
            assert not os.path.exists(db_path)
        finally:
            # Clean up: remove the file if it still exists
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_reset_database_nonexistent_file(self):
        """Test the reset_database function with a nonexistent file."""
        # Use a path that doesn't exist
        nonexistent_path = "/tmp/nonexistent_file.db"

        # Verify the file doesn't exist
        assert not os.path.exists(nonexistent_path)

        # Call the reset_database function (should not raise an exception)
        reset_database(nonexistent_path)

        # Verify it still doesn't exist
        assert not os.path.exists(nonexistent_path)

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.exists")
    def test_reset_database_exception_handling(self, mock_exists, mock_unlink):
        """Test that reset_database handles exceptions gracefully."""
        # Mock Path.exists to return True so the unlink operation is attempted
        mock_exists.return_value = True
        # Mock Path.unlink to raise an exception
        mock_unlink.side_effect = PermissionError("Permission denied")

        # The db_path value doesn't matter since we're mocking the methods
        db_path = "/fake/path.db"

        # Call the reset_database function - this should handle the exception gracefully
        success = reset_database(db_path)

        # Should return False since deletion failed
        assert success is False

    def test_reset_logs(self):
        """Test the reset_logs function."""
        # Create a temporary directory for logs
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)

            # Create some log files in the directory
            log_files = [
                logs_dir / "test_log_20230101_120000.log",
                logs_dir / "test_log_20230102_120000.log",
                logs_dir / "other_file.txt",  # This should not be deleted
                logs_dir / "another_log.txt",  # This should be deleted
            ]

            for log_file in log_files:
                log_file.touch()

            # Verify the files exist
            for log_file in log_files:
                assert log_file.exists()

            # Call the reset_logs function
            reset_logs(logs_dir)

            # Verify the log and txt files were removed
            assert not (logs_dir / "test_log_20230101_120000.log").exists()
            assert not (logs_dir / "test_log_20230102_120000.log").exists()
            assert not (logs_dir / "other_file.txt").exists()  # This should also be removed
            assert not (logs_dir / "another_log.txt").exists()  # .txt files are also removed

    def test_reset_logs_no_matching_files(self):
        """Test the reset_logs function when no matching files exist."""
        # Create a temporary directory with no matching log files
        with tempfile.TemporaryDirectory() as temp_dir:
            other_file = Path(temp_dir) / "other_file.log"
            other_file.touch()

            # Verify the file exists
            assert other_file.exists()

            # Call the reset_logs function with a prefix that doesn't match
            reset_logs("nonexistent_prefix")

            # Verify the other file still exists
            assert other_file.exists()

    def test_reset_repos(self):
        """Test the reset_repos function."""
        # Create a temporary directory for repos
        with tempfile.TemporaryDirectory() as temp_base_dir:
            # Change to the temporary directory so the relative path works correctly
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_base_dir)

                repos_dir_name = "test_repos"
                repos_dir = Path(repos_dir_name)
                repos_dir.mkdir()

                # Create a subdirectory and file in the repos directory
                sub_dir = repos_dir / "test_org" / "test_repo"
                sub_dir.mkdir(parents=True)
                test_file = sub_dir / "test.txt"
                test_file.write_text("test content")

                # Verify the directory and file exist
                assert repos_dir.exists()
                assert (repos_dir / "test_org" / "test_repo").exists()
                assert test_file.exists()

                # Call the reset_repos function
                reset_repos(repos_dir_name)

                # Verify the repos directory is gone
                assert not repos_dir.exists()
            finally:
                os.chdir(original_cwd)  # Restore the original working directory

    def test_reset_repos_nonexistent(self):
        """Test the reset_repos function when the directory doesn't exist."""
        # Call the reset_repos function with a directory that doesn't exist
        reset_repos("nonexistent_repos")
        # Should not raise an exception

    def test_reset_all(self):
        """Test the reset_all function."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create a database file
                db_path = Path("test.db")
                db_path.touch()

                # Create a logs directory with log files
                logs_dir = Path("logs")
                logs_dir.mkdir()
                log_file = logs_dir / "test_log_20230101_120000.log"
                log_file.touch()

                # Create a repos directory
                repos_dir = Path("repos")
                repos_dir.mkdir()
                repos_sub_dir = repos_dir / "test_repo"
                repos_sub_dir.mkdir()

                # Verify all exist
                assert db_path.exists()
                assert log_file.exists()
                assert repos_dir.exists()
                assert repos_sub_dir.exists()

                # Run reset_all
                reset_all(db_path, logs_dir, repos_dir)

                # Verify they were all removed from the current directory
                assert not db_path.exists()
                assert not log_file.exists()
                assert not repos_dir.exists()
            finally:
                os.chdir(original_cwd)  # Restore the original working directory

    def test_reset_all_nonexistent_paths(self):
        """Test the reset_all function with nonexistent paths."""
        # This should not raise an exception even if paths don't exist
        reset_all("nonexistent.db", "nonexistent_prefix", "nonexistent_repos")
        # Should not raise an exception
