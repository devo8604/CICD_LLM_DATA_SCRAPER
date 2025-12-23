"""Unit tests for status and statistics utilities."""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.utils.status_utils import PipelineStatistics, PipelineStatus


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config():
    """Create a test configuration."""
    config = MagicMock(spec=AppConfig)
    config.BASE_DIR = tempfile.mkdtemp()
    config.DATA_DIR = "data"
    config.REPOS_DIR_NAME = "repos"
    config.DB_PATH = "pipeline.db"

    # Mock model properties accessed by new code
    config.model.pipeline.base_dir = config.BASE_DIR
    config.model.pipeline.repos_dir_name = config.REPOS_DIR_NAME

    return config


@pytest.fixture
def test_db(temp_data_dir, config):
    """Create a test database with sample data."""
    db_path = temp_data_dir / config.DB_PATH

    # Create database connection directly
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables (DBManager should handle this, but ensure they exist)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS TrainingSamples (
            sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_source VARCHAR(512),
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model_type_intended VARCHAR(100),
            sample_quality_score REAL,
            is_multiturn BOOLEAN
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ConversationTurns (
            turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id INTEGER,
            turn_index INTEGER,
            role VARCHAR(50),
            content TEXT,
            is_label BOOLEAN,
            metadata_json TEXT,
            FOREIGN KEY (sample_id) REFERENCES TrainingSamples(sample_id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS FileHashes (
            file_path TEXT PRIMARY KEY,
            content_hash TEXT,
            last_processed DATETIME,
            sample_id INTEGER,
            FOREIGN KEY (sample_id) REFERENCES TrainingSamples(sample_id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS FailedFiles (
            failed_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            reason TEXT,
            failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Insert test samples
    for i in range(10):
        cursor.execute(
            """
            INSERT INTO TrainingSamples
            (dataset_source, sample_quality_score, is_multiturn)
            VALUES (?, ?, ?)
            """,
            (f"/path/to/repos/org{i % 3}/repo{i}/file.py", 0.8 + (i % 3) * 0.05, False),
        )

        sample_id = cursor.lastrowid

        # Insert conversation turns
        cursor.execute(
            """
            INSERT INTO ConversationTurns
            (sample_id, turn_index, role, content, is_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sample_id, 0, "user", f"Question {i}", False),
        )

        cursor.execute(
            """
            INSERT INTO ConversationTurns
            (sample_id, turn_index, role, content, is_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sample_id, 1, "assistant", f"Answer {i}", True),
        )

        # Insert file hash
        cursor.execute(
            """
            INSERT INTO FileHashes
            (file_path, content_hash, last_processed, sample_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                f"/path/to/repos/org{i % 3}/repo{i}/file.py",
                f"hash{i}",
                datetime.now().isoformat(),
                sample_id,
            ),
        )

    # Insert some failed files
    for i in range(3):
        cursor.execute(
            """
            INSERT INTO FailedFiles (file_path, reason)
            VALUES (?, ?)
            """,
            (f"/path/to/failed/file{i}.py", f"Error reason {i}"),
        )

    conn.commit()
    conn.close()

    return db_path


class TestPipelineStatus:
    """Test PipelineStatus class."""

    def test_get_database_stats_empty(self, config, temp_data_dir):
        """Test getting stats from non-existent database."""
        status = PipelineStatus(config, temp_data_dir)
        stats = status.get_database_stats()

        assert stats["total_samples"] == 0
        assert stats["total_turns"] == 0
        assert stats["failed_files"] == 0
        assert stats["processed_files"] == 0
        assert stats["last_activity"] is None

    def test_get_database_stats_with_data(self, config, temp_data_dir, test_db):
        """Test getting stats from populated database."""
        status = PipelineStatus(config, temp_data_dir)
        stats = status.get_database_stats()

        assert stats["total_samples"] == 10
        assert stats["total_turns"] == 20  # 2 turns per sample
        assert stats["failed_files"] == 3
        assert stats["processed_files"] == 10
        assert stats["last_activity"] is not None

    def test_get_repository_count_empty(self, config, temp_data_dir):
        """Test repository count with no repos."""
        status = PipelineStatus(config, temp_data_dir)
        count = status.get_repository_count()

        assert count == 0

    def test_get_repository_count_with_repos(self, config, temp_data_dir):
        """Test repository count with sample repos."""
        # Create fake repository structure
        repos_dir = Path(config.BASE_DIR) / config.REPOS_DIR_NAME
        repos_dir.mkdir(parents=True, exist_ok=True)

        # Create org/repo structure
        for i in range(3):
            org_dir = repos_dir / f"org{i}"
            org_dir.mkdir(exist_ok=True)
            for j in range(2):
                repo_dir = org_dir / f"repo{j}"
                repo_dir.mkdir(exist_ok=True)

        status = PipelineStatus(config, temp_data_dir)
        count = status.get_repository_count()

        assert count == 6  # 3 orgs * 2 repos each

    def test_get_database_size(self, config, temp_data_dir, test_db):
        """Test database size calculation."""
        status = PipelineStatus(config, temp_data_dir)
        size_str = status.get_database_size()

        assert size_str.endswith(" KB") or size_str.endswith(" B")
        assert size_str != "0 B"

    def test_get_repos_txt_count_missing(self, config, temp_data_dir):
        """Test repos.txt count when file doesn't exist."""
        status = PipelineStatus(config, temp_data_dir)
        count = status.get_repos_txt_count()

        assert count == 0

    def test_get_repos_txt_count_with_repos(self, config, temp_data_dir):
        """Test repos.txt count with sample repos."""
        repos_file = Path(config.BASE_DIR) / "repos.txt"
        repos_file.write_text("https://github.com/user/repo1\nhttps://github.com/user/repo2\n# Comment line\n\nhttps://github.com/user/repo3\n")

        status = PipelineStatus(config, temp_data_dir)
        count = status.get_repos_txt_count()

        assert count == 3

    def test_get_next_recommended_action_no_repos_txt(self, config, temp_data_dir):
        """Test recommendation when repos.txt doesn't exist."""
        status = PipelineStatus(config, temp_data_dir)
        db_stats = status.get_database_stats()
        action = status.get_next_recommended_action(db_stats)

        assert "repos.txt" in action.lower()

    def test_get_next_recommended_action_no_cloned_repos(self, config, temp_data_dir):
        """Test recommendation when no repos are cloned."""
        # Create repos.txt
        repos_file = Path(config.BASE_DIR) / "repos.txt"
        repos_file.write_text("https://github.com/user/repo1\n")

        status = PipelineStatus(config, temp_data_dir)
        db_stats = status.get_database_stats()
        action = status.get_next_recommended_action(db_stats)

        assert "scrape" in action.lower()

    def test_get_next_recommended_action_with_failed_files(self, config, temp_data_dir, test_db):
        """Test recommendation when there are failed files."""
        # Create repos structure
        repos_dir = Path(config.BASE_DIR) / config.REPOS_DIR_NAME
        repos_dir.mkdir(parents=True, exist_ok=True)
        (repos_dir / "org1").mkdir(exist_ok=True)
        (repos_dir / "org1" / "repo1").mkdir(exist_ok=True)

        # Create repos.txt
        repos_file = Path(config.BASE_DIR) / "repos.txt"
        repos_file.write_text("https://github.com/org1/repo1\n")

        status = PipelineStatus(config, temp_data_dir)
        db_stats = status.get_database_stats()
        action = status.get_next_recommended_action(db_stats)

        assert "retry" in action.lower()

    def test_format_bytes(self):
        """Test byte formatting."""
        assert PipelineStatus._format_bytes(500) == "500.00 B"
        assert PipelineStatus._format_bytes(1024) == "1.00 KB"
        assert PipelineStatus._format_bytes(1024 * 1024) == "1.00 MB"
        assert PipelineStatus._format_bytes(1024 * 1024 * 1024) == "1.00 GB"

    @patch("src.utils.status_utils.Console")
    def test_display_status(self, mock_console, config, temp_data_dir, test_db):
        """Test status display output."""
        status = PipelineStatus(config, temp_data_dir)
        status.display_status()

        # Verify console.print was called
        mock_console.return_value.print.assert_called()


class TestPipelineStatistics:
    """Test PipelineStatistics class."""

    def test_get_repository_breakdown_empty(self, config, temp_data_dir):
        """Test repository breakdown with no data."""
        stats = PipelineStatistics(config, temp_data_dir)
        breakdown = stats.get_repository_breakdown()

        assert breakdown == []

    def test_get_repository_breakdown_with_data(self, config, temp_data_dir, test_db):
        """Test repository breakdown with sample data."""
        stats = PipelineStatistics(config, temp_data_dir)
        breakdown = stats.get_repository_breakdown()

        assert len(breakdown) > 0
        # Check structure of returned data
        for repo, sample_count, turn_count in breakdown:
            assert isinstance(repo, str)
            assert isinstance(sample_count, int)
            assert isinstance(turn_count, int)
            assert sample_count > 0
            assert turn_count > 0

    def test_get_quality_distribution_empty(self, config, temp_data_dir):
        """Test quality distribution with no data."""
        stats = PipelineStatistics(config, temp_data_dir)
        distribution = stats.get_quality_distribution()

        assert distribution == []

    def test_get_quality_distribution_with_data(self, config, temp_data_dir, test_db):
        """Test quality distribution with sample data."""
        stats = PipelineStatistics(config, temp_data_dir)
        distribution = stats.get_quality_distribution()

        assert len(distribution) > 0
        # Check structure
        for score, count in distribution:
            assert isinstance(score, float)
            assert isinstance(count, int)
            assert count > 0

    def test_get_failed_files_details_empty(self, config, temp_data_dir):
        """Test failed files details with no failures."""
        stats = PipelineStatistics(config, temp_data_dir)
        failed = stats.get_failed_files_details()

        assert failed == []

    def test_get_failed_files_details_with_data(self, config, temp_data_dir, test_db):
        """Test failed files details with sample data."""
        stats = PipelineStatistics(config, temp_data_dir)
        failed = stats.get_failed_files_details()

        assert len(failed) == 3
        for file_path, reason, failed_at in failed:
            assert isinstance(file_path, str)
            assert isinstance(reason, str)
            assert isinstance(failed_at, str)

    @patch("src.utils.status_utils.Console")
    def test_display_statistics_table(self, mock_console, config, temp_data_dir, test_db):
        """Test statistics display in table format."""
        stats = PipelineStatistics(config, temp_data_dir)
        stats.display_statistics(output_format="table")

        # Verify console.print was called multiple times (for each table)
        assert mock_console.return_value.print.call_count > 0

    def test_display_statistics_json(self, config, temp_data_dir, test_db, capsys):
        """Test statistics display in JSON format."""
        stats = PipelineStatistics(config, temp_data_dir)
        stats.display_statistics(output_format="json")

        # Capture output and verify it's valid JSON
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)

        assert "repositories" in data
        assert "quality_distribution" in data
        assert "failed_files" in data
        assert isinstance(data["repositories"], list)
        assert isinstance(data["quality_distribution"], list)
        assert isinstance(data["failed_files"], list)
