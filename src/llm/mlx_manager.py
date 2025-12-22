"""MLX Model management functionality with pre-download capability."""

import logging
import os
import shutil
from pathlib import Path

try:
    import huggingface_hub
    from mlx_lm import load

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

from src.core.config import AppConfig


class MLXModelManager:
    """Manager for MLX models: list, download, remove, etc."""

    def __init__(self, config: AppConfig = None):
        self.config = config or AppConfig()
        # Get the cache directory where MLX models are stored
        self.cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

    def list_local_models(self) -> list[dict[str, str]]:
        """List locally cached MLX models."""
        if not MLX_AVAILABLE:
            return []

        models = []
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.is_dir() and item.name.startswith("models--"):
                    model_name = item.name.replace("models--", "").replace("--", "/")
                    # Check if this looks like an MLX model (has model files)
                    model_files = list(item.rglob("*.safetensors")) + list(item.rglob("*.bin"))
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
            logging.error("MLX libraries not available. Please install mlx and mlx-lm.")
            return False

        try:
            logging.info(f"Downloading model: {model_name}")
            logging.info("This may take several minutes...")

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

            logging.info(f"Successfully downloaded: {model_name}")
            return True
        except Exception as e:
            logging.error(f"Error downloading model {model_name}: {e}")
            return False

    def preload_model(self, model_name: str) -> bool:
        """Pre-load a model to cache it fully before pipeline use."""
        if not MLX_AVAILABLE:
            logging.error("MLX libraries not available. Please install mlx and mlx-lm.")
            return False

        try:
            logging.info(f"Pre-loading model to cache: {model_name}")
            logging.info("This may take several minutes if it's not cached...")

            # Load model to ensure it's fully cached locally
            model, tokenizer = load(
                model_name,
                lazy=False,  # Load model immediately
            )

            logging.info(f"Successfully pre-loaded: {model_name}")
            logging.info("Model is now fully cached and ready for pipeline use.")
            return True
        except Exception as e:
            logging.error(f"Error pre-loading model {model_name}: {e}")
            return False

    def remove_model(self, model_name: str) -> bool:
        """Remove a locally cached MLX model."""
        try:
            # Convert model name to directory name format used by HF hub
            dir_name = f"models--{model_name.replace('/', '--')}"
            model_path = self.cache_dir / dir_name

            if not model_path.exists():
                logging.warning(f"Model {model_name} not found in local cache.")
                return False

            # Confirm before deletion
            logging.info(f"About to delete model: {model_name}")
            logging.info(f"Location: {model_path}")
            logging.info(f"Size: {self._format_size(self._get_directory_size(model_path))}")

            confirm = input("Are you sure you want to delete this model? (yes/no): ")
            if confirm.lower() not in ["yes", "y"]:
                logging.info("Deletion cancelled.")
                return False

            shutil.rmtree(model_path)
            logging.info(f"Successfully removed model: {model_name}")
            return True
        except Exception as e:
            logging.error(f"Error removing model {model_name}: {e}")
            return False

    def get_model_info(self, model_name: str) -> dict | None:
        """Get detailed information about a specific model."""
        try:
            # Try to get info about the model from local cache
            dir_name = f"models--{model_name.replace('/', '--')}"
            model_path = self.cache_dir / dir_name

            if model_path.exists():
                size = self._get_directory_size(model_path)
                files = [str(f.relative_to(model_path)) for f in model_path.rglob("*") if f.is_file()]

                return {
                    "name": model_name,
                    "path": str(model_path),
                    "size": self._format_size(size),
                    "file_count": len(files),
                    "cached": True,
                }

            # Model is not cached, get info from remote
            logging.info(f"Model {model_name} is not cached locally. Checking remote...")
            # For now, we'll just return basic info since getting remote info requires API calls
            return {"name": model_name, "cached": False}
        except Exception as e:
            logging.error(f"Error getting info for model {model_name}: {e}")
            return None


def handle_mlx_command(args):
    """Handle MLX management commands."""
    manager = MLXModelManager()

    if args.mlx_command == "list":
        models = manager.list_local_models()
        if not models:
            logging.info("No locally cached MLX models found.")
        else:
            logging.info(f"Found {len(models)} locally cached models:")
            for model in models:
                logging.info(f"  - {model['name']} ({model['size']})")

    elif args.mlx_command == "download":
        manager.download_model(args.model_name)

    elif args.mlx_command == "remove":
        manager.remove_model(args.model_name)

    elif args.mlx_command == "info":
        info = manager.get_model_info(args.model_name)
        if info:
            logging.info(f"Model: {info['name']}")
            logging.info(f"Cached: {'Yes' if info['cached'] else 'No'}")
            if info["cached"]:
                logging.info(f"Location: {info['path']}")
                logging.info(f"Size: {info['size']}")
                logging.info(f"Files: {info['file_count']}")
