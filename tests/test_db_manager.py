"""Comprehensive unit tests for the DBManager class."""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.db_manager import DBManager


class TestDBManagerInitialization:
    """Test cases for DBManager initialization."""

    def test_initialization_with_string_path(self):
        """Test DBManager initialization with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            db_manager = DBManager(db_path)

            assert db_manager.db_path == Path(db_path)
            assert db_manager.state_manager is not None
            assert db_manager.training_data_repo is not None

            db_manager.close_db()

    def test_initialization_with_path_object(self):
        """Test DBManager initialization with Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            assert db_manager.db_path == db_path
            assert db_manager.state_manager is not None
            assert db_manager.training_data_repo is not None

            db_manager.close_db()

    def test_database_file_created(self):
        """Test that database file is created on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            assert db_path.exists()
            db_manager.close_db()

    def test_tables_created_on_initialization(self):
        """Test that required tables are created on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Check that tables exist
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            assert "pipeline_state" in tables
            assert "TrainingSamples" in tables
            assert "ConversationTurns" in tables
            assert "FileHashes" in tables
            assert "FailedFiles" in tables

            conn.close()
            db_manager.close_db()


class TestDBManagerStateManagement:
    """Test cases for state management methods."""

    def test_save_and_get_state(self):
        """Test saving and retrieving state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Save state
            test_state = {
                "current_file": "test.txt",
                "processed_count": 42,
                "status": "running"
            }
            db_manager.save_state(test_state)

            # Retrieve state
            retrieved_state = db_manager.get_state()

            assert retrieved_state["current_file"] == "test.txt"
            assert retrieved_state["processed_count"] == 42
            assert retrieved_state["status"] == "running"

            db_manager.close_db()

    def test_get_state_empty(self):
        """Test getting state when database is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            state = db_manager.get_state()

            assert state == {}
            db_manager.close_db()

    def test_save_state_updates_existing(self):
        """Test that saving state updates existing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Save initial state
            db_manager.save_state({"counter": 1})

            # Update state
            db_manager.save_state({"counter": 2})

            # Retrieve state
            state = db_manager.get_state()

            assert state["counter"] == 2
            db_manager.close_db()

    def test_save_state_with_dict_and_list(self):
        """Test saving state with complex data types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            test_state = {
                "config": {"key1": "value1", "key2": 123},
                "files": ["file1.txt", "file2.txt"],
                "count": 5
            }
            db_manager.save_state(test_state)

            retrieved_state = db_manager.get_state()

            assert retrieved_state["config"] == {"key1": "value1", "key2": 123}
            assert retrieved_state["files"] == ["file1.txt", "file2.txt"]
            assert retrieved_state["count"] == "5"  # Note: Numbers are stored as strings

            db_manager.close_db()


