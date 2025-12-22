"""System monitoring utilities for the TUI dashboard."""

import platform
import subprocess

import psutil


def get_system_memory_info() -> dict[str, any]:
    """Get system memory (RAM) information."""
    memory = psutil.virtual_memory()

    return {
        "total": memory.total,
        "available": memory.available,
        "used": memory.used,
        "percent_used": memory.percent,
        "free": memory.free,
        "buffers": memory.buffers if hasattr(memory, "buffers") else 0,
        "cached": memory.cached if hasattr(memory, "cached") else 0,
    }


def get_swap_info() -> dict[str, any]:
    """Get system swap information."""
    swap = psutil.swap_memory()

    return {
        "total": swap.total,
        "used": swap.used,
        "free": swap.free,
        "percent_used": swap.percent,
        "sin": swap.sin,  # Memory swapped in from disk (cumulative)
        "sout": swap.sout,  # Memory swapped out to disk (cumulative)
    }


def get_gpu_info() -> dict[str, any]:
    """Get GPU information if available."""
    gpu_info = {"available": False, "type": "none", "gpus": []}

    # Check for NVIDIA GPUs using nvidia-smi
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            close_fds=False,
        )
        if result.returncode == 0:
            gpu_info["available"] = True
            gpu_info["type"] = "nvidia"

            # Parse nvidia-smi output
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = [part.strip() for part in line.split(",")]
                    if len(parts) >= 6:
                        gpu_info["gpus"].append(
                            {
                                "name": parts[0],
                                "memory_total": int(parts[1]),
                                "memory_used": int(parts[2]),
                                "memory_free": int(parts[3]),
                                "gpu_utilization": int(parts[4]),
                                "memory_utilization": int(parts[5]),
                            }
                        )
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass

    # Check for Apple Silicon GPU - try different approaches for better detection
    if not gpu_info["available"] and platform.system() == "Darwin":
        try:
            # Try system_profiler to get GPU info
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=5,
                close_fds=False,
            )
            if result.returncode == 0:
                # Look for Apple Silicon chips
                import re

                # Check for Apple Silicon Graphics processors
                apple_gpu_pattern = r"(Apple M\d+[A-Z]* \w+ Graphics)"
                gpu_matches = re.findall(apple_gpu_pattern, result.stdout, re.IGNORECASE)

                # Also look for general Apple Silicon indicators
                chip_match = re.search(r"Apple (M\d+[A-Z]*)", result.stdout, re.IGNORECASE)

                if gpu_matches or chip_match:
                    gpu_info["available"] = True
                    gpu_info["type"] = "apple_silicon"

                    # Extract more specific GPU name
                    if gpu_matches:
                        # Take the first GPU match
                        gpu_name = gpu_matches[0]
                    elif chip_match:
                        # Build a generic GPU name from the chip name
                        gpu_name = f"{chip_match.group(1)} Integrated GPU"
                    else:
                        gpu_name = "Apple Silicon GPU"

                    gpu_info["gpus"].append(
                        {
                            "name": gpu_name,
                            "memory_total": 0,  # Memory is shared with system on Apple Silicon
                            "memory_used": 0,
                            "memory_free": 0,
                            "gpu_utilization": 0,
                            "memory_utilization": 0,
                        }
                    )
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            pass

        # Fallback: if on Darwin and no specific GPU detected, still acknowledge Apple Silicon as having integrated GPU
        if not gpu_info["available"]:
            try:
                # Alternative check for Apple Silicon
                result = subprocess.run(
                    ["uname", "-m"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    close_fds=False,
                )
                if result.returncode == 0 and (
                    "arm" in result.stdout.lower()
                    or "arm64" in result.stdout.lower()
                    or "aarch64" in result.stdout.lower()
                ):
                    gpu_info["available"] = True
                    gpu_info["type"] = "apple_silicon"
                    gpu_info["gpus"].append(
                        {
                            "name": "Apple Silicon Integrated GPU",
                            "memory_total": 0,
                            "memory_used": 0,
                            "memory_free": 0,
                            "gpu_utilization": 0,
                            "memory_utilization": 0,
                        }
                    )
            except (
                subprocess.TimeoutExpired,
                FileNotFoundError,
                subprocess.SubprocessError,
            ):
                pass

    # Check for AMD GPUs
    if not gpu_info["available"]:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showallinfo"],
                capture_output=True,
                text=True,
                timeout=5,
                close_fds=False,
            )
            if result.returncode == 0:
                gpu_info["available"] = True
                gpu_info["type"] = "amd"
                gpu_info["gpus"].append(
                    {
                        "name": "AMD GPU",
                        "memory_total": 0,
                        "memory_used": 0,
                        "memory_free": 0,
                        "gpu_utilization": 0,
                        "memory_utilization": 0,
                    }
                )
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            pass

    return gpu_info


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def get_system_stats() -> dict[str, any]:
    """Get all system statistics."""
    memory_info = get_system_memory_info()
    swap_info = get_swap_info()
    gpu_info = get_gpu_info()

    return {"memory": memory_info, "swap": swap_info, "gpu": gpu_info}
