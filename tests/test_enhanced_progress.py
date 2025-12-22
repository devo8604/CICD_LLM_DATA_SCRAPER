"""Unit tests for enhanced progress display."""

import time
from unittest.mock import patch

from src.ui.enhanced_progress import EnhancedProgressDisplay, ProcessingStats


class TestProcessingStats:
    """Test ProcessingStats dataclass."""

    def test_initialization(self):
        """Test default initialization."""
        stats = ProcessingStats()

        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.files_failed == 0
        assert stats.qa_pairs_generated == 0
        assert stats.tokens_used == 0
        assert stats.current_file == ""
        assert stats.current_repo == ""
        assert stats.start_time > 0

    def test_total_files(self):
        """Test total_files property."""
        stats = ProcessingStats(
            files_processed=10,
            files_skipped=5,
            files_failed=2,
        )

        assert stats.total_files == 17

    def test_success_rate_zero_files(self):
        """Test success_rate with no files."""
        stats = ProcessingStats()
        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Test success_rate calculation."""
        stats = ProcessingStats(
            files_processed=8,
            files_skipped=0,
            files_failed=2,
        )

        # 8 processed out of 10 total = 80%
        assert stats.success_rate == 80.0

    def test_success_rate_with_skipped(self):
        """Test success_rate includes skipped files in total."""
        stats = ProcessingStats(
            files_processed=10,
            files_skipped=5,
            files_failed=0,
        )

        # Skipped files count in the total
        # 10 processed out of 15 total = 66.67%
        assert abs(stats.success_rate - 66.67) < 0.01

    def test_elapsed_time(self):
        """Test elapsed_time calculation."""
        start = time.time()
        stats = ProcessingStats(start_time=start)

        time.sleep(0.1)  # Sleep for 100ms

        elapsed = stats.elapsed_time
        assert elapsed >= 0.1
        assert elapsed < 0.5  # Should be less than 500ms

    def test_elapsed_timedelta(self):
        """Test elapsed_timedelta returns timedelta object."""
        stats = ProcessingStats(start_time=time.time() - 100)

        delta = stats.elapsed_timedelta
        assert delta.seconds >= 99
        assert delta.seconds <= 101

    def test_estimated_cost_default_pricing(self):
        """Test cost estimation with default pricing."""
        stats = ProcessingStats(tokens_used=1_000_000)

        cost = stats.estimated_cost()

        # With default pricing:
        # Input (30%): 300k tokens * $0.15/1M = $0.045
        # Output (70%): 700k tokens * $0.60/1M = $0.420
        # Total: $0.465
        assert abs(cost - 0.465) < 0.001

    def test_estimated_cost_custom_pricing(self):
        """Test cost estimation with custom pricing."""
        stats = ProcessingStats(tokens_used=2_000_000)

        pricing = {
            "input_price": 0.10,
            "output_price": 0.40,
        }
        cost = stats.estimated_cost(pricing)

        # Input (30%): 600k tokens * $0.10/1M = $0.060
        # Output (70%): 1.4M tokens * $0.40/1M = $0.560
        # Total: $0.620
        assert abs(cost - 0.620) < 0.001

    def test_estimated_cost_zero_tokens(self):
        """Test cost estimation with zero tokens."""
        stats = ProcessingStats(tokens_used=0)

        cost = stats.estimated_cost()
        assert cost == 0.0


class TestEnhancedProgressDisplay:
    """Test EnhancedProgressDisplay class."""

    def test_initialization(self):
        """Test initialization."""
        display = EnhancedProgressDisplay(total_repos=10, show_battery=True)

        assert display.total_repos == 10
        assert display.show_battery is True
        assert display.stats.files_processed == 0
        assert display.live is None

    def test_initialization_no_battery(self):
        """Test initialization without battery display."""
        display = EnhancedProgressDisplay(show_battery=False)

        assert display.show_battery is False

    @patch("src.ui.enhanced_progress.Live")
    def test_start_stop(self, mock_live):
        """Test start and stop methods."""
        display = EnhancedProgressDisplay(total_repos=5)

        # Start
        display.start()
        assert display.live is not None

        # Stop
        display.stop()

    def test_record_file_processed(self):
        """Test recording a processed file."""
        display = EnhancedProgressDisplay()

        display.record_file_processed(qa_count=5, tokens=1000)

        assert display.stats.files_processed == 1
        assert display.stats.qa_pairs_generated == 5
        assert display.stats.tokens_used == 1000

    def test_record_file_skipped(self):
        """Test recording a skipped file."""
        display = EnhancedProgressDisplay()

        display.record_file_skipped()
        display.record_file_skipped()

        assert display.stats.files_skipped == 2

    def test_record_file_failed(self):
        """Test recording a failed file."""
        display = EnhancedProgressDisplay()

        display.record_file_failed()

        assert display.stats.files_failed == 1

    def test_set_current_file(self):
        """Test setting current file."""
        display = EnhancedProgressDisplay()

        display.set_current_file("/path/to/file.py")

        assert display.stats.current_file == "/path/to/file.py"

    def test_update_repo_progress(self):
        """Test updating repository progress."""
        display = EnhancedProgressDisplay(total_repos=10)

        display.update_repo_progress(5, "my-repo")

        assert display.stats.current_repo == "my-repo"

    def test_update_file_progress(self):
        """Test updating file progress."""
        display = EnhancedProgressDisplay()

        display.update_file_progress(total=100, current=50, description="my-repo")

        # Should update without error

    @patch("src.ui.enhanced_progress.get_battery_status")
    def test_get_battery_display_with_battery(self, mock_battery):
        """Test battery display when battery info is available."""
        mock_battery.return_value = {"percent": 75, "plugged": False}

        display = EnhancedProgressDisplay(show_battery=True)
        battery_text = display._get_battery_display()

        assert battery_text is not None
        assert "75%" in battery_text.plain

    @patch("src.ui.enhanced_progress.get_battery_status")
    def test_get_battery_display_no_battery(self, mock_battery):
        """Test battery display when battery info not available."""
        mock_battery.return_value = None

        display = EnhancedProgressDisplay(show_battery=True)
        battery_text = display._get_battery_display()

        assert battery_text is None

    def test_get_battery_display_disabled(self):
        """Test battery display when disabled."""
        display = EnhancedProgressDisplay(show_battery=False)
        battery_text = display._get_battery_display()

        assert battery_text is None

    @patch("src.ui.enhanced_progress.get_battery_status")
    def test_get_battery_display_charging(self, mock_battery):
        """Test battery display when charging."""
        mock_battery.return_value = {"percent": 50, "plugged": True}

        display = EnhancedProgressDisplay(show_battery=True)
        battery_text = display._get_battery_display()

        assert battery_text is not None
        assert "50%" in battery_text.plain
        assert "charging" in battery_text.plain

    def test_get_current_status(self):
        """Test current status display."""
        display = EnhancedProgressDisplay()

        display.stats.current_repo = "my-repo"
        display.stats.current_file = "/path/to/file.py"

        status = display._get_current_status()

        assert "my-repo" in status.plain
        assert "file.py" in status.plain

    def test_get_current_status_long_filename(self):
        """Test current status with very long filename."""
        display = EnhancedProgressDisplay()

        long_path = "/very/long/path/" + ("x" * 100) + "/file.py"
        display.stats.current_file = long_path

        status = display._get_current_status()

        # Should truncate long filenames
        assert len(status.plain) < len(long_path)
        assert "..." in status.plain

    def test_get_stats_table(self):
        """Test stats table generation."""
        display = EnhancedProgressDisplay()

        # Add some stats
        display.stats.files_processed = 10
        display.stats.files_skipped = 2
        display.stats.files_failed = 1
        display.stats.qa_pairs_generated = 50
        display.stats.tokens_used = 10000

        table = display._get_stats_table()

        # Table should be created without errors
        assert table is not None

    @patch("src.ui.enhanced_progress.Console")
    def test_print_summary(self, mock_console):
        """Test printing final summary."""
        display = EnhancedProgressDisplay()

        display.stats.files_processed = 20
        display.stats.files_skipped = 5
        display.stats.files_failed = 2
        display.stats.qa_pairs_generated = 100
        display.stats.tokens_used = 50000

        display.print_summary()

        # Should call console.print
        assert display.console.print.called

    def test_battery_check_throttling(self):
        """Test that battery checks are throttled."""
        display = EnhancedProgressDisplay(show_battery=True)

        # First check should happen
        display._get_battery_display()
        first_check_time = display.last_battery_check

        # Immediate second check should use cached value
        display._get_battery_display()
        assert display.last_battery_check == first_check_time

        # After 11 seconds, should check again
        display.last_battery_check = time.time() - 11
        with patch("src.ui.enhanced_progress.get_battery_status") as mock_battery:
            mock_battery.return_value = {"percent": 50, "plugged": False}
            display._get_battery_display()
            assert mock_battery.called
