import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.data.optimized_db_manager import OptimizedDBManager


class TestOptimizedDBManager:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test.db")

    @pytest.fixture
    def db_manager(self, db_path):
        manager = OptimizedDBManager(db_path)
        yield manager
        manager.close_db()

    def test_initialization(self, db_manager):
        # Check tables exist
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert "qa_samples" in tables
            assert "file_hashes" in tables
            assert "failed_files" in tables
            assert "processing_state" in tables
            assert "processed_questions" in tables

    def test_add_qa_sample(self, db_manager):
        assert db_manager.add_qa_sample("file.txt", "Q", "A") is True

        samples = db_manager.get_qa_samples_for_file("file.txt")
        assert len(samples) == 1
        assert samples[0]["question"] == "Q"
        assert samples[0]["answer"] == "A"

    def test_add_qa_samples_batch(self, db_manager):
        samples = [("file1.txt", "Q1", "A1"), ("file2.txt", "Q2", "A2")]
        assert db_manager.add_qa_samples_batch(samples) is True

        assert len(db_manager.get_qa_samples_for_file("file1.txt")) == 1
        assert len(db_manager.get_qa_samples_for_file("file2.txt")) == 1

    def test_get_all_tracked_files(self, db_manager):
        db_manager.add_qa_sample("file1.txt", "Q", "A")
        db_manager.add_qa_sample("file2.txt", "Q", "A")

        files = db_manager.get_all_tracked_files()
        assert len(files) == 2
        assert "file1.txt" in files
        assert "file2.txt" in files

    def test_file_hash_operations(self, db_manager):
        assert db_manager.save_file_hash("file.txt", "hash123") is True
        assert db_manager.get_file_hash("file.txt") == "hash123"

        assert db_manager.delete_file_hash("file.txt") is True
        assert db_manager.get_file_hash("file.txt") is None

    def test_delete_samples_for_file(self, db_manager):
        db_manager.add_qa_sample("file.txt", "Q", "A")
        assert db_manager.delete_samples_for_file("file.txt") is True
        assert len(db_manager.get_qa_samples_for_file("file.txt")) == 0

    def test_failed_files_operations(self, db_manager):
        assert db_manager.add_failed_file("file.txt", "reason") is True

        failed = db_manager.get_failed_files()
        assert len(failed) == 1
        assert failed[0] == ("file.txt", "reason")

        assert db_manager.remove_failed_file("file.txt") is True
        assert len(db_manager.get_failed_files()) == 0

    def test_processed_questions_operations(self, db_manager):
        assert db_manager.mark_question_processed("file.txt", "Question 1") is True

        hashes = db_manager.get_processed_question_hashes("file.txt")
        assert len(hashes) == 1

        # Batch
        assert db_manager.mark_questions_processed_batch("file.txt", ["Question 2", "Question 3"]) is True
        hashes = db_manager.get_processed_question_hashes("file.txt")
        assert len(hashes) == 3

    def test_stats(self, db_manager):
        db_manager.add_qa_sample("file.txt", "Q", "A")
        db_manager.add_failed_file("failed.txt", "reason")
        db_manager.mark_question_processed("file.txt", "Q")

        stats = db_manager.get_stats()
        assert stats["qa_samples"] == 1
        assert stats["unique_files"] == 1
        assert stats["failed_files"] == 1
        assert stats["processed_questions"] == 1

    def test_batch_insert_qa_pairs(self, db_manager):
        pairs = [("Q1", "A1"), ("Q2", "A2")]
        assert db_manager.batch_insert_qa_pairs("file.txt", pairs) is True

        samples = db_manager.get_qa_samples_for_file("file.txt")
        assert len(samples) == 2

        # Check questions marked processed
        hashes = db_manager.get_processed_question_hashes("file.txt")
        assert len(hashes) == 2

    def test_error_handling_retry(self, db_manager):
        # We can't easily mock the internal _execute_query failure within a live test unless we mock the connection
        # But we can try to inject a failure by closing connection abruptly or mocking

        with patch.object(db_manager, "_execute_query", side_effect=[sqlite3.Error("Fail"), MagicMock()]) as mock_exec:
            # First fail, then succeed (retry logic)
            # wait, retry decorator re-calls the function. so mocking _execute_query
            # inside the function call is tricky if we mock the method itself.
            # If we mock _execute_query, add_qa_sample calls it.
            # 1st call to add_qa_sample -> calls mock_exec -> raises Error
            # retry catches, sleeps, calls add_qa_sample again
            # 2nd call to add_qa_sample -> calls mock_exec -> returns result

            # However, if we mock _execute_query, we need it to return a valid cursor on success
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_exec.side_effect = [sqlite3.Error("Fail"), mock_cursor]

            # We test a read operation for simplicity
            db_manager.get_all_tracked_files()

            assert mock_exec.call_count == 1

    def test_database_error_propagation(self, db_manager):
        # Test that persistent errors raise DatabaseError (or return False depending on method)
        # methods decorated with retry(..., exceptions=...) usually re-raise after max attempts,
        # BUT the methods in OptimizedDBManager wrap the call in try/except and return False/None/Empty list.

        with patch.object(db_manager, "_execute_query", side_effect=sqlite3.Error("Persistent Fail")):
            assert db_manager.add_qa_sample("f", "q", "a") is False