class TestDBManagerQASamples:
    """Test cases for Q&A sample management."""

    def test_add_qa_sample(self):
        """Test adding a Q&A sample."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            sample_id = db_manager.add_qa_sample(
                file_path="test.py",
                question_text="What does this code do?",
                answer_text="It processes data."
            )

            assert sample_id > 0
            db_manager.close_db()

    def test_add_multiple_qa_samples(self):
        """Test adding multiple Q&A samples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            sample_id1 = db_manager.add_qa_sample(
                "test1.py", "Question 1?", "Answer 1"
            )
            sample_id2 = db_manager.add_qa_sample(
                "test2.py", "Question 2?", "Answer 2"
            )

            assert sample_id1 > 0
            assert sample_id2 > 0
            assert sample_id2 > sample_id1

            db_manager.close_db()

    def test_qa_sample_stored_in_database(self):
        """Test that Q&A sample is correctly stored in database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            sample_id = db_manager.add_qa_sample(
                "test.py",
                "What is Python?",
                "A programming language."
            )

            # Verify data in database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT dataset_source FROM TrainingSamples WHERE sample_id = ?",
                (sample_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "repo_file:test.py"

            cursor.execute(
                "SELECT role, content FROM ConversationTurns WHERE sample_id = ? ORDER BY turn_index",
                (sample_id,)
            )
            turns = cursor.fetchall()
            assert len(turns) == 2
            assert turns[0][0] == "user"
            assert turns[0][1] == "What is Python?"
            assert turns[1][0] == "assistant"
            assert turns[1][1] == "A programming language."

            conn.close()
            db_manager.close_db()


class TestDBManagerFileHashes:
    """Test cases for file hash management."""

    def test_save_and_get_file_hash(self):
        """Test saving and retrieving file hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            test_hash = "a" * 64  # SHA256 hash length
            db_manager.save_file_hash("test.py", test_hash)

            retrieved_hash = db_manager.get_file_hash("test.py")

            assert retrieved_hash == test_hash
            db_manager.close_db()

    def test_get_file_hash_nonexistent(self):
        """Test getting hash for file that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            result = db_manager.get_file_hash("nonexistent.py")

            assert result is None
            db_manager.close_db()

    def test_save_file_hash_with_sample_id(self):
        """Test saving file hash with associated sample_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            sample_id = db_manager.add_qa_sample("test.py", "Q?", "A")
            test_hash = "b" * 64

            db_manager.save_file_hash("test.py", test_hash, sample_id)

            # Verify in database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content_hash, sample_id FROM FileHashes WHERE file_path = ?",
                ("test.py",)
            )
            row = cursor.fetchone()

            assert row[0] == test_hash
            assert row[1] == sample_id

            conn.close()
            db_manager.close_db()

    def test_delete_file_hash(self):
        """Test deleting file hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Save a hash
            db_manager.save_file_hash("test.py", "c" * 64)

            # Verify it exists
            assert db_manager.get_file_hash("test.py") is not None

            # Delete it
            db_manager.delete_file_hash("test.py")

            # Verify it's gone
            assert db_manager.get_file_hash("test.py") is None

            db_manager.close_db()

    def test_get_all_tracked_files(self):
        """Test getting all tracked files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Save multiple file hashes
            db_manager.save_file_hash("file1.py", "a" * 64)
            db_manager.save_file_hash("file2.py", "b" * 64)
            db_manager.save_file_hash("file3.py", "c" * 64)

            tracked_files = db_manager.get_all_tracked_files()

            assert len(tracked_files) == 3
            assert "file1.py" in tracked_files
            assert "file2.py" in tracked_files
            assert "file3.py" in tracked_files

            db_manager.close_db()

    def test_get_all_tracked_files_empty(self):
        """Test getting tracked files when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            tracked_files = db_manager.get_all_tracked_files()

            assert tracked_files == []
            db_manager.close_db()

    def test_get_processed_question_hashes(self):
        """Test getting processed question hashes for a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Add multiple Q&A samples for same file
            db_manager.add_qa_sample("test.py", "Question 1?", "Answer 1")
            db_manager.add_qa_sample("test.py", "Question 2?", "Answer 2")

            # Get hashes
            hashes = db_manager.get_processed_question_hashes("test.py")

            assert isinstance(hashes, set)
            assert len(hashes) == 2

            db_manager.close_db()


