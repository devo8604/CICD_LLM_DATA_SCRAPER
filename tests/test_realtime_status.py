import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.realtime_status import (
    RealTimeStatus,
    get_battery_level,
    get_disk_space,
    show_realtime_status,
)


class TestRealTimeStatus:
    @patch("platform.system")
    @patch("subprocess.run")
    def test_get_battery_level_macos_success(self, mock_run, mock_system):
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Now drawing from 'AC Power'\n-InternalBattery-0\t85%; charging; 1:00 remaining",
        )

        result = get_battery_level()
        assert result == (85, True)

    @patch("platform.system")
    @patch("subprocess.run")
    def test_get_battery_level_macos_discharging(self, mock_run, mock_system):
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Now drawing from 'Battery Power'\n-InternalBattery-0\t45%; discharging; 2:00 remaining",
        )

        result = get_battery_level()
        assert result == (45, False)

    @patch("platform.system")
    @patch("subprocess.run")
    def test_get_battery_level_macos_fallback(self, mock_run, mock_system):
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(returncode=0, stdout="InternalBattery 50%; charging")

        result = get_battery_level()
        assert result == (50, True)

    @patch("platform.system")
    def test_get_battery_level_linux(self, mock_system):
        mock_system.return_value = "Linux"
        assert get_battery_level() is None

    @patch("platform.system")
    @patch("subprocess.run")
    def test_get_battery_level_error(self, mock_run, mock_system):
        mock_system.return_value = "Darwin"
        mock_run.side_effect = Exception("Fail")
        assert get_battery_level() is None

    @patch("shutil.disk_usage")
    def test_get_disk_space(self, mock_disk_usage):
        mock_disk_usage.return_value = (1000, 500, 500)
        total, used, percent = get_disk_space(".")
        assert total == 1000
        assert used == 500
        assert percent == 50.0

    @pytest.fixture
    def status_obj(self):
        config = MagicMock(spec=AppConfig)
        config.DB_PATH = "pipeline.db"
        config.BASE_DIR = "."
        config.REPOS_DIR_NAME = "repos"
        data_dir = Path("data")
        return RealTimeStatus(config, data_dir)

    def test_get_database_stats_not_exists(self, status_obj):
        with patch.object(Path, "exists", return_value=False):
            stats = status_obj.get_database_stats()
            assert stats["total_samples"] == 0

    def test_get_database_stats_cached(self, status_obj):
        status_obj._cached_db_stats = {"total_samples": 100}
        status_obj._last_db_check = time.time()

        stats = status_obj.get_database_stats()
        assert stats["total_samples"] == 100

    def test_get_database_stats_query(self, status_obj):
        with (
            patch.object(Path, "exists", return_value=True),
            patch("sqlite3.connect") as mock_connect,
        ):
            mock_cursor = MagicMock()
            mock_connect.return_value.cursor.return_value = mock_cursor
            # Mock return values for the 5 queries
            mock_cursor.fetchone.side_effect = [
                (10,),
                (20,),
                (5,),
                (15,),
                ("2023-01-01",),
            ]

            stats = status_obj.get_database_stats()

            assert stats["total_samples"] == 10
            assert stats["total_turns"] == 20
            assert stats["failed_files"] == 5
            assert stats["processed_files"] == 15
            assert stats["last_activity"] == "2023-01-01"

    def test_get_repository_count(self, status_obj):
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir") as mock_iterdir,
        ):
            # Org dir
            org_dir = MagicMock()
            org_dir.is_dir.return_value = True
            org_dir.name = "org"

            # Repo dir
            repo_dir = MagicMock()
            repo_dir.is_dir.return_value = True
            repo_dir.name = "repo"

            org_dir.iterdir.return_value = [repo_dir]
            mock_iterdir.return_value = [org_dir]

            assert status_obj.get_repository_count() == 1

    def test_get_database_size(self, status_obj):
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 1024
            assert status_obj.get_database_size() == "1.00 KB"

    def test_get_repos_txt_count(self, status_obj):
        with (
            patch.object(Path, "exists", return_value=True),
            patch("builtins.open", mock_open(read_data="repo1\nrepo2\n#comment")),
        ):
            assert status_obj.get_repos_txt_count() == 2

    def test_get_next_recommended_action(self, status_obj):
        with patch.object(status_obj, "get_repos_txt_count", return_value=0):
            assert "repos.txt" in status_obj.get_next_recommended_action({})

        with (
            patch.object(status_obj, "get_repos_txt_count", return_value=1),
            patch.object(status_obj, "get_repository_count", return_value=0),
        ):
            assert "scrape" in status_obj.get_next_recommended_action({})

        with (
            patch.object(status_obj, "get_repos_txt_count", return_value=1),
            patch.object(status_obj, "get_repository_count", return_value=1),
        ):
            db_stats = {"processed_files": 0}
            assert "prepare" in status_obj.get_next_recommended_action(db_stats)

            db_stats = {"processed_files": 1, "failed_files": 1}
            assert "retry" in status_obj.get_next_recommended_action(db_stats)

            db_stats = {"processed_files": 1, "failed_files": 0, "total_samples": 1}
            assert "export" in status_obj.get_next_recommended_action(db_stats)

    def test_get_status_panel(self, status_obj):
        # Mock all internal calls to avoid complex setup
        with (
            patch("src.pipeline.realtime_status.get_battery_level", return_value=(50, True)),
            patch("src.pipeline.realtime_status.get_disk_space", return_value=(100, 50, 50.0)),
            patch.object(status_obj, "get_database_size", return_value="1 KB"),
            patch.object(status_obj, "get_database_stats") as mock_stats,
            patch.object(status_obj, "get_repos_txt_count", return_value=1),
            patch.object(status_obj, "get_repository_count", return_value=1),
        ):
            mock_stats.return_value = {
                "processed_files": 10,
                "failed_files": 0,
                "total_samples": 100,
                "total_turns": 200,
                "last_activity": "2023-01-01T12:00:00",
            }

            panel = status_obj._get_status_panel()
            assert panel is not None

    def test_display_real_time_status(self, status_obj):
        # Mock Live display
        with (
            patch("src.pipeline.realtime_status.Live"),
            patch.object(status_obj, "_get_status_panel"),
        ):
            status_obj.display_real_time_status(duration=1)

    def test_cli(self, status_obj):
        with patch("src.pipeline.realtime_status.RealTimeStatus") as mock_cls:
            mock_instance = mock_cls.return_value
            show_realtime_status(status_obj.config, status_obj.data_dir, 1)
            mock_instance.display_real_time_status.assert_called_with(duration=1)
