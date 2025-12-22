"""Runtime patches for compatibility and stability."""

import asyncio
import multiprocessing
import signal
import subprocess


def apply_patches():
    """Apply all runtime patches."""

    # Handle Ctrl+C gracefully
    def signal_handler(signum, frame):
        import os

        os._exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)
    except ValueError:
        # Not in main thread, ignore
        pass

    # Fix for Python 3.14 multiprocessing issues in Textual TUI
    try:
        if multiprocessing.get_start_method(allow_none=True) != "fork":
            multiprocessing.set_start_method("fork", force=True)
    except (RuntimeError, ValueError):
        pass

    # Subprocess and asyncio patches
    _original_run = subprocess.run

    def _patched_run(*args, **kwargs):
        if "close_fds" not in kwargs:
            kwargs["close_fds"] = False
        return _original_run(*args, **kwargs)

    subprocess.run = _patched_run

    _original_popen_init = subprocess.Popen.__init__

    def _patched_popen_init(self, *args, **kwargs):
        if "close_fds" not in kwargs:
            kwargs["close_fds"] = False
        return _original_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _patched_popen_init

    # Also patch asyncio subprocess
    _original_create_subprocess_exec = asyncio.create_subprocess_exec

    async def _patched_create_subprocess_exec(*args, **kwargs):
        if "close_fds" not in kwargs:
            kwargs["close_fds"] = False
        return await _original_create_subprocess_exec(*args, **kwargs)

    asyncio.create_subprocess_exec = _patched_create_subprocess_exec
