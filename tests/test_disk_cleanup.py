"""Unit tests for disk_cleanup module."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from src.utils.disk_cleanup import DiskCleanupManager


class TestDiskCleanupManager(unittest.TestCase):
    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.model.pipeline.data_dir = "/data"
        self.mock_config.REPOS_DIR = "/repos"
        self.mock_config.LOGS_DIR = "/logs"
        self.manager = DiskCleanupManager(self.mock_config)

    def test_init_defaults(self):
        """Test initialization with missing config attributes."""
        empty_config = MagicMock()
        del empty_config.model.pipeline.data_dir
        del empty_config.REPOS_DIR
        del empty_config.LOGS_DIR

        # Accessing missing attributes on MagicMock usually returns another Mock,
        # so we need to force AttributeError to test the except blocks.
        # But DiskCleanupManager accesses them directly.
        # To strictly test the 'except AttributeError', we need an object that raises it.

        class BrokenConfig:
            pass

        manager = DiskCleanupManager(BrokenConfig())
        self.assertEqual(manager.data_dir, Path("data"))
        self.assertEqual(manager.repos_dir, Path("repos"))
        self.assertEqual(manager.logs_dir, Path("logs"))

    @patch("src.utils.disk_cleanup.Path.exists")
    @patch("src.utils.disk_cleanup.Path.glob")
    @patch("time.time")
    def test_cleanup_old_logs(self, mock_time, mock_glob, mock_exists):
        """Test cleaning up logs older than N days."""
        mock_exists.return_value = True
        current_time = 1000000
        mock_time.return_value = current_time

        # 30 days in seconds = 30 * 24 * 3600 = 2,592,000
        days_30 = 2592000

        # File 1: Old (current - 31 days)
        file1 = MagicMock()
        file1.stat.return_value.st_mtime = current_time - days_30 - 100
        file1.__str__.return_value = "/logs/old.log"

        # File 2: New (current - 10 days)
        file2 = MagicMock()
        file2.stat.return_value.st_mtime = current_time - 100
        file2.__str__.return_value = "/logs/new.log"

        # File 3: Old but fails to delete
        file3 = MagicMock()
        file3.stat.return_value.st_mtime = current_time - days_30 - 100
        file3.unlink.side_effect = Exception("Permission denied")
        file3.__str__.return_value = "/logs/error.log"

        mock_glob.return_value = [file1, file2, file3]

        removed = self.manager.cleanup_old_logs(days_to_keep=30)

        self.assertEqual(removed, 1)  # Only file1 successfully removed
        file1.unlink.assert_called_once()
        file2.unlink.assert_not_called()
        file3.unlink.assert_called_once()

    @patch("src.utils.disk_cleanup.Path")
    def test_cleanup_empty_directories_mocked_path(self, mock_path_cls):
        """Test cleanup_empty_directories with mocked Path class."""
        # Setup the manager again with mocked Path to avoid issues
        mock_config = MagicMock()
        manager = DiskCleanupManager(mock_config)

        # When Path(root) is called, it returns a mock.
        # We need THAT mock to handle division.
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance

        # Mock Path.walk to return a root that isn't used for division directly,
        # but passed to Path constructor.
        mock_root_arg = MagicMock()
        mock_path_cls.walk.return_value = [(mock_root_arg, ["dir1", "dir2"], [])]

        # Mock dir objects
        mock_dir1 = MagicMock()
        mock_dir1.is_dir.return_value = True
        mock_dir1.iterdir.return_value = []  # Empty

        mock_dir2 = MagicMock()
        mock_dir2.is_dir.return_value = True
        mock_dir2.iterdir.return_value = [1]  # Not empty

        # Setup division on the instance returned by Path(root)
        def div_side_effect(arg):
            if arg == "dir1":
                return mock_dir1
            if arg == "dir2":
                return mock_dir2
            return MagicMock()

        mock_path_instance.__truediv__.side_effect = div_side_effect

        # Call method
        mock_base = MagicMock()
        mock_base.exists.return_value = True

        count = manager.cleanup_empty_directories(mock_base)

        self.assertEqual(count, 1)
        mock_dir1.rmdir.assert_called_once()
        mock_dir2.rmdir.assert_not_called()

    @patch("src.utils.disk_cleanup.Path")
    def test_cleanup_temp_files(self, mock_path_cls):
        """Test cleanup of temp files."""
        # Manager setup involves Path calls, so valid mocks needed
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance
        manager = DiskCleanupManager(MagicMock())

        # rglob return values
        file1 = MagicMock()
        file1.is_file.return_value = True

        file2 = MagicMock()
        file2.is_file.return_value = True
        file2.unlink.side_effect = Exception("Error")

        # Mocking rglob behavior
        # It iterates over patterns.
        # We can just make it return a list containing files
        mock_path_instance.exists.return_value = True
        mock_path_instance.rglob.return_value = [file1, file2]

        count = manager.cleanup_temp_files()

        # We have 2 dirs (data_dir, repos_dir) * 6 patterns * 2 files each = 24 files found
        # Half fail to delete.
        self.assertEqual(count, 12)
        # file1.unlink called 12 times
        self.assertEqual(file1.unlink.call_count, 12)

    @patch("src.utils.disk_cleanup.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="repo1\nrepo2")
    @patch("time.time")
    @patch("src.utils.disk_cleanup.shutil.rmtree")
    def test_cleanup_old_repos(self, mock_rmtree, mock_time, mock_file, mock_path_cls):
        """Test cleanup of old repositories."""
        mock_time.return_value = 1000000
        days_180 = 180 * 24 * 3600
        cutoff = 1000000 - days_180

        # Setup mocks for Path("repos.txt") vs Path(config...)
        # We use a side_effect that checks arguments to return different mocks

        mock_repos_txt = MagicMock()
        mock_repos_txt.exists.return_value = True

        mock_general_path = MagicMock()

        def path_side_effect(arg=None):
            if str(arg) == "repos.txt":
                return mock_repos_txt
            return mock_general_path

        mock_path_cls.side_effect = path_side_effect

        manager = DiskCleanupManager(MagicMock())
        # The manager.repos_dir will be mock_general_path

        mock_general_path.exists.return_value = True

        # Structure: repos_dir -> org_dir -> repo_dir

        # Org Dir
        org_dir = MagicMock()
        org_dir.is_dir.return_value = True
        org_dir.name = "org"

        # Repo 1: In repos.txt (keep)
        repo1 = MagicMock()
        repo1.is_dir.return_value = True
        repo1.name = "repo1"
        repo1.stat.return_value.st_mtime = cutoff - 100  # Old but kept

        # Repo 2: Not in repos.txt, Old (delete)
        repo2 = MagicMock()
        repo2.is_dir.return_value = True
        repo2.name = "repo_old"
        repo2.stat.return_value.st_mtime = cutoff - 100

        # Repo 3: Not in repos.txt, New (keep)
        repo3 = MagicMock()
        repo3.is_dir.return_value = True
        repo3.name = "repo_new"
        repo3.stat.return_value.st_mtime = cutoff + 100

        org_dir.iterdir.return_value = [repo1, repo2, repo3]
        mock_general_path.iterdir.return_value = [org_dir]

        count = manager.cleanup_old_repos()

        self.assertEqual(count, 1)
        mock_rmtree.assert_called_once_with(repo2)

    @patch("src.utils.disk_cleanup.psutil.disk_usage")
    def test_get_disk_usage_percent(self, mock_usage):
        """Test disk usage calculation."""
        manager = DiskCleanupManager(MagicMock())

        # Success case
        mock_usage.return_value = MagicMock(used=80, total=100)
        self.assertEqual(manager.get_disk_usage_percent(), 80.0)

        # Failure case fallback
        mock_usage.side_effect = [Exception("Error"), MagicMock(used=50, total=100)]
        self.assertEqual(manager.get_disk_usage_percent(), 50.0)

        # Total failure
        mock_usage.side_effect = Exception("Error")
        self.assertEqual(manager.get_disk_usage_percent(), 0.0)

    @patch("src.utils.disk_cleanup.DiskCleanupManager.get_disk_usage_percent")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_old_logs")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_temp_files")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_empty_directories")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_old_repos")
    def test_cleanup_if_needed(self, mock_repos, mock_dirs, mock_temp, mock_logs, mock_disk):
        """Test cleanup trigger logic."""
        manager = DiskCleanupManager(MagicMock())

        # Case 1: Usage low (no cleanup)
        mock_disk.return_value = 50.0
        stats = manager.cleanup_if_needed(threshold_percent=80.0)
        self.assertEqual(stats["disk_usage_before"], 50.0)
        mock_logs.assert_not_called()

        # Case 2: Usage high (cleanup triggered)
        mock_disk.side_effect = [85.0, 70.0]  # Before, After
        stats = manager.cleanup_if_needed(threshold_percent=80.0)
        self.assertEqual(stats["disk_usage_before"], 85.0)
        mock_logs.assert_called_once()
        self.assertEqual(stats["disk_usage_after"], 70.0)

    @patch("src.utils.disk_cleanup.DiskCleanupManager.get_disk_usage_percent")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_old_logs")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_temp_files")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_empty_directories")
    @patch("src.utils.disk_cleanup.DiskCleanupManager.cleanup_old_repos")
    def test_force_cleanup(self, mock_repos, mock_dirs, mock_temp, mock_logs, mock_disk):
        """Test forced cleanup."""
        manager = DiskCleanupManager(MagicMock())
        mock_disk.return_value = 40.0

        stats = manager.force_cleanup()

        mock_logs.assert_called_once()
        mock_temp.assert_called_once()
        mock_dirs.assert_called_once()
        mock_repos.assert_called_once()
        self.assertEqual(stats["disk_usage_after"], 40.0)