class TestDBManagerDeleteOperations:
    """Test cases for deletion operations."""

    def test_delete_samples_for_file(self):
        """Test deleting all samples for a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Add samples for two files
            db_manager.add_qa_sample("file1.py", "Q1?", "A1")
            db_manager.add_qa_sample("file1.py", "Q2?", "A2")
            db_manager.add_qa_sample("file2.py", "Q3?", "A3")

            # Delete samples for file1.py
            db_manager.delete_samples_for_file("file1.py")

            # Verify file1.py samples are gone
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM TrainingSamples WHERE dataset_source LIKE ?",
                ("%file1.py%",)
            )
            count = cursor.fetchone()[0]
            assert count == 0

            # Verify file2.py samples still exist
            cursor.execute(
                "SELECT COUNT(*) FROM TrainingSamples WHERE dataset_source LIKE ?",
                ("%file2.py%",)
            )
            count = cursor.fetchone()[0]
            assert count == 1

            conn.close()
            db_manager.close_db()


class TestDBManagerFailedFiles:
    """Test cases for failed file management."""

    def test_add_failed_file(self):
        """Test adding a failed file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            db_manager.add_failed_file("failed.py", "Syntax error")

            failed_files = db_manager.get_failed_files()

            assert len(failed_files) == 1
            assert failed_files[0][0] == "failed.py"
            assert failed_files[0][1] == "Syntax error"

            db_manager.close_db()

    def test_get_failed_files_empty(self):
        """Test getting failed files when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            failed_files = db_manager.get_failed_files()

            assert failed_files == []
            db_manager.close_db()

    def test_add_multiple_failed_files(self):
        """Test adding multiple failed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            db_manager.add_failed_file("fail1.py", "Error 1")
            db_manager.add_failed_file("fail2.py", "Error 2")
            db_manager.add_failed_file("fail3.py", "Error 3")

            failed_files = db_manager.get_failed_files()

            assert len(failed_files) == 3
            file_paths = [f[0] for f in failed_files]
            assert "fail1.py" in file_paths
            assert "fail2.py" in file_paths
            assert "fail3.py" in file_paths

            db_manager.close_db()

    def test_remove_failed_file(self):
        """Test removing a failed file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Add failed files
            db_manager.add_failed_file("fail1.py", "Error 1")
            db_manager.add_failed_file("fail2.py", "Error 2")

            # Remove one
            db_manager.remove_failed_file("fail1.py")

            # Verify
            failed_files = db_manager.get_failed_files()
            assert len(failed_files) == 1
            assert failed_files[0][0] == "fail2.py"

            db_manager.close_db()


class TestDBManagerCloseDB:
    """Test cases for database closure."""

    def test_close_db(self):
        """Test closing database connections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Should not raise any errors
            db_manager.close_db()

    def test_close_db_idempotent(self):
        """Test that closing database multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Close multiple times - should not raise errors
            db_manager.close_db()
            db_manager.close_db()
            db_manager.close_db()

    @patch('src.db_manager.logging')
    def test_close_db_logs_error_on_exception(self, mock_logging):
        """Test that close_db logs errors but doesn't raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            # Mock close methods to raise exceptions
            db_manager.state_manager.close = MagicMock(side_effect=Exception("Test error"))

            # Should not raise, but should log error
            db_manager.close_db()

            # Verify error was logged
            assert mock_logging.error.called


class TestDBManagerDelegation:
    """Test that DBManager properly delegates to sub-managers."""

    def test_get_state_delegates_to_state_manager(self):
        """Test that get_state delegates to StateManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            with patch.object(db_manager.state_manager, 'get_state', return_value={"test": "value"}):
                result = db_manager.get_state()

                db_manager.state_manager.get_state.assert_called_once()
                assert result == {"test": "value"}

            db_manager.close_db()

    def test_save_state_delegates_to_state_manager(self):
        """Test that save_state delegates to StateManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            with patch.object(db_manager.state_manager, 'save_state'):
                db_manager.save_state({"key": "value"})

                db_manager.state_manager.save_state.assert_called_once_with({"key": "value"})

            db_manager.close_db()

    def test_add_qa_sample_delegates_to_training_data_repo(self):
        """Test that add_qa_sample delegates to TrainingDataRepository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db_manager = DBManager(db_path)

            with patch.object(db_manager.training_data_repo, 'add_qa_sample', return_value=42):
                result = db_manager.add_qa_sample("file.py", "Q?", "A")

                db_manager.training_data_repo.add_qa_sample.assert_called_once_with("file.py", "Q?", "A")
                assert result == 42

            db_manager.close_db()
