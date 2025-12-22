"""Enhanced memory management for large file processing."""

import gc
import logging
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psutil

from src.core.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class MemoryUsage:
    """Data class to represent memory usage statistics."""

    total: int
    available: int
    used: int
    percent_used: float
    process_memory: int
    process_percent: float


class MemoryManager:
    """Memory management utilities for large file processing."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._memory_threshold = config.MAX_FILE_SIZE  # Use config to determine threshold
        self._active_buffers: dict[str, Any] = {}
        self._buffer_sizes: dict[str, int] = {}
        self._max_buffer_size = config.CHUNK_READ_SIZE * 10  # 10x chunk size as max buffer

    def get_memory_usage(self) -> MemoryUsage:
        """Get current system and process memory usage."""
        # System memory
        svmem = psutil.virtual_memory()

        # Process memory
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss

        return MemoryUsage(
            total=svmem.total,
            available=svmem.available,
            used=svmem.used,
            percent_used=svmem.percent,
            process_memory=process_memory,
            process_percent=(process_memory / svmem.total) * 100,
        )

    def is_memory_low(self, threshold: float = 0.85) -> bool:
        """Check if system memory is running low."""
        usage = self.get_memory_usage()
        return usage.percent_used > threshold * 100

    def is_process_memory_high(self, threshold: float = 0.75) -> bool:
        """Check if process memory usage is high."""
        usage = self.get_memory_usage()
        return usage.process_percent > threshold * 100

    @contextmanager
    def memory_buffer(self, name: str, size: int):
        """Context manager to manage memory buffers."""
        try:
            # Check if we have enough memory before allocating
            usage = self.get_memory_usage()
            if usage.percent_used > 90:
                logger.warning(f"High memory usage detected: {usage.percent_used:.1f}%")
                self.force_garbage_collection()

            # Limit buffer size
            if size > self._max_buffer_size:
                logger.warning(f"Buffer size {size} exceeds max allowed {self._max_buffer_size}")
                size = self._max_buffer_size

            # Create buffer
            buffer = bytearray(size)
            self._active_buffers[name] = buffer
            self._buffer_sizes[name] = size

            yield buffer
        finally:
            # Clean up buffer
            if name in self._active_buffers:
                del self._active_buffers[name]
                del self._buffer_sizes[name]

    def force_garbage_collection(self) -> int:
        """Force garbage collection and return number of collected objects."""
        collected = gc.collect()
        logger.debug(f"Garbage collection: {collected} objects collected")
        return collected

    def clear_buffers(self):
        """Clear all active buffers to free memory."""
        for name in list(self._active_buffers.keys()):
            del self._active_buffers[name]
            del self._buffer_sizes[name]
        self.force_garbage_collection()

    @contextmanager
    def monitor_memory(self, operation_name: str = "operation"):
        """Context manager to monitor memory before and after an operation."""
        before_usage = self.get_memory_usage()
        logger.debug(f"Memory before {operation_name}: {before_usage.percent_used:.1f}% used")

        try:
            yield
        finally:
            after_usage = self.get_memory_usage()
            usage_diff = after_usage.used - before_usage.used

            logger.debug(
                f"Memory after {operation_name}: {after_usage.percent_used:.1f}% used, "
                f"diff: {usage_diff / 1024 / 1024:.1f}MB"
            )

            # If memory usage increased significantly, force GC
            if usage_diff > 50 * 1024 * 1024:  # 50MB increase
                self.force_garbage_collection()

    def ensure_memory_available(self, required_mb: int = 100) -> bool:
        """Check if required memory is available synchronously."""
        usage = self.get_memory_usage()
        required_bytes = required_mb * 1024 * 1024

        # If not enough memory, try to free up some
        if usage.available < required_bytes:
            logger.warning(
                f"Not enough memory available: {usage.available / 1024 / 1024:.1f}MB, "
                f"need {required_mb}MB. Attempting to free memory..."
            )

            self.force_garbage_collection()
            time.sleep(0.1)  # Brief pause to allow system to free memory

            usage = self.get_memory_usage()

            if usage.available < required_bytes:
                logger.error(f"Still not enough memory after GC: {usage.available / 1024 / 1024:.1f}MB")
                return False

        return True


class FileReader:
    """Synchronous file reader with memory-efficient chunked reading."""

    def __init__(self, config: AppConfig, memory_manager: MemoryManager):
        self.config = config
        self.memory_manager = memory_manager

    def read_file_chunks(
        self,
        file_path: str,
        chunk_size: int | None = None,
        max_file_size: int | None = None,
    ) -> list[str]:
        """
        Read a file in chunks synchronously, handling large files efficiently.

        Args:
            file_path: Path to the file to read
            chunk_size: Size of chunks to read (uses config default if None)
            max_file_size: Maximum file size to read (uses config default if None)

        Returns:
            List of file content chunks
        """
        chunk_size = chunk_size or self.config.model.processing.chunk_read_size
        max_size = max_file_size or self.config.model.pipeline.max_file_size

        # Check if file exceeds max size
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            logger.warning(f"File {file_path} ({file_size} bytes) exceeds max size {max_size}")
            raise ValueError(f"File too large: {file_path}")

        chunks = []

        with self.memory_manager.monitor_memory(f"reading {file_path}"):
            try:
                # Memory efficient reading
                def read_in_chunks():
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        chunks = []
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            chunks.append(chunk)
                        return chunks

                # Read the file content
                file_chunks = read_in_chunks()
                content = "".join(file_chunks)

                # For very large files, we might want to process in smaller segments
                if len(content) > chunk_size * 10:  # If content is very large
                    for i in range(0, len(content), chunk_size * 10):
                        segment = content[i : i + chunk_size * 10]
                        chunks.append(segment)
                else:
                    chunks = [content]

            except UnicodeDecodeError:
                logger.warning(f"Unicode decode error for file: {file_path}, skipping...")
                raise
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                raise

        return chunks

    def read_file_with_memory_protection(self, file_path: str, max_size_mb: float = 10.0) -> str | None:
        """
        Read a file with memory protection to prevent excessive memory usage.

        Args:
            file_path: Path to the file to read
            max_size_mb: Maximum file size in MB to read

        Returns:
            File content as string or None if file is too large
        """
        max_size_bytes = int(max_size_mb * 1024 * 1024)
        file_size = os.path.getsize(file_path)

        if file_size > max_size_bytes:
            logger.warning(f"Skipping file {file_path} due to size: {file_size / 1024 / 1024:.1f}MB > {max_size_mb}MB")
            return None

        # Check available memory
        if not self.memory_manager.ensure_memory_available(int(max_size_mb) + 50):  # Add 50MB buffer
            logger.error(f"Not enough memory to read file {file_path}")
            return None

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error reading file {file_path} with memory protection: {e}")
            return None


class LargeFileManager:
    """Manager for handling large files with efficient memory usage."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.memory_manager = MemoryManager(config)
        self.file_reader = FileReader(config, self.memory_manager)

    def process_large_file(self, file_path: str, processor_func: Callable[[str], None]) -> bool:
        """
        Process a large file with memory-efficient handling.

        Args:
            file_path: Path to the file to process
            processor_func: Function to process file content

        Returns:
            True if processing was successful
        """
        try:
            # First check if we have enough memory for this operation
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / 1024 / 1024

            if file_size > self.config.model.pipeline.max_file_size:
                logger.warning(f"File {file_path} exceeds max size. Skipping.")
                return False

            # Use memory-protected reading
            content = self.file_reader.read_file_with_memory_protection(
                file_path,
                file_size_mb + 5,  # Add 5MB buffer
            )

            if content is None:
                return False

            # Process content with memory monitoring
            with self.memory_manager.monitor_memory(f"processing {file_path}"):
                processor_func(content)

            return True

        except Exception as e:
            logger.error(f"Error processing large file {file_path}: {e}")
            return False

    def cleanup_memory(self):
        """Clean up memory resources."""
        self.memory_manager.clear_buffers()
        self.memory_manager.force_garbage_collection()


# Global memory manager instance
_memory_manager_instance: LargeFileManager | None = None


def get_memory_manager(config: AppConfig) -> LargeFileManager:
    """Get a singleton instance of the memory manager."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = LargeFileManager(config)
    return _memory_manager_instance
