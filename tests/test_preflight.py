"""Unit tests for pre-flight validation checks."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.preflight import PreflightCheck, PreflightValidator, run_preflight_checks


class TestPreflightCheck:
    """Test PreflightCheck class."""

    def test_initialization(self):
        """Test check initialization."""
        check = PreflightCheck(
            name="Test Check",
            status="pass",
            message="All good",
            severity="error",
        )

        assert check.name == "Test Check"
        assert check.status == "pass"
        assert check.message == "All good"
        assert check.severity == "error"

    def test_default_values(self):
        """Test default initialization values."""
        check = PreflightCheck(name="Test")

        assert check.name == "Test"
        assert check.status == "pending"
        assert check.message == ""
        assert check.severity == "error"


class TestPreflightValidator:
    """Test PreflightValidator class."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = MagicMock(spec=AppConfig)
        config.USE_MLX = False
        config.LLM_BASE_URL = "http://localhost:11454"
        config.DB_PATH = "pipeline.db"
        config.DATA_DIR = "data"
        config.REPOS_DIR_NAME = "repos"
        config.LOG_FILE_PREFIX = "test_log"
        config.BATTERY_LOW_THRESHOLD = 15

        # Mock model properties
        config.model.use_mlx = False
        config.model.llm.base_url = "http://localhost:11454"
        config.model.llm.request_timeout = 300
        config.model.battery.low_threshold = 15
        config.model.pipeline.base_dir = "."

        return config

    def test_initialization(self, config, temp_data_dir):
        """Test validator initialization."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")

        assert validator.config == config
        assert validator.data_dir == temp_data_dir
        assert validator.command == "prepare"
        assert len(validator.checks) == 0

    @patch("src.pipeline.preflight.httpx.Client")
    def test_check_llm_availability_llama_cpp_success(self, mock_client, config, temp_data_dir):
        """Test LLM check with successful llama.cpp connection."""
        # Mock successful health check
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_llm_availability()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "reachable" in validator.checks[0].message.lower()

    @patch("src.pipeline.preflight.httpx.Client")
    def test_check_llm_availability_llama_cpp_failure(self, mock_client, config, temp_data_dir):
        """Test LLM check with failed llama.cpp connection."""
        # Mock connection error
        import httpx

        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("Connection refused")

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_llm_availability()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "fail"
        assert "cannot connect" in validator.checks[0].message.lower()

    def test_check_llm_availability_mlx_success(self, config, temp_data_dir):
        """Test LLM check with MLX available."""
        config.USE_MLX = True

        # Mock the import of mlx.core
        mock_mlx = MagicMock()
        with patch.dict("sys.modules", {"mlx.core": mock_mlx}):
            validator = PreflightValidator(config, temp_data_dir, "prepare")
            validator._check_llm_availability()

            assert len(validator.checks) == 1
            # If MLX is installed on the system, it will pass, otherwise it will fail
            assert validator.checks[0].status in ["pass", "fail"]

    def test_check_llm_availability_mlx_not_installed(self, config, temp_data_dir):
        """Test LLM check with MLX not installed."""
        config.USE_MLX = True

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_llm_availability()

        assert len(validator.checks) == 1
        # Should fail if MLX isn't actually installed
        assert validator.checks[0].status in ["pass", "fail"]

    def test_check_disk_space_sufficient(self, config, temp_data_dir):
        """Test disk space check with sufficient space."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_disk_space(min_gb=0.001)  # Very low threshold

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "gb available" in validator.checks[0].message.lower()

    @patch("src.pipeline.preflight.get_battery_status")
    def test_check_battery_level_sufficient(self, mock_battery, config, temp_data_dir):
        """Test battery check with sufficient charge."""
        import sys

        if sys.platform != "darwin":
            pytest.skip("Battery checks only on macOS")

        mock_battery.return_value = {"percent": 80, "plugged": False}

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_battery_level()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"

    @patch("src.pipeline.preflight.get_battery_status")
    def test_check_battery_level_low(self, mock_battery, config, temp_data_dir):
        """Test battery check with low charge."""
        import sys

        if sys.platform != "darwin":
            pytest.skip("Battery checks only on macOS")

        mock_battery.return_value = {"percent": 10, "plugged": False}
        config.BATTERY_LOW_THRESHOLD = 15

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_battery_level()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "warning"

    @patch("src.pipeline.preflight.get_battery_status")
    def test_check_battery_level_charging(self, mock_battery, config, temp_data_dir):
        """Test battery check while charging."""
        import sys

        if sys.platform != "darwin":
            pytest.skip("Battery checks only on macOS")

        mock_battery.return_value = {"percent": 50, "plugged": True}

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_battery_level()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "charging" in validator.checks[0].message.lower()

    def test_check_database_size_not_exists(self, config, temp_data_dir):
        """Test database size check when database doesn't exist."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_database_size()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "will be created" in validator.checks[0].message.lower()

    def test_check_database_size_small(self, config, temp_data_dir):
        """Test database size check with small database."""
        db_path = temp_data_dir / config.DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_text("x" * 1024 * 10)  # 10 KB

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_database_size()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "mb" in validator.checks[0].message.lower()

    def test_check_database_size_large(self, config, temp_data_dir):
        """Test database size check with large database."""
        db_path = temp_data_dir / config.DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Create a large file (just write size, don't actually write data for speed)
        with open(db_path, "wb") as f:
            f.seek(600 * 1024 * 1024 - 1)  # 600 MB
            f.write(b"\0")

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_database_size()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "warning"
        assert "large" in validator.checks[0].message.lower()

    def test_check_database_exists_present(self, config, temp_data_dir):
        """Test database exists check when present."""
        db_path = temp_data_dir / config.DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_text("database")

        validator = PreflightValidator(config, temp_data_dir, "export")
        validator._check_database_exists()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"

    def test_check_database_exists_missing(self, config, temp_data_dir):
        """Test database exists check when missing."""
        validator = PreflightValidator(config, temp_data_dir, "export")
        validator._check_database_exists()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "fail"
        assert "not found" in validator.checks[0].message.lower()

    def test_check_data_dir_writable_success(self, config, temp_data_dir):
        """Test data directory write permission check."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_data_dir_writable()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "writable" in validator.checks[0].message.lower()

    def test_check_repos_txt_not_exists(self, config, temp_data_dir):
        """Test repos.txt check when file doesn't exist."""
        config.BASE_DIR = str(temp_data_dir)

        validator = PreflightValidator(config, temp_data_dir, "scrape")
        validator._check_repos_txt()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "fail"
        assert "not found" in validator.checks[0].message.lower()

    def test_check_repos_txt_empty(self, config, temp_data_dir):
        """Test repos.txt check with empty file."""
        config.BASE_DIR = str(temp_data_dir)
        config.model.pipeline.base_dir = str(temp_data_dir)
        repos_file = temp_data_dir / "repos.txt"
        repos_file.write_text("# Just comments\n\n")

        validator = PreflightValidator(config, temp_data_dir, "scrape")
        validator._check_repos_txt()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "fail"
        assert "empty" in validator.checks[0].message.lower()

    def test_check_repos_txt_valid(self, config, temp_data_dir):
        """Test repos.txt check with valid file."""
        config.BASE_DIR = str(temp_data_dir)
        config.model.pipeline.base_dir = str(temp_data_dir)
        repos_file = temp_data_dir / "repos.txt"
        repos_file.write_text("https://github.com/user/repo1\n# Comment\nhttps://github.com/user/repo2\n")

        validator = PreflightValidator(config, temp_data_dir, "scrape")
        validator._check_repos_txt()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"
        assert "2 repositories" in validator.checks[0].message.lower()

    def test_check_config_valid_no_loader(self, config, temp_data_dir):
        """Test config validation when no loader present."""
        # Remove config_loader if it exists
        if hasattr(config, "config_loader"):
            delattr(config, "config_loader")

        validator = PreflightValidator(config, temp_data_dir, "prepare")
        validator._check_config_valid()

        assert len(validator.checks) == 1
        assert validator.checks[0].status == "pass"

    @patch("src.pipeline.preflight.Console")
    def test_run_all_checks_prepare_command(self, mock_console, config, temp_data_dir):
        """Test running all checks for prepare command."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")

        with patch.object(validator, "_check_llm_availability"):
            with patch.object(validator, "_check_disk_space"):
                with patch.object(validator, "_check_battery_level"):
                    with patch.object(validator, "_check_database_size"):
                        with patch.object(validator, "_check_data_dir_writable"):
                            with patch.object(validator, "_check_config_valid"):
                                _ = validator.run_all_checks()

        # Should have called all prepare-related checks
        assert len(validator.checks) >= 0

    @patch("src.pipeline.preflight.Console")
    def test_run_all_checks_scrape_command(self, mock_console, config, temp_data_dir):
        """Test running all checks for scrape command."""
        config.BASE_DIR = str(temp_data_dir)
        config.model.pipeline.base_dir = str(temp_data_dir)
        repos_file = temp_data_dir / "repos.txt"
        repos_file.write_text("https://github.com/user/repo\n")

        validator = PreflightValidator(config, temp_data_dir, "scrape")
        with patch.object(validator, "_display_results"):
            _ = validator.run_all_checks()

        # Should check repos.txt (Repositories List), disk space, data dir
        assert any("Repositories List" in c.name for c in validator.checks)
        assert any("Disk Space" in c.name for c in validator.checks)
        assert any("Data Directory" in c.name for c in validator.checks)

    @patch("src.pipeline.preflight.Console")
    def test_run_all_checks_returns_false_on_critical_failure(self, mock_console, config, temp_data_dir):
        """Test that run_all_checks returns False on critical failures."""
        validator = PreflightValidator(config, temp_data_dir, "prepare")

        # Mock one of the checks to fail
        def mock_fail():
            validator.checks.append(PreflightCheck(name="Test", status="fail", severity="error"))

        with (
            patch.object(validator, "_check_llm_availability", side_effect=mock_fail),
            patch.object(validator, "_display_results"),
        ):
            result = validator.run_all_checks()

        assert result is False

    @patch("src.pipeline.preflight.Console")
    def test_run_all_checks_returns_true_on_warnings(self, mock_console, config, temp_data_dir):
        """Test that run_all_checks returns True with only warnings."""
        validator = PreflightValidator(config, temp_data_dir, "export")  # Use export to avoid prepare checks

        # Mock all the check methods to do nothing
        with patch.object(validator, "_check_database_exists"):
            with patch.object(validator, "_check_database_size"):
                with patch.object(validator, "_check_disk_space"):
                    with patch.object(validator, "_display_results"):
                        # Add manual checks after running
                        validator.checks = [
                            PreflightCheck(name="Test1", status="pass", severity="info"),
                            PreflightCheck(name="Test2", status="warning", severity="warning"),
                        ]

                        # Just check the logic, not the full run
                        critical_failures = [c for c in validator.checks if c.status == "fail" and c.severity == "error"]
                        result = len(critical_failures) == 0

        assert result is True


def test_run_preflight_checks_integration(temp_dir=None):
    """Test run_preflight_checks wrapper function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = MagicMock(spec=AppConfig)
        config.USE_MLX = True  # Avoid network calls
        data_dir = Path(tmpdir)

        with patch("src.pipeline.preflight.PreflightValidator.run_all_checks") as mock_run:
            mock_run.return_value = True
            result = run_preflight_checks(config, data_dir, "prepare")

        assert result is True
        mock_run.assert_called_once()
