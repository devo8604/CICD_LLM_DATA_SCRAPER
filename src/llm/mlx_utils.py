"""Utilities for MLX detection and management."""

import importlib.util


def is_mlx_available() -> bool:
    """Check if MLX library is installed and available."""
    try:
        # Check if the module can be found
        if importlib.util.find_spec("mlx") is None:
            return False

        # Try a real import to be absolutely sure (handles cases where find_spec is not enough)
        import mlx.core  # noqa: F401

        return True
    except (ImportError, ValueError, AttributeError):
        return False
