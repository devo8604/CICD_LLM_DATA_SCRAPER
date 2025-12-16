"""Comprehensive unit tests for utility functions."""

import pytest
import sys
from unittest.mock import patch, MagicMock, call
import subprocess
import time

from src.utils import (
    check_battery_status,
    pause_on_low_battery,
    get_repo_urls_from_file,
)


class TestBatteryManagement:
    """Test cases for battery management functionality."""

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_success(self, mock_run):
        """Test successful battery status retrieval on macOS."""
        mock_run.return_value = MagicMock(
            stdout="Now drawing from 'AC Power'\n -InternalBattery-0 (id=1234567)	85%; charging; 1:23 remaining present: true\n",
            returncode=0,
        )

        battery = check_battery_status()

        assert battery == 85
        mock_run.assert_called_once_with(
            ["pmset", "-g", "batt"], capture_output=True, text=True, check=True
        )

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_low_battery(self, mock_run):
        """Test battery status retrieval with low battery."""
        mock_run.return_value = MagicMock(
            stdout="Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1234567)	12%; discharging; 0:23 remaining present: true\n",
            returncode=0,
        )

        battery = check_battery_status()

        assert battery == 12

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_full_battery(self, mock_run):
        """Test battery status at 100%."""
        mock_run.return_value = MagicMock(
            stdout="Now drawing from 'AC Power'\n -InternalBattery-0 (id=1234567)	100%; charged; 0:00 remaining present: true\n",
            returncode=0,
        )

        battery = check_battery_status()

        assert battery == 100

    @patch("sys.platform", "linux")
    def test_check_battery_status_non_macos(self):
        """Test that battery check returns None on non-macOS platforms."""
        battery = check_battery_status()

        assert battery is None

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_command_error(self, mock_run):
        """Test handling of subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "pmset")

        battery = check_battery_status()

        assert battery is None

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_file_not_found(self, mock_run):
        """Test handling when pmset is not found."""
        mock_run.side_effect = FileNotFoundError("pmset not found")

        battery = check_battery_status()

        assert battery is None

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_malformed_output(self, mock_run):
        """Test handling of malformed pmset output."""
        mock_run.return_value = MagicMock(
            stdout="Some unexpected output without battery info\n", returncode=0
        )

        battery = check_battery_status()

        assert battery is None

    @patch("sys.platform", "linux")
    def test_pause_on_low_battery_non_macos(self):
        """Test that pause function does nothing on non-macOS."""
        # Should return immediately without checking battery
        pause_on_low_battery()
        # No assertion needed - just verifying it doesn't hang or error

    @patch("sys.platform", "darwin")
    @patch("src.utils.check_battery_status")
    @patch("src.utils.config")
    def test_pause_on_low_battery_above_threshold(self, mock_config, mock_battery):
        """Test that pause returns immediately when battery is above threshold."""
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_battery.return_value = 80  # Above threshold

        pause_on_low_battery()

        # Should call check_battery_status once and return
        assert mock_battery.call_count == 1

    @patch("sys.platform", "darwin")
    @patch("src.utils.check_battery_status")
    @patch("src.utils.config")
    @patch("time.sleep")
    def test_pause_on_low_battery_below_threshold_then_recovers(
        self, mock_sleep, mock_config, mock_battery
    ):
        """Test pause behavior when battery drops below threshold then recovers."""
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_config.BATTERY_HIGH_THRESHOLD = 90
        mock_config.BATTERY_CHECK_INTERVAL = 60

        # Flow:
        # 1. First check: 10% (< 15) - enters pause, logs warning
        # 2. Inner while: 10 < 90, sleep, then check: 50%
        # 3. Inner while: 50 < 90, sleep, then check: 95%
        # 4. Inner while: 95 >= 90, exits inner while, logs resume message
        # 5. Outer while: loops back to top, check: 95% (>= 15) - returns
        mock_battery.side_effect = [10, 50, 95, 95]

        pause_on_low_battery()

        # Should check battery 4 times and sleep twice
        assert mock_battery.call_count == 4
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(60)

    @patch("sys.platform", "darwin")
    @patch("src.utils.check_battery_status")
    @patch("src.utils.config")
    def test_pause_on_low_battery_unavailable_status(self, mock_config, mock_battery):
        """Test handling when battery status becomes unavailable."""
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_battery.return_value = None

        pause_on_low_battery()

        # Should return immediately when status is unavailable
        assert mock_battery.call_count == 1

    @patch("sys.platform", "darwin")
    @patch("src.utils.check_battery_status")
    @patch("src.utils.config")
    @patch("time.sleep")
    def test_pause_on_low_battery_status_becomes_unavailable_while_paused(
        self, mock_sleep, mock_config, mock_battery
    ):
        """Test handling when battery status becomes unavailable while paused."""
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_config.BATTERY_HIGH_THRESHOLD = 90
        mock_config.BATTERY_CHECK_INTERVAL = 60

        # Battery low, then becomes unavailable
        mock_battery.side_effect = [10, None]

        pause_on_low_battery()

        # Should check twice, sleep once, then return when status unavailable
        assert mock_battery.call_count == 2
        assert mock_sleep.call_count == 1


class TestRepoURLs:
    """Test cases for repository URL handling."""

    def test_get_repo_urls_from_file(self, tmp_path):
        """Test reading repository URLs from file."""
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text(
            "https://github.com/user/repo1\n"
            "https://github.com/user/repo2\n"
            "# This is a comment\n"
            "https://github.com/user/repo3\n"
            "\n"  # Empty line
            "https://github.com/user/repo4\n"
        )

        urls = get_repo_urls_from_file(str(repos_file))

        assert len(urls) == 4
        assert "https://github.com/user/repo1" in urls
        assert "https://github.com/user/repo2" in urls
        assert "https://github.com/user/repo3" in urls
        assert "https://github.com/user/repo4" in urls
        assert "# This is a comment" not in urls

    def test_get_repo_urls_empty_file(self, tmp_path):
        """Test reading from empty file."""
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text("")

        urls = get_repo_urls_from_file(str(repos_file))

        assert urls == []

    def test_get_repo_urls_file_not_found(self):
        """Test handling when repos.txt doesn't exist."""
        urls = get_repo_urls_from_file("nonexistent_repos.txt")

        assert urls == []

    def test_get_repo_urls_only_comments_and_whitespace(self, tmp_path):
        """Test file with only comments and whitespace."""
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text(
            "# Comment 1\n"
            "   \n"
            "# Comment 2\n"
            "\n"
            "# Comment 3\n"
        )

        urls = get_repo_urls_from_file(str(repos_file))

        assert urls == []

    def test_get_repo_urls_with_inline_whitespace(self, tmp_path):
        """Test URLs with leading/trailing whitespace."""
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text(
            "  https://github.com/user/repo1  \n"
            "\thttps://github.com/user/repo2\t\n"
            "https://github.com/user/repo3\n"
        )

        urls = get_repo_urls_from_file(str(repos_file))

        assert len(urls) == 3
        # URLs should be stripped of whitespace
        assert "https://github.com/user/repo1" in urls
        assert "https://github.com/user/repo2" in urls
