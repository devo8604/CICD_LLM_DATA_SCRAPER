"""MLX Model loading and management."""

import gc
import platform

import structlog

try:
    import mlx.core as mx
    from mlx_lm import generate, load

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

logger = structlog.get_logger(__name__)


class MLXModelManager:
    """Manages loading, unloading and memory of MLX models."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._context_window = 4096

        if not MLX_AVAILABLE:
            raise ImportError("MLX libraries are not installed.")

    def load_model(self):
        """Load the MLX model and tokenizer."""
        if self.model is not None:
            return

        import huggingface_hub

        original_tqdm = getattr(huggingface_hub, "tqdm", None)

        logger.info("Loading MLX model", model_name=self.model_name)
        try:
            # Set default device to GPU on Apple Silicon
            if platform.system() == "Darwin" and "arm" in platform.machine():
                mx.set_default_device(mx.gpu)

            self.model, self.tokenizer = load(
                self.model_name,
                lazy=False,
            )

            if original_tqdm:
                huggingface_hub.tqdm = original_tqdm

            self.model.eval()
            self._context_window = self._detect_context_window()

            self.clear_memory()
            self._warmup_model()

            logger.info("Successfully loaded MLX model", model_name=self.model_name, context_window=self._context_window)

        except Exception as e:
            if original_tqdm:
                huggingface_hub.tqdm = original_tqdm
            self.unload_model()
            logger.error("Failed to load MLX model", model_name=self.model_name, error=str(e))
            raise

    def _warmup_model(self):
        """Warm up the model to initialize GPU."""
        try:
            generate(
                model=self.model,
                tokenizer=self.tokenizer,
                prompt="Say hello.",
                max_tokens=10,
            )
        except Exception as e:
            logger.debug("Model warmup skipped", error=str(e))

    def unload_model(self):
        """Unload the model to free up memory."""
        if self.model is not None:
            logger.info("Unloading MLX model", model_name=self.model_name)
            self.model = None
            self.tokenizer = None
            self.clear_memory()

    def clear_memory(self):
        """Clears MLX core caches and triggers GC."""
        if MLX_AVAILABLE:
            try:
                mx.eval()
                mx.clear_cache()
                gc.collect()
            except Exception as e:
                logger.warning("Failed to clear MLX cache", error=str(e))

    @property
    def context_window(self) -> int:
        return self._context_window

    def _detect_context_window(self) -> int:
        """Detect the context window size."""
        default_window = 4096
        try:
            if hasattr(self.model, "config"):
                config = self.model.config
                keys = ["max_position_embeddings", "max_sequence_length", "model_max_length", "n_ctx"]
                for key in keys:
                    val = getattr(config, key, None) or (config.get(key) if isinstance(config, dict) else None)
                    if val and isinstance(val, int) and val > 0:
                        return val
            if hasattr(self.tokenizer, "model_max_length"):
                window = self.tokenizer.model_max_length
                if window and isinstance(window, int) and 0 < window < 1000000:
                    return window
        except Exception as e:
            logger.warning("Failed to detect context window", error=str(e))
        return default_window
