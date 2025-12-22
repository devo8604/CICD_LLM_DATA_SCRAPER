from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.utils.memory_manager import (
    FileReader,
    LargeFileManager,
    MemoryManager,
    get_memory_manager,
)


class TestMemoryManager:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.MAX_FILE_SIZE = 1000
        config.CHUNK_READ_SIZE = 100
        return config

    @pytest.fixture
    def memory_manager(self, mock_config):
        return MemoryManager(mock_config)

    @patch("psutil.virtual_memory")
    @patch("psutil.Process")
    @patch("os.getpid")
    def test_get_memory_usage(self, mock_pid, mock_process, mock_vmem, memory_manager):
        mock_vmem.return_value = MagicMock(total=1000, available=500, used=500, percent=50.0)
        mock_process_instance = MagicMock()
        mock_process_instance.memory_info.return_value.rss = 100
        mock_process.return_value = mock_process_instance

        usage = memory_manager.get_memory_usage()

        assert usage.total == 1000
        assert usage.available == 500
        assert usage.process_memory == 100
        assert usage.process_percent == 10.0

    def test_is_memory_low(self, memory_manager):
        with patch.object(memory_manager, "get_memory_usage") as mock_usage:
            mock_usage.return_value = MagicMock(percent_used=90.0)
            assert memory_manager.is_memory_low(threshold=0.8) is True

            mock_usage.return_value = MagicMock(percent_used=70.0)
            assert memory_manager.is_memory_low(threshold=0.8) is False

    def test_is_process_memory_high(self, memory_manager):
        with patch.object(memory_manager, "get_memory_usage") as mock_usage:
            mock_usage.return_value = MagicMock(process_percent=80.0)
            assert memory_manager.is_process_memory_high(threshold=0.75) is True

    @patch("src.utils.memory_manager.gc")
    def test_force_garbage_collection(self, mock_gc, memory_manager):
        mock_gc.collect.return_value = 10
        assert memory_manager.force_garbage_collection() == 10
        mock_gc.collect.assert_called()

    def test_memory_buffer(self, memory_manager):
        with patch.object(memory_manager, "get_memory_usage") as mock_usage:
            mock_usage.return_value = MagicMock(percent_used=50.0)

            with memory_manager.memory_buffer("test_buf", 50) as buf:
                assert isinstance(buf, bytearray)
                assert len(buf) == 50
                assert "test_buf" in memory_manager._active_buffers

            assert "test_buf" not in memory_manager._active_buffers

    def test_memory_buffer_high_memory(self, memory_manager):
        with (
            patch.object(memory_manager, "get_memory_usage") as mock_usage,
            patch.object(memory_manager, "force_garbage_collection") as mock_gc,
        ):
            mock_usage.return_value = MagicMock(percent_used=95.0)

            with memory_manager.memory_buffer("test_buf", 50):
                pass

            mock_gc.assert_called()

    def test_memory_buffer_cap_size(self, memory_manager):
        memory_manager._max_buffer_size = 100
        with patch.object(memory_manager, "get_memory_usage") as mock_usage:
            mock_usage.return_value = MagicMock(percent_used=50.0)

            with memory_manager.memory_buffer("test_buf", 200) as buf:
                assert len(buf) == 100

    def test_monitor_memory(self, memory_manager):
        with (
            patch.object(memory_manager, "get_memory_usage") as mock_usage,
            patch.object(memory_manager, "force_garbage_collection") as mock_gc,
        ):
            # First call (before): 100 used, Second call (after): 200 used
            mock_usage.side_effect = [
                MagicMock(used=100, percent_used=10.0),
                MagicMock(used=100 + 60 * 1024 * 1024, percent_used=20.0),  # > 50MB diff
            ]

            with memory_manager.monitor_memory("op"):
                pass

            mock_gc.assert_called()

    def test_ensure_memory_available(self, memory_manager):
        with (
            patch.object(memory_manager, "get_memory_usage") as mock_usage,
            patch.object(memory_manager, "force_garbage_collection") as mock_gc,
        ):
            # Case 1: Enough memory
            mock_usage.return_value = MagicMock(available=200 * 1024 * 1024)
            assert memory_manager.ensure_memory_available(100) is True
            mock_gc.assert_not_called()

            # Case 2: Not enough, GC helps
            mock_usage.side_effect = [
                MagicMock(available=50 * 1024 * 1024),  # Check 1
                MagicMock(available=150 * 1024 * 1024),  # Check 2 (after GC)
            ]
            assert memory_manager.ensure_memory_available(100) is True
            mock_gc.assert_called()

    def test_ensure_memory_available_fail(self, memory_manager):
        with (
            patch.object(memory_manager, "get_memory_usage") as mock_usage,
            patch.object(memory_manager, "force_garbage_collection"),
            patch("time.sleep"),
        ):
            mock_usage.return_value = MagicMock(available=10 * 1024 * 1024)  # Always low

            assert memory_manager.ensure_memory_available(100) is False


