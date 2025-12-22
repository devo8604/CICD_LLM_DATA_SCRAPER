"MLX Client for running models natively on Apple Silicon."

import hashlib
import os
import threading
from collections import OrderedDict

import structlog

# Set tokenizers parallelism to avoid warnings in multiprocessing
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Global lock to ensure MLX operations don't run concurrently
MLX_LOCK = threading.Lock()

try:
    from mlx_lm import generate
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

from src.core.config import AppConfig  # noqa: E402
from src.core.protocols import LLMInterface  # noqa: E402
from src.llm.mlx.model_manager import MLXModelManager  # noqa: E402
from src.llm.mlx.prompt_formatter import MLXPromptFormatter  # noqa: E402
from src.llm.prompt_utils import get_prompt_manager  # noqa: E402

logger = structlog.get_logger(__name__)


class MLXClient(LLMInterface):
    """
    MLX Client for running models natively on Apple Silicon.
    Uses Apple's MLX framework for optimized performance on M-series chips.
    """

    def __init__(
        self,
        model_name: str,
        max_retries: int = 3,
        retry_delay: int = 5,
        config: AppConfig | None = None,
    ):
        # Validate platform
        import platform
        is_apple_silicon = platform.system() == "Darwin" and ("arm" in platform.machine() or "aarch64" in platform.machine())
        if not is_apple_silicon:
            raise RuntimeError(
                "MLX is only supported on Apple Silicon (M1/M2/M3) Macs. "
                "Please use a different LLM backend for non-Apple Silicon systems."
            )

        self.config = config or AppConfig()
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.prompt_manager = get_prompt_manager(theme=self.config.model.pipeline.prompt_theme)

        # Specialized components
        self.model_manager = MLXModelManager(model_name)
        self.model_manager.load_model()
        
        self.formatter = MLXPromptFormatter(
            self.model_manager.tokenizer, 
            self.prompt_manager, 
            self.model_manager.context_window
        )

        # Initialize cache for better performance
        self._generate_cache = OrderedDict()
        self._cache_size = 256

    def generate_questions(
        self,
        content: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        pbar=None,
    ) -> list[str] | None:
        """Generate questions from code content using MLX."""
        import time
        start_time = time.time()
        logger.info("Starting generate_questions", content_length=len(content))

        try:
            if pbar:
                pbar.set_description(f"Gen Qs (ctx: {self.context_window}, MLX)")

            prompt = self.formatter.format_question_prompt(content, "Generate diverse, specific questions.")
            
            questions_text = self._generate_text_sync(prompt, temperature, max_tokens)

            if not questions_text:
                logger.warning("Empty response, retrying with direct prompt")
                direct_prompt = f"Q: What does this code do?\n\nCode:\n{content}"
                questions_text = self._generate_text_sync(direct_prompt, temperature, max_tokens)

            if isinstance(questions_text, list):
                # If it's already a list (e.g. from a mock), use it directly
                questions = questions_text
            else:
                questions = self.formatter.parse_questions(questions_text)

            if not questions and questions_text and questions_text.strip():
                questions = [questions_text.strip()]

            if pbar:
                pbar.set_description(f"Qs: {len(questions) if questions else 0} (MLX)")

            logger.info("generate_questions completed", duration=time.time() - start_time, count=len(questions) if questions else 0)
            return questions if questions else None

        except Exception as e:
            logger.error("Error generating questions with MLX", error=str(e), exc_info=True)
            return None

    def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        pbar=None,
    ) -> str | None:
        """Generate an answer to a question based on context using MLX."""
        import time
        start_time = time.time()
        logger.info("Starting get_answer_single", question=question[:50], context_length=len(context))

        if pbar:
            pbar.set_description(f"Gen Ans (ctx: {self.context_window}, MLX)")

        try:
            prompt = self.formatter.format_answer_prompt(question, context, max_tokens or self.config.model.generation.default_max_tokens)
            answer = self._generate_text_sync(prompt, temperature, max_tokens)

            if answer:
                answer = answer.replace("Answer:", "").replace(question, "").strip()

            if pbar:
                pbar.set_description(f"Ans: {len(answer) if answer else 0} chars (MLX)")

            logger.info("get_answer_single completed", duration=time.time() - start_time)
            return answer if answer and answer.strip() else None

        except Exception as e:
            logger.error("Error generating answer with MLX", error=str(e), exc_info=True)
            return None

    def _generate_text_sync(self, prompt: str, temperature: float = 0.7, max_tokens: int = None) -> str:
        """Generate text synchronously with locking and caching."""
        import time
        if max_tokens is None:
            max_tokens = self.config.model.generation.default_max_tokens

        start_overall = time.time()
        
        # Ensure model is loaded
        if self.model_manager.model is None:
            self.model_manager.load_model()

        # Cache check
        cache_hash = hashlib.md5(f"{prompt}_{temperature}_{max_tokens}".encode()).hexdigest()
        if cache_hash in self._generate_cache:
            self._generate_cache.move_to_end(cache_hash)
            logger.info("Cache hit for generation")
            return self._generate_cache[cache_hash]

        with MLX_LOCK:
            logger.info("Starting MLX generation", max_tokens=max_tokens)
            generation_start = time.time()
            try:
                response = generate(
                    model=self.model_manager.model,
                    tokenizer=self.model_manager.tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    verbose=False,
                )
            except Exception as e:
                logger.error("MLX generation failed", error=str(e))
                raise

            logger.info("MLX generation completed", duration=time.time() - generation_start)

        # Update cache
        if len(self._generate_cache) >= self._cache_size:
            self._generate_cache.popitem(last=False)
        self._generate_cache[cache_hash] = response or ""

        return self._generate_cache[cache_hash]

    def clear_context(self):
        """No state maintained between generations."""
        pass

    def clear_mlx_memory(self):
        """Clears MLX core caches."""
        self.model_manager.clear_memory()

    def update_model(self, model_name: str):
        """Update to a different model."""
        self.model_manager.unload_model()
        self.model_name = model_name
        self.model_manager = MLXModelManager(model_name)
        self.model_manager.load_model()
        self.formatter = MLXPromptFormatter(
            self.model_manager.tokenizer, 
            self.prompt_manager, 
            self.model_manager.context_window
        )

    def unload_model(self):
        """Unload model to free memory."""
        self.model_manager.unload_model()

    @property
    def context_window(self) -> int:
        return self.model_manager.context_window

    def __del__(self):
        try:
            if hasattr(self, 'model_manager'):
                self.model_manager.unload_model()
        except Exception:
            pass