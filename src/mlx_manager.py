"""MLX Model management functionality with pre-download capability."""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import json

try:
    import huggingface_hub
    from mlx_lm import load

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

from src.config import AppConfig


class MLXModelManager:
    """Manager for MLX models: list, download, remove, etc."""

    def __init__(self, config: AppConfig = None):
        self.config = config or AppConfig()
        # Get the cache directory where MLX models are stored
        self.cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

    def list_local_models(self) -> List[Dict[str, str]]:
        """List locally cached MLX models."""
        if not MLX_AVAILABLE:
            return []

        models = []
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.is_dir() and item.name.startswith("models--"):
                    model_name = item.name.replace("models--", "").replace("--", "/")
                    # Check if this looks like an MLX model (has model files)
                    model_files = list(item.rglob("*.safetensors")) + list(
                        item.rglob("*.bin")
                    )
                    if model_files:
                        size = self._get_directory_size(item)
                        models.append(
                            {
                                "name": model_name,
                                "path": str(item),
                                "size": self._format_size(size),
                            }
                        )
        return models

    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory in bytes."""
        total_size = 0
        for dirpath, _, filenames in os.walk(directory):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                total_size += filepath.stat().st_size
        return total_size

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def download_model(self, model_name: str) -> bool:
        """Download an MLX model with explicit progress."""
        if not MLX_AVAILABLE:
            print("MLX libraries not available. Please install mlx and mlx-lm.")
            return False

        try:
            print(f"Downloading model: {model_name}")
            print("This may take several minutes...")

            # Use huggingface_hub to download the model explicitly
            # This will show download progress bars separately
            huggingface_hub.snapshot_download(
                repo_id=model_name,
                local_dir=None,  # Use default cache
                allow_patterns=[
                    "*.json",
                    "*.safetensors",
                    "*.bin",
                    "*.py",
                    "*.txt",
                    "*.model",
                ],
            )

            print(f"Successfully downloaded: {model_name}")
            return True
        except Exception as e:
            print(f"Error downloading model {model_name}: {e}")
            return False

    def preload_model(self, model_name: str) -> bool:
        """Pre-load a model to cache it fully before pipeline use."""
        if not MLX_AVAILABLE:
            print("MLX libraries not available. Please install mlx and mlx-lm.")
            return False

        try:
            print(f"Pre-loading model to cache: {model_name}")
            print("This may take several minutes if it's not cached...")

            # Load model to ensure it's fully cached locally
            model, tokenizer = load(
                model_name,
                lazy=False,  # Load model immediately
            )

            print(f"Successfully pre-loaded: {model_name}")
            print("Model is now fully cached and ready for pipeline use.")
            return True
        except Exception as e:
            print(f"Error pre-loading model {model_name}: {e}")
            return False

    def remove_model(self, model_name: str) -> bool:
        """Remove a locally cached MLX model."""
        try:
            # Convert model name to directory name format used by HF hub
            dir_name = f"models--{model_name.replace('/', '--')}"
            model_path = self.cache_dir / dir_name

            if not model_path.exists():
                print(f"Model {model_name} not found in local cache.")
                return False

            # Confirm before deletion
            print(f"About to delete model: {model_name}")
            print(f"Location: {model_path}")
            print(f"Size: {self._format_size(self._get_directory_size(model_path))}")

            confirm = input("Are you sure you want to delete this model? (yes/no): ")
            if confirm.lower() not in ["yes", "y"]:
                print("Deletion cancelled.")
                return False

            shutil.rmtree(model_path)
            print(f"Successfully removed model: {model_name}")
            return True
        except Exception as e:
            print(f"Error removing model {model_name}: {e}")
            return False

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get detailed information about a specific model."""
        try:
            # Try to get info about the model from local cache
            dir_name = f"models--{model_name.replace('/', '--')}"
            model_path = self.cache_dir / dir_name

            if model_path.exists():
                size = self._get_directory_size(model_path)
                files = [
                    str(f.relative_to(model_path))
                    for f in model_path.rglob("*")
                    if f.is_file()
                ]

                return {
                    "name": model_name,
                    "path": str(model_path),
                    "size": self._format_size(size),
                    "file_count": len(files),
                    "cached": True,
                }

            # Model is not cached, get info from remote
            print(f"Model {model_name} is not cached locally. Checking remote...")
            # For now, we'll just return basic info since getting remote info requires API calls
            return {"name": model_name, "cached": False}
        except Exception as e:
            print(f"Error getting info for model {model_name}: {e}")
            return None
