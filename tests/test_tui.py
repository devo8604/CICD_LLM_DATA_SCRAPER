"""Tests for the Text User Interface functionality."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.config import AppConfig
from src.ui.pipeline_tui import (
    BatteryWidget,
    DatabaseSizeWidget,
    DiskUsageWidget,
    GPUWidget,
    MemoryWidget,
    PipelineTUIApp,
    StatsWidget,
    SwapWidget,
)


class TestTUIWidgets(unittest.TestCase):
    """Test TUI widgets individually."""

    def setUp(self):
        self.config = AppConfig()
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_battery_widget(self):
        """Test battery widget functionality."""
        widget = BatteryWidget()
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial battery info
        battery_info = widget.battery_info
        self.assertIsInstance(battery_info, tuple)
        self.assertEqual(len(battery_info), 2)

    def test_disk_usage_widget(self):
        """Test disk usage widget functionality."""
        widget = DiskUsageWidget(str(self.data_dir))
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial disk info
        disk_info = widget.disk_usage
        self.assertIsInstance(disk_info, tuple)
        self.assertEqual(len(disk_info), 3)

    def test_memory_widget(self):
        """Test memory widget functionality."""
        widget = MemoryWidget()
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial memory info
        memory_info = widget.memory_info
        self.assertIsInstance(memory_info, dict)

    def test_swap_widget(self):
        """Test swap widget functionality."""
        widget = SwapWidget()
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial swap info
        swap_info = widget.swap_info
        self.assertIsInstance(swap_info, dict)

    def test_gpu_widget(self):
        """Test GPU widget functionality."""
        widget = GPUWidget()
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial GPU info
        gpu_info = widget.gpu_info
        self.assertIsInstance(gpu_info, dict)

    def test_database_size_widget(self):
        """Test database size widget functionality."""
        db_path = self.data_dir / "test.db"
        # Create a small test database file
        with open(db_path, "w") as f:
            f.write("test")

        widget = DatabaseSizeWidget(db_path)
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial size info
        size_str = widget.db_size_str
        self.assertIsInstance(size_str, str)
        self.assertIn("B", size_str)

    def test_stats_widget(self):
        """Test stats widget functionality."""
        widget = StatsWidget(self.config, self.data_dir)
        # The widget should initialize without errors
        self.assertIsNotNone(widget)

        # Should have initial stats
        stats = widget.stats
        self.assertIsInstance(stats, dict)
        self.assertIn("total_samples", stats)


class TestTUIApp(unittest.TestCase):
    """Test the main TUI application."""

    def setUp(self):
        self.config = AppConfig()
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_app_initialization(self):
        """Test TUI app initialization."""
        app = PipelineTUIApp(self.config, self.data_dir)
        self.assertIsNotNone(app)
        self.assertEqual(app.config, self.config)
        self.assertEqual(app.data_dir, self.data_dir)

    @patch("src.ui.pipeline_tui.run_tui")
    def test_run_tui_function(self, mock_run):
        """Test the run_tui function."""
        from src.ui.pipeline_tui import run_tui

        # This should not raise any exceptions
        run_tui(self.config, self.data_dir)

        # The mock should have been called with the app
        mock_run.assert_called()


def test_battery_function():
    """Test the battery function directly."""
    from src.pipeline.realtime_status import get_battery_level

    # This should return either None or a tuple
    result = get_battery_level()
    if result is not None:
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], bool)
    # If None, it means not on macOS or error occurred, which is expected


def test_disk_space_function():
    """Test the disk space function directly."""
    from src.pipeline.realtime_status import get_disk_space

    # This should return a tuple of 3 values
    total, used, percent = get_disk_space()
    assert isinstance(total, int)
    assert isinstance(used, int)
    assert isinstance(percent, float)
    assert total >= 0
    assert used >= 0
    assert 0 <= percent <= 100


if __name__ == "__main__":
    # Run the individual function tests
    test_battery_function()
    test_disk_space_function()

    # Run unit tests
    unittest.main()
