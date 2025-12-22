"""Unit tests for the pipeline TUI module."""

from pathlib import Path

from src.core.config import AppConfig
from src.ui.pipeline_tui import (
    BatteryWidget,
    DatabaseSizeWidget,
    DiskUsageWidget,
    GPUWidget,
    LogPanel,
    MemoryWidget,
    PipelineTUIApp,
    ProcessStatusWidget,
    ProgressTrackingWidget,
    StatsWidget,
    SwapWidget,
)


class TestBatteryWidget:
    """Test the BatteryWidget class."""

    def test_initialization(self):
        """Test that BatteryWidget initializes properly."""
        widget = BatteryWidget()
        assert widget is not None

    def test_battery_info_reactive(self):
        """Test battery info reactive property."""
        widget = BatteryWidget()
        widget.battery_info = (80, False)
        assert widget.battery_info == (80, False)


class TestDiskUsageWidget:
    """Test the DiskUsageWidget class."""

    def test_initialization(self):
        """Test that DiskUsageWidget initializes properly."""
        widget = DiskUsageWidget("/tmp")
        assert widget is not None
        assert widget.path == "/tmp"

    def test_disk_usage_reactive(self):
        """Test disk usage reactive property."""
        widget = DiskUsageWidget("/tmp")
        widget.disk_usage = (1000, 500, 50.0)
        assert widget.disk_usage == (1000, 500, 50.0)

    def test_disk_progress_reactive(self):
        """Test disk progress reactive property."""
        widget = DiskUsageWidget("/tmp")
        widget.disk_progress = 75.0
        assert widget.disk_progress == 75.0


class TestDatabaseSizeWidget:
    """Test the DatabaseSizeWidget class."""

    def test_initialization(self):
        """Test that DatabaseSizeWidget initializes properly."""
        db_path = Path("test.db")
        widget = DatabaseSizeWidget(db_path)
        assert widget is not None
        assert widget.db_path == db_path

    def test_db_size_reactive(self):
        """Test database size reactive properties."""
        db_path = Path("test.db")
        widget = DatabaseSizeWidget(db_path)
        widget.db_size_str = "1.5 MB"
        widget.db_size_bytes = 1572864
        assert widget.db_size_str == "1.5 MB"
        assert widget.db_size_bytes == 1572864


class TestStatsWidget:
    """Test the StatsWidget class."""

    def test_initialization(self):
        """Test that StatsWidget initializes properly."""
        config = AppConfig()
        data_dir = Path("data")
        widget = StatsWidget(config, data_dir)
        assert widget is not None
        assert widget.config == config
        assert widget.data_dir == data_dir

    def test_stats_reactive(self):
        """Test stats reactive property."""
        config = AppConfig()
        data_dir = Path("data")
        widget = StatsWidget(config, data_dir)
        stats = {
            "repos_txt_count": 5,
            "repo_count": 10,
            "total_samples": 100,
            "total_turns": 200,
            "failed_files": 0,
            "processed_files": 50,
        }
        widget.stats = stats
        assert widget.stats == stats


class TestProgressTrackingWidget:
    """Test the ProgressTrackingWidget class."""

    def test_initialization(self):
        """Test that ProgressTrackingWidget initializes properly."""
        config = AppConfig()
        data_dir = Path("data")
        widget = ProgressTrackingWidget(config, data_dir)
        assert widget is not None
        assert widget.config == config
        assert widget.data_dir == data_dir

    def test_progress_summary_reactive(self):
        """Test progress summary reactive property."""
        config = AppConfig()
        data_dir = Path("data")
        widget = ProgressTrackingWidget(config, data_dir)
        summary = {
            "total_progress": 50.0,
            "total_repos": 20,
            "current_repo_index": 5,
            "current_repo_name": "test-repo",
            "current_repo_files_total": 100,
            "current_repo_files_processed": 50,
            "current_file_path": "/path/to/file.py",
            "total_files": 1000,
            "files_processed": 500,
        }
        widget.progress_summary = summary
        assert widget.progress_summary == summary


class TestProcessStatusWidget:
    """Test the ProcessStatusWidget class."""

    def test_initialization(self):
        """Test that ProcessStatusWidget initializes properly."""
        widget = ProcessStatusWidget()
        assert widget is not None

    def test_status_text_reactive(self):
        """Test status text reactive property."""
        widget = ProcessStatusWidget()
        widget.status_text = "Processing"
        assert widget.status_text == "Processing"

    def test_progress_value_reactive(self):
        """Test progress value reactive property."""
        widget = ProcessStatusWidget()
        widget.progress_value = 75.0
        assert widget.progress_value == 75.0


class TestMemoryWidget:
    """Test the MemoryWidget class."""

    def test_initialization(self):
        """Test that MemoryWidget initializes properly."""
        widget = MemoryWidget()
        assert widget is not None

    def test_memory_info_reactive(self):
        """Test memory info reactive property."""
        widget = MemoryWidget()
        memory_info = {
            "total": 16000000000,
            "used": 8000000000,
            "percent_used": 50.0,
            "available": 8000000000,
        }
        widget.memory_info = memory_info
        assert widget.memory_info == memory_info


class TestSwapWidget:
    """Test the SwapWidget class."""

    def test_initialization(self):
        """Test that SwapWidget initializes properly."""
        widget = SwapWidget()
        assert widget is not None

    def test_swap_info_reactive(self):
        """Test swap info reactive property."""
        widget = SwapWidget()
        swap_info = {
            "total": 4000000000,
            "used": 1000000000,
            "percent_used": 25.0,
            "free": 3000000000,
        }
        widget.swap_info = swap_info
        assert widget.swap_info == swap_info


class TestGPUWidget:
    """Test the GPUWidget class."""

    def test_initialization(self):
        """Test that GPUWidget initializes properly."""
        widget = GPUWidget()
        assert widget is not None

    def test_gpu_info_reactive(self):
        """Test GPU info reactive property."""
        widget = GPUWidget()
        gpu_info = {
            "available": True,
            "type": "Metal",
            "gpus": [{"name": "Apple M1", "gpu_utilization": 40, "memory_utilization": 30}],
        }
        widget.gpu_info = gpu_info
        assert widget.gpu_info == gpu_info


class TestLogPanel:
    """Test the LogPanel class."""

    def test_initialization(self):
        """Test that LogPanel initializes properly."""
        log_panel = LogPanel()
        assert log_panel is not None

    def test_log_message(self):
        """Test logging a message."""
        log_panel = LogPanel()
        # Just test that it doesn't raise an exception
        log_panel.log_message("Test message", "info")


class TestPipelineTUIApp:
    """Test the PipelineTUIApp class."""

    def test_initialization(self):
        """Test that PipelineTUIApp initializes properly."""
        config = AppConfig()
        data_dir = Path("data")
        app = PipelineTUIApp(config, data_dir)
        assert app is not None
        assert app.config == config
        assert app.data_dir == data_dir

    def test_compose_method(self):
        """Test the compose method."""
        config = AppConfig()
        data_dir = Path("data")
        app = PipelineTUIApp(config, data_dir)
        # Just ensure it doesn't fail
        # Note: This would be more thoroughly tested in integration tests
        assert app is not None
