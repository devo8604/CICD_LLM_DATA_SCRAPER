"""Comprehensive unit tests for utility functions."""

import subprocess
from unittest.mock import MagicMock, patch

from src.core.utils import (
    _run_git_command,
    check_battery_status,
    clone_or_update_repos,
    estimate_tokens,
    get_battery_status,
    get_repo_urls_from_file,
    get_repos_from_github_page,
    identify_key_sections,
    pause_on_low_battery,
    smart_split_code,
)


class TestBatteryManagement:
    """Test cases for battery management functionality."""

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_success(self, mock_run):
        """Test successful battery status retrieval on macOS."""
        mock_run.return_value = MagicMock(
            stdout=("Now drawing from 'AC Power'\n -InternalBattery-0 (id=1234567)\t85%; charging; 1:23 remaining present: true\n"),
            returncode=0,
        )

        battery = check_battery_status()

        assert battery == 85
        mock_run.assert_called_once_with(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            check=True,
            close_fds=False,
            timeout=10,
        )

    @patch("sys.platform", "linux")
    def test_get_battery_status_non_macos(self):
        assert get_battery_status() is None

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_get_battery_status_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="85%; charging; 1:23 remaining\nAC Power",
            returncode=0,
        )
        status = get_battery_status()
        assert status == {"percent": 85, "plugged": True}

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_get_battery_status_discharging(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="42%; discharging; 2:00 remaining\nBattery Power",
            returncode=0,
        )
        status = get_battery_status()
        assert status == {"percent": 42, "plugged": False}

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_get_battery_status_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "pmset")
        assert get_battery_status() is None

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_low_battery(self, mock_run):
        """Test battery status retrieval with low battery."""
        mock_run.return_value = MagicMock(
            stdout=("Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1234567)\t12%; discharging; 0:23 remaining present: true\n"),
            returncode=0,
        )

        battery = check_battery_status()

        assert battery == 12

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_check_battery_status_full_battery(self, mock_run):
        """Test battery status at 100%."""
        mock_run.return_value = MagicMock(
            stdout=("Now drawing from 'AC Power'\n -InternalBattery-0 (id=1234567)\t100%; charged; 0:00 remaining present: true\n"),
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
        mock_run.return_value = MagicMock(stdout="Some unexpected output without battery info\n", returncode=0)

        battery = check_battery_status()

        assert battery is None

    @patch("sys.platform", "linux")
    def test_pause_on_low_battery_non_macos(self):
        """Test that pause function does nothing on non-macOS."""
        # Should return immediately without checking battery
        pause_on_low_battery()
        # No assertion needed - just verifying it doesn't hang or error

    @patch("sys.platform", "darwin")
    @patch("src.core.utils.check_battery_status")
    def test_pause_on_low_battery_above_threshold(self, mock_battery):
        """Test that pause returns immediately when battery is above threshold."""
        mock_config = MagicMock()
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_battery.return_value = 80  # Above threshold

        pause_on_low_battery(config=mock_config)

        # Should call check_battery_status once and return
        assert mock_battery.call_count == 1

    @patch("sys.platform", "darwin")
    @patch("src.core.utils.check_battery_status")
    @patch("time.sleep")
    def test_pause_on_low_battery_below_threshold_then_recovers(self, mock_sleep, mock_battery):
        """Test pause behavior when battery drops below threshold then recovers."""
        mock_config = MagicMock()
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

        pause_on_low_battery(config=mock_config)

        # Should check battery 4 times and sleep twice
        assert mock_battery.call_count == 4
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(60)

    @patch("sys.platform", "darwin")
    @patch("src.core.utils.check_battery_status")
    def test_pause_on_low_battery_unavailable_status(self, mock_battery):
        """Test handling when battery status becomes unavailable."""
        mock_config = MagicMock()
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_battery.return_value = None

        pause_on_low_battery(config=mock_config)

        # Should return immediately when status is unavailable
        assert mock_battery.call_count == 1

    @patch("sys.platform", "darwin")
    @patch("src.core.utils.check_battery_status")
    @patch("time.sleep")
    def test_pause_on_low_battery_status_becomes_unavailable_while_paused(self, mock_sleep, mock_battery):
        """Test handling when battery status becomes unavailable while paused."""
        mock_config = MagicMock()
        mock_config.BATTERY_LOW_THRESHOLD = 15
        mock_config.BATTERY_HIGH_THRESHOLD = 90
        mock_config.BATTERY_CHECK_INTERVAL = 60

        # Battery low, then becomes unavailable
        mock_battery.side_effect = [10, None]

        pause_on_low_battery(config=mock_config)

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
        repos_file.write_text("# Comment 1\n   \n# Comment 2\n\n# Comment 3\n")

        urls = get_repo_urls_from_file(str(repos_file))

        assert urls == []

    def test_get_repo_urls_with_inline_whitespace(self, tmp_path):
        """Test URLs with leading/trailing whitespace."""
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text("  https://github.com/user/repo1  \n\thttps://github.com/user/repo2\t\nhttps://github.com/user/repo3\n")

        urls = get_repo_urls_from_file(str(repos_file))

        assert len(urls) == 3
        # URLs should be stripped of whitespace
        assert "https://github.com/user/repo1" in urls
        assert "https://github.com/user/repo2" in urls

    def test_get_repo_urls_unsafe_path(self):
        urls = get_repo_urls_from_file("/etc/passwd")
        assert urls == []


class TestGitHubScraping:
    """Test cases for GitHub scraping functionality."""

    @patch("src.core.utils.requests.get")
    def test_get_repos_from_github_page_success(self, mock_get):
        """Test successful scraping of GitHub page."""
        mock_response = MagicMock()
        mock_response.content = b"""
        <html>
            <body>
                <h3 class=\"wb-break-all\"><a href=\"/org/repo1\">repo1</a></h3>
                <a data-hovercard-type=\"repository\" href=\"/org/repo2\">repo2</a>
                <div class=\"Box-row\"><a itemprop=\"name codeRepository\" href=\"/org/repo3\">repo3</a></div>
                <a class=\"v-align-middle\" href=\"/org/repo4\">repo4</a>
            </body>
        </html>
        """
        mock_get.return_value = mock_response

        repos = get_repos_from_github_page("https://github.com/org")

        assert len(repos) == 4
        assert "https://github.com/org/repo1" in repos
        assert "https://github.com/org/repo2" in repos
        assert "https://github.com/org/repo3" in repos
        assert "https://github.com/org/repo4" in repos

    @patch("src.core.utils.requests.get")
    def test_get_repos_from_github_page_error(self, mock_get):
        """Test handling of request errors."""
        mock_get.side_effect = Exception("Network error")

        repos = get_repos_from_github_page("https://github.com/org")

        assert repos == []

    @patch("src.core.utils.requests.get")
    def test_get_repos_from_github_page_parse_error(self, mock_get):
        """Test handling of parsing errors."""
        mock_get.return_value.content = b"Invalid HTML"
        # Since BeautifulSoup handles most invalid HTML gracefully, we force an error by mocking BS if needed
        # Or simpler, if we want to trigger the generic Exception catch in the function:
        with patch("src.core.utils.BeautifulSoup", side_effect=Exception("Parse error")):
            repos = get_repos_from_github_page("https://github.com/org")
            assert repos == []

    def test_get_repos_from_github_page_invalid_url(self):
        assert get_repos_from_github_page("http://evil.com") == []


class TestGitOperations:
    """Test cases for Git operations."""

    @patch("src.core.utils.subprocess.run")
    def test_run_git_command_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="success")
        success, output = _run_git_command(["git", "status"])
        assert success is True
        assert output == "success"

    @patch("src.core.utils.subprocess.run")
    def test_run_git_command_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        success, output = _run_git_command(["git", "status"])
        assert success is False
        assert output == "error"

    @patch("src.core.utils.subprocess.run")
    def test_run_git_command_exception(self, mock_run):
        mock_run.side_effect = Exception("Crash")
        success, output = _run_git_command(["git", "status"])
        assert success is False
        assert "Crash" in output

    def test_run_git_command_invalid_cmd(self):
        success, output = _run_git_command("git status")
        assert success is False
        assert "Invalid command format" in output

    def test_run_git_command_dangerous_chars(self):
        success, output = _run_git_command(["git", "status; rm -rf /"])
        assert success is False
        assert "potentially dangerous characters" in output

    @patch("src.core.utils._run_git_command")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_clone_or_update_repos_new(self, mock_makedirs, mock_exists, mock_git, tmp_path):
        mock_exists.return_value = False  # Not existing
        mock_git.return_value = (True, "Cloned")

        repos_dir = str(tmp_path / "repos")
        clone_or_update_repos(repos_dir, ["https://github.com/user/repo.git"])

        # Verify clone called
        assert mock_git.called
        args, _ = mock_git.call_args
        assert "clone" in args[0]
        assert "https://github.com/user/repo.git" in args[0]

    @patch("src.core.utils._run_git_command")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_clone_or_update_repos_existing(self, mock_makedirs, mock_exists, mock_git, tmp_path):
        mock_exists.return_value = True  # Existing
        mock_git.return_value = (True, "Updated")

        repos_dir = str(tmp_path / "repos")
        clone_or_update_repos(repos_dir, ["https://github.com/user/repo.git"])

        # Verify update calls
        # 1. reset, 2. pull
        assert mock_git.call_count == 2
        assert "reset" in mock_git.call_args_list[0][0][0]
        assert "pull" in mock_git.call_args_list[1][0][0]

    @patch("src.core.utils._run_git_command")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_clone_or_update_repos_fail(self, mock_makedirs, mock_exists, mock_git, tmp_path):
        mock_exists.return_value = False
        mock_git.return_value = (False, "Error")

        repos_dir = str(tmp_path / "repos")
        callback = MagicMock()
        clone_or_update_repos(repos_dir, ["https://github.com/user/repo.git"], progress_callback=callback)

        callback.assert_called_with("https://github.com/user/repo.git", "error", 1, 1)

    def test_clone_or_update_repos_unsafe_dir(self):
        clone_or_update_repos("/etc", ["http://github.com/repo"])
        # Should log error and return


class TestCodeProcessingUtils:
    def test_estimate_tokens(self):
        assert estimate_tokens("hello world") == 2
        assert estimate_tokens("") == 0

    def test_smart_split_code(self):
        content = "line1\nline2\nline3\nline4"
        # 4 chars per token, so each line is ~1.25 tokens.
        # content is ~20 chars = 5 tokens.
        chunks = smart_split_code(content, max_context_tokens=3, overlap_ratio=0)
        assert len(chunks) > 1

    def test_identify_key_sections(self):
        content = "def test():\n    pass\n\nclass MyClass:\n    def __init__(self): pass"
        sections = identify_key_sections(content)
        assert len(sections) >= 2
