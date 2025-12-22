"""Unit tests for the progress tracker module."""

from src.ui.progress_tracker import ProgressTracker, get_progress_tracker


class TestProgressTracker:
    """Test the ProgressTracker class."""

    def test_initialization(self):
        """Test that ProgressTracker initializes properly."""
        tracker = ProgressTracker()

        assert tracker.total_repos == 0
        assert tracker.total_files == 0
        assert tracker.current_repo_index == 0
        assert tracker.current_repo_name == ""
        assert tracker.current_repo_files_total == 0
        assert tracker.current_repo_files_processed == 0
        assert tracker.current_file_path == ""
        assert tracker.current_file_progress == 0.0
        assert tracker.overall_progress == 0.0
        assert tracker.files_processed == 0

    def test_update_total_repos(self):
        """Test updating total repositories."""
        tracker = ProgressTracker()
        tracker.update_total_repos(10)

        assert tracker.total_repos == 10

    def test_update_total_files(self):
        """Test updating total files."""
        tracker = ProgressTracker()
        tracker.update_total_files(100)

        assert tracker.total_files == 100

    def test_update_current_repo(self):
        """Test updating current repository information."""
        tracker = ProgressTracker()
        tracker.update_current_repo(2, "test_repo", 50)

        assert tracker.current_repo_index == 2
        assert tracker.current_repo_name == "test_repo"
        assert tracker.current_repo_files_total == 50
        assert tracker.current_repo_files_processed == 0  # Should reset

    def test_increment_repo_files_processed(self):
        """Test incrementing files processed in current repository."""
        tracker = ProgressTracker()
        tracker.update_total_repos(1)
        tracker.update_total_files(5)
        tracker.update_current_repo(0, "test_repo", 5)

        tracker.increment_repo_files_processed()

        assert tracker.current_repo_files_processed == 1
        assert tracker.files_processed == 1
        assert tracker.overall_progress == 20.0  # 1/5 = 20%

    def test_increment_multiple_files(self):
        """Test incrementing multiple files to see progress."""
        tracker = ProgressTracker()
        tracker.update_total_repos(1)
        tracker.update_total_files(5)

        # Process all 5 files
        for _ in range(5):
            tracker.increment_repo_files_processed()

        assert tracker.current_repo_files_processed == 5
        assert tracker.files_processed == 5
        assert tracker.overall_progress == 100.0  # 5/5 = 100%

    def test_update_current_file(self):
        """Test updating current file path."""
        tracker = ProgressTracker()
        file_path = "/path/to/test/file.py"
        tracker.update_current_file(file_path)

        assert tracker.current_file_path == file_path

    def test_update_file_progress(self):
        """Test updating file progress."""
        tracker = ProgressTracker()
        tracker.update_file_progress(75.5)

        assert tracker.current_file_progress == 75.5

    def test_calculate_overall_progress_zero_total(self):
        """Test calculating overall progress when total files is zero."""
        tracker = ProgressTracker()
        tracker.update_total_repos(1)
        tracker.update_total_files(0)  # Zero total files

        # Add some processed files when total is 0
        tracker.increment_repo_files_processed()

        summary = tracker.get_progress_summary()
        assert summary["total_progress"] == 0.0

    def test_calculate_overall_progress_with_multiple_repos(self):
        """Test calculating overall progress with multiple repositories."""
        tracker = ProgressTracker()
        tracker.update_total_repos(2)
        tracker.update_total_files(10)  # 10 total files across 2 repos
        tracker.update_current_repo(0, "repo1", 4)  # 4 files in first repo

        # Process 2 files in first repo
        tracker.increment_repo_files_processed()
        tracker.increment_repo_files_processed()

        summary = tracker.get_progress_summary()
        assert summary["total_progress"] == 20.0  # 2/10 = 20%
        assert summary["current_repo_index"] == 0
        assert summary["current_repo_name"] == "repo1"
        assert summary["current_repo_files_processed"] == 2

    def test_get_progress_summary(self):
        """Test getting progress summary."""
        tracker = ProgressTracker()
        tracker.update_total_repos(5)
        tracker.update_total_files(20)
        tracker.update_current_repo(1, "test_repo", 4)
        tracker.update_current_file("/path/to/file.py")

        summary = tracker.get_progress_summary()

        expected_summary = {
            "overall_progress": 0.0,
            "total_progress": 0.0,  # No files processed yet
            "total_repos": 5,
            "current_repo_index": 1,
            "current_repo_name": "test_repo",
            "current_repo_files_total": 4,
            "current_repo_files_processed": 0,
            "current_file_path": "/path/to/file.py",
            "current_file_size": 0,
            "current_file_progress": 0.0,
            "total_files": 20,
            "files_processed": 0,
            "elapsed_time": 0,
            "model_name": "Unknown",
            "backend": "Unknown",
        }

        assert summary == expected_summary

    def test_get_detailed_progress_string(self):
        """Test getting detailed progress string."""
        tracker = ProgressTracker()
        tracker.update_total_repos(3)
        tracker.update_total_files(10)
        tracker.update_current_repo(1, "test_repo", 4)
        tracker.update_current_file("/path/to/very_long_filename_that_should_be_truncated.py")
        tracker.increment_repo_files_processed()  # Process 1 file in current repo

        detailed_str = tracker.get_detailed_progress_string()

        # Should contain overall progress, repo info, and current file
        assert "Overall: 10.0%" in detailed_str  # 1/10 = 10%
        assert "Repo: 2/3 - test_repo" in detailed_str
        assert "Files: 1/4 files (25.0%)" in detailed_str  # 1 processed out of 4
        assert "File: very_long_filename_that_should_be_truncated.py" in detailed_str

    def test_detailed_progress_string_no_repos(self):
        """Test detailed progress string when no repositories."""
        tracker = ProgressTracker()

        detailed_str = tracker.get_detailed_progress_string()
        assert detailed_str == "No repositories to process"

    def test_detailed_progress_string_with_long_filename(self):
        """Test that long filenames are truncated appropriately."""
        tracker = ProgressTracker()
        tracker.update_total_repos(1)
        tracker.update_total_files(1)
        tracker.update_current_repo(0, "test_repo", 1)

        # Create a very long filename
        long_filename = "a" * 100 + ".py"
        long_path = f"/path/to/{long_filename}"
        tracker.update_current_file(long_path)

        detailed_str = tracker.get_detailed_progress_string()
        # Should truncate the filename to about 50 chars + "..."
        assert "File: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in detailed_str
        assert "..." in detailed_str

    def test_thread_safety(self):
        """Test that operations are thread-safe by checking for potential race conditions."""
        import threading
        import time

        tracker = ProgressTracker()

        def update_progress():
            for _ in range(10):
                tracker.update_total_repos(5)
                tracker.update_total_files(20)
                tracker.update_current_repo(0, "test_repo", 4)
                tracker.increment_repo_files_processed()
                time.sleep(0.001)  # Small delay to increase chance of race condition if not thread-safe

        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=update_progress)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that no errors occurred and values are reasonable
        summary = tracker.get_progress_summary()
        # Should not have negative values or other obvious errors
        assert summary["total_repos"] == 5  # Should remain at 5
        assert summary["total_files"] == 20  # Should remain at 20
        assert summary["files_processed"] >= 0  # Should not be negative


class TestGetProgressTracker:
    """Test the get_progress_tracker function."""

    def test_get_progress_tracker_singleton(self):
        """Test that get_progress_tracker returns the same instance."""
        tracker1 = get_progress_tracker()
        tracker2 = get_progress_tracker()

        assert tracker1 is tracker2  # Same instance

    def test_global_tracker_functionality(self):
        """Test that the global tracker works correctly."""
        tracker = get_progress_tracker()

        # Manually reset internal state for consistent testing
        tracker.total_repos = 0
        tracker.total_files = 0
        tracker.current_repo_index = 0
        tracker.current_repo_name = ""
        tracker.current_repo_files_total = 0
        tracker.current_repo_files_processed = 0
        tracker.files_processed = 0
        tracker.current_file_path = ""
        tracker.current_file_progress = 0.0

        # Reset the tracker state
        tracker.update_total_repos(1)
        tracker.update_total_files(1)
        tracker.update_current_repo(0, "test_repo", 1)

        # Update progress
        tracker.increment_repo_files_processed()

        # Check that progress was updated
        summary = tracker.get_progress_summary()
        assert summary["total_progress"] == 100.0  # 1/1 = 100%