class TestFileReader:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.MAX_FILE_SIZE = 1000
        config.CHUNK_READ_SIZE = 100
        return config

    @pytest.fixture
    def memory_manager(self):
        return MagicMock(spec=MemoryManager)

    @pytest.fixture
    def file_reader(self, mock_config, memory_manager):
        return FileReader(mock_config, memory_manager)

    @patch("os.path.getsize")
    def test_read_file_chunks_too_large(self, mock_getsize, file_reader):
        mock_getsize.return_value = 2000  # > 1000
        with pytest.raises(ValueError, match="File too large"):
            file_reader.read_file_chunks("file.txt")

    @patch("os.path.getsize")
    def test_read_file_chunks(self, mock_getsize, file_reader):
        mock_getsize.return_value = 500
        file_content = "content" * 10

        with patch("builtins.open", mock_open(read_data=file_content)):
            chunks = file_reader.read_file_chunks("file.txt")
            assert "".join(chunks) == file_content

    @patch("os.path.getsize")
    def test_read_file_chunks_split_large_content(self, mock_getsize, file_reader):
        mock_getsize.return_value = 500
        # Config chunk size is 100. Split logic kicks in if content > chunk * 10 (1000)
        # Wait, the split logic is: if len(content) > chunk_size * 10

        # Let's verify the logic in the source code:
        # if len(content) > chunk_size * 10: ...

        chunk_size = 10
        file_reader.config.CHUNK_READ_SIZE = chunk_size

        # Make content large enough
        content = "a" * (chunk_size * 10 + 5)

        with patch("builtins.open", mock_open(read_data=content)):
            chunks = file_reader.read_file_chunks("file.txt")
            # Should be split into chunks of size (chunk_size * 10) = 100
            assert len(chunks) == 2  # 100 + 5
            assert len(chunks[0]) == 100
            assert len(chunks[1]) == 5

    @patch("os.path.getsize")
    def test_read_file_with_memory_protection(self, mock_getsize, file_reader):
        mock_getsize.return_value = 100
        file_reader.memory_manager.ensure_memory_available.return_value = True

        with patch("builtins.open", mock_open(read_data="content")):
            content = file_reader.read_file_with_memory_protection("file.txt")
            assert content == "content"

    @patch("os.path.getsize")
    def test_read_file_with_memory_protection_too_large(self, mock_getsize, file_reader):
        mock_getsize.return_value = 20 * 1024 * 1024  # 20MB
        # Default max_size_mb is 10.0
        content = file_reader.read_file_with_memory_protection("file.txt")
        assert content is None

    @patch("os.path.getsize")
    def test_read_file_with_memory_protection_no_memory(self, mock_getsize, file_reader):
        mock_getsize.return_value = 100
        file_reader.memory_manager.ensure_memory_available.return_value = False

        content = file_reader.read_file_with_memory_protection("file.txt")
        assert content is None


class TestLargeFileManager:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.MAX_FILE_SIZE = 1000
        config.CHUNK_READ_SIZE = 100
        return config

    @pytest.fixture
    def large_file_manager(self, mock_config):
        return LargeFileManager(mock_config)

    def test_cleanup_memory(self, large_file_manager):
        with (
            patch.object(large_file_manager.memory_manager, "clear_buffers") as mock_clear,
            patch.object(large_file_manager.memory_manager, "force_garbage_collection") as mock_gc,
        ):
            large_file_manager.cleanup_memory()
            mock_clear.assert_called()
            mock_gc.assert_called()

    @patch("os.path.getsize")
    def test_process_large_file(self, mock_getsize, large_file_manager):
        mock_getsize.return_value = 500

        with (
            patch.object(
                large_file_manager.file_reader,
                "read_file_with_memory_protection",
                return_value="content",
            ),
            patch.object(large_file_manager.memory_manager, "monitor_memory"),
        ):
            processor = MagicMock()
            result = large_file_manager.process_large_file("file.txt", processor)

            assert result is True
            processor.assert_called_with("content")

    @patch("os.path.getsize")
    def test_process_large_file_too_large(self, mock_getsize, large_file_manager):
        mock_getsize.return_value = 2000  # > 1000

        result = large_file_manager.process_large_file("file.txt", lambda x: None)
        assert result is False

    @patch("os.path.getsize")
    def test_process_large_file_read_fail(self, mock_getsize, large_file_manager):
        mock_getsize.return_value = 500

        with patch.object(
            large_file_manager.file_reader,
            "read_file_with_memory_protection",
            return_value=None,
        ):
            result = large_file_manager.process_large_file("file.txt", lambda x: None)
            assert result is False


def test_get_memory_manager():
    # Need to reset the singleton for the test or it might be set by previous tests (if they used it, but they didn't)
    # The module level variable _memory_manager_instance persists

    # We can patch the module variable, but since it's global, we might need to access it via the module
    import src.utils.memory_manager

    src.utils.memory_manager._memory_manager_instance = None

    config = MagicMock(spec=AppConfig)
    manager1 = get_memory_manager(config)
    manager2 = get_memory_manager(config)

    assert isinstance(manager1, LargeFileManager)
    assert manager1 is manager2
