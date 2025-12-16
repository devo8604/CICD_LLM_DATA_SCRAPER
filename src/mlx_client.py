"""MLX Client for running models natively on Apple Silicon."""

import asyncio
import logging
import os
import platform
import threading
from typing import List, Optional
from pathlib import Path
import sys

# Set tokenizers parallelism to avoid warnings in multiprocessing
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Global lock to ensure MLX operations don't run concurrently
# This prevents the GPU command buffer conflicts while allowing other operations to run in parallel
MLX_LOCK = threading.Lock()

try:
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm import load, generate

    # Only import what we actually need
    MLX_AVAILABLE = True

    def _check_apple_silicon():
        """Check if running on Apple Silicon."""
        machine = platform.machine()
        system = platform.system()
        return system == "Darwin" and (
            "arm" in machine or "ARM" in machine or "aarch64" in machine
        )

    # Check if this is Apple Silicon when module is imported (only if MLX is available)
    IS_APPLE_SILICON = _check_apple_silicon()

except ImportError as e:
    MLX_AVAILABLE = False
    IS_APPLE_SILICON = False  # If MLX isn't available, platform doesn't matter
    logging.warning(
        f"MLX libraries not available. MLX client will not function. Error: {e}"
    )

from src.config import AppConfig
from src.protocols import LLMInterface


class MLXClient:
    """
    MLX Client for running models natively on Apple Silicon.
    Uses Apple's MLX framework for optimized performance on M-series chips.
    """

    def __init__(
        self,
        model_name: str,
        max_retries: int = 3,
        retry_delay: int = 5,
        config: Optional[AppConfig] = None,
    ):
        if not MLX_AVAILABLE:
            raise ImportError(
                "MLX libraries are not installed. Please install mlx and mlx-lm packages."
            )

        if not IS_APPLE_SILICON:
            raise RuntimeError(
                "MLX is only supported on Apple Silicon (M1/M2/M3) Macs. "
                "Please use a different LLM backend for non-Apple Silicon systems."
            )

        self.config = config or AppConfig()
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize cache for better performance on repeated requests
        from functools import lru_cache
        import hashlib

        self._generate_cache = {}
        self._cache_size = 128  # Cache size for generation results

        # Optimize memory usage for Apple Silicon - only set device if MLX is properly available
        try:
            mx.set_default_device(mx.gpu)  # Use GPU by default for better performance
        except Exception:
            # If device setting fails (e.g., in test environment), continue with default
            logging.warning("Could not set MLX GPU device, using default")
            pass

        # Load the model and tokenizer with optimizations
        # Suppress progress bars during model loading to avoid UI conflicts
        import huggingface_hub

        original_tqdm = getattr(huggingface_hub, "tqdm", None)

        logging.info(f"Loading MLX model: {self.model_name}")
        try:
            print(f"Loading MLX model: {self.model_name}...")
            print("This may take several minutes for the first run...")

            # Temporarily disable progress bars during model loading to avoid UI conflicts
            if original_tqdm:
                huggingface_hub.tqdm = lambda *args, **kwargs: (
                    args[0] if args else iter([])
                )

            # Load with optimizations for better performance on Apple Silicon
            self.model, self.tokenizer = load(
                self.model_name,
                adapter_path=None,  # Add support for LoRA adapters if needed
                lazy=False,  # Load model immediately
            )

            # Restore progress bars if they were disabled
            if original_tqdm:
                huggingface_hub.tqdm = original_tqdm

            # Ensure model is in eval mode and optimize for inference
            self.model.eval()

            # Pre-warm the model by running a simple generation to initialize GPU
            self._warmup_model()

            logging.info(f"Successfully loaded MLX model: {self.model_name}")
            print("Model loaded. Starting pipeline...")

        except Exception as e:
            # Restore progress bars in case of error too
            if original_tqdm:
                huggingface_hub.tqdm = original_tqdm
            logging.error(f"Failed to load MLX model {self.model_name}: {e}")
            raise

    def _warmup_model(self):
        """Warm up the model to initialize GPU and cache for better performance."""
        try:
            # Run a simple generation to initialize GPU
            import time

            start_time = time.time()
            _ = generate(
                model=self.model,
                tokenizer=self.tokenizer,
                prompt="Say hello.",
                max_tokens=10,
            )
            warmup_time = time.time() - start_time
            logging.info(f"Model warmup completed in {warmup_time:.2f}s")
        except Exception as e:
            # If warmup fails (e.g., due to mocked objects during testing), just log and continue
            logging.info(f"Model warmup skipped: {e}")

    def _format_prompt(self, content: str, instruction: str) -> str:
        """
        Format the prompt for the model based on the model type.
        Uses a more code-focused approach for better Q&A generation.
        """
        # Truncate content if it's too large to avoid context length issues
        max_content_length = 2048  # Adjust as needed based on model capabilities

        if len(content) > max_content_length:
            # Keep the beginning and end of content, with an indicator of truncation
            half_length = max_content_length // 2
            truncated_content = (
                content[:half_length]
                + "\n... [Content truncated for model context window] ...\n"
                + content[-half_length:]
            )
        else:
            truncated_content = content

        # Format using the model's tokenizer chat template which is required for MLX models
        messages = [
            {
                "role": "system",
                "content": "You are an expert researcher and analyst. Generate only the specific questions requested by the user. Do not include any template instructions or system messages in your response.",
            },
            {
                "role": "user",
                "content": f"""Based on the following content, analyze its meaning and generate multiple relevant questions:

CONTENT:
```
{truncated_content}
```

INSTRUCTION: {instruction}

Generate as many diverse, specific questions as possible to thoroughly test understanding of this content. Focus on the purpose, function, important details, format, structure, relationships, implications, context, and significance. Ask different types of questions: What does it contain? How is it structured? Why is it formatted this way? What are the key elements? What could be improved? What is the context? What are the relationships between parts? How does it relate to other concepts? What assumptions does it make? What are the implications?

IMPORTANT: Return only clear, specific questions. Each question should be on its own line, formatted as "Q1: What does this content do?", "Q2: How is this organized?", etc. Do NOT include ANSWER: sections or empty code blocks like ``` in your response.""",
            },
        ]

        # Apply the chat template from the tokenizer if available (required for newer models)
        if hasattr(self.tokenizer, "apply_chat_template"):
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Fallback for older tokenizers without apply_chat_template
            # Construct a simple format that should work with most models
            prompt_parts = []
            for message in messages:
                role = message["role"]
                content = message["content"]
                if role == "system":
                    prompt_parts.append(f"System: {content}")
                elif role == "user":
                    prompt_parts.append(f"User: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant: {content}")
            prompt = "\n\n".join(prompt_parts)

        return prompt

    async def generate_questions(
        self, content: str, temperature: float = 0.7, max_tokens: int = 500, pbar=None
    ) -> Optional[List[str]]:
        """
        Generate questions from code content using MLX.
        """
        if pbar:
            pbar.set_description("Generating questions (MLX)")

        try:
            # Create a prompt asking for questions based on the content
            prompt = self._format_prompt(
                content,
                "Generate as many diverse, specific questions as possible about the given content that would help understand its purpose, structure, important elements, relationships, implications, and potential improvements.",
            )

            # Log the prompt for debugging
            logging.debug(f"MLX Generate Questions Prompt: {prompt[:100]}...")

            # Generate questions
            questions_text = await asyncio.get_event_loop().run_in_executor(
                None, self._generate_text_sync, prompt, temperature, max_tokens
            )

            # Log the response for debugging
            logging.debug(
                f"MLX Generate Questions Response: {questions_text[:200] if questions_text else 'None'}..."
            )

            # If we got an empty response, try with a more specific prompt
            if not questions_text or questions_text.strip() == "":
                logging.warning(
                    "Empty response from model, trying with more direct prompt"
                )
                direct_prompt = f"""Based on this code:

```
{content}
```

Please generate exactly 1-2 questions about this code. Each question should start with 'Q:' followed by the question and end with '?'

Examples:
Q: What is the purpose of this function?
Q: What does this code do?
"""

                questions_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._generate_text_sync,
                    direct_prompt,
                    temperature,
                    max_tokens,
                )

            # Parse the generated text into individual questions
            questions = self._parse_questions(questions_text)

            # If still no questions, return the raw text as a single question if there's content
            if not questions and questions_text and questions_text.strip():
                questions = [questions_text.strip()]

            # Log progress if needed
            if pbar:
                pbar.set_description(
                    f"Questions gen: {len(questions) if questions else 0} (MLX)"
                )

            return questions if questions else None

        except Exception as e:
            logging.error(f"Error generating questions with MLX: {e}")
            import traceback

            logging.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def _generate_text_sync(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 500
    ) -> str:
        """
        Generate text synchronously (called from executor for async compatibility).
        With caching and performance optimizations.
        """
        # Create cache key from entire prompt and parameters to enable caching
        # Use full prompt hash to ensure different prompts get different cache entries
        import hashlib

        cache_hash = hashlib.md5(
            f"{prompt}_{temperature}_{max_tokens}".encode()
        ).hexdigest()

        # Check cache first for performance
        if cache_hash in self._generate_cache:
            return self._generate_cache[cache_hash]

        # Use lock to prevent concurrent MLX generation which causes GPU command buffer conflicts
        try:
            with MLX_LOCK:
                # Generate with MLX - use only parameters that are actually supported by generate_step
                # The logs show that generate_step doesn't accept temp, top_p, repetition_penalty
                response = generate(
                    model=self.model,
                    tokenizer=self.tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                )

            # Add to cache (with size limit)
            if len(self._generate_cache) < self._cache_size:
                self._generate_cache[cache_hash] = (
                    response if response is not None else ""
                )

            return response if response is not None else ""
        except Exception as e:
            # Provide better error information for users
            logging.error(f"Synchronous generation error: {e}")
            logging.error(
                f"Prompt that failed: {prompt[:200]}..."
            )  # Log first 200 chars of prompt
            import traceback

            logging.error(f"Full traceback: {traceback.format_exc()}")

            # Inform users about common issues
            error_msg = str(e)
            if "Insufficient Memory" in error_msg or "Out of memory" in error_msg:
                logging.error(
                    "💡 Memory Error Tip: This error usually happens with large models on limited GPU memory."
                )
                logging.error(
                    "💡 Solutions: Try a smaller model (e.g., 7B instead of 30B) or increase system memory."
                )
            elif "unexpected keyword argument" in error_msg:
                logging.error(
                    "💡 Parameter Error Tip: MLX doesn't support all standard LLM parameters like 'temp', 'top_p', 'repetition_penalty'."
                )
                logging.error(
                    "💡 Solution: Parameters have been removed in this version to ensure compatibility."
                )
            elif "command encoder" in error_msg:
                logging.error(
                    "💡 GPU Conflict Error: Another MLX operation may be running simultaneously."
                )
                logging.error(
                    "💡 Solution: MLX operations are now serialized to prevent this issue."
                )

            return ""

    def _parse_questions(self, text: str) -> List[str]:
        """
        Parse generated text into a list of questions.
        Enhanced to capture multiple question formats and patterns including Q#: format.
        """
        if not text or not text.strip():
            return []

        # Split by common question indicators, clean up, and filter
        lines = text.split("\n")
        questions = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line is in the format "Q1: question?", "Q2: question?", etc.
            if ":" in line and line.startswith(("Q", "q")):
                # Look for patterns like "Q1: ", "Q2: ", "Q10: ", etc.
                import re

                q_pattern = r"^[Qq]\d+:\s*(.+?\?)$"
                match = re.match(q_pattern, line)
                if match:
                    question = match.group(1).strip()
                    if question and len(question) > 3:  # Substantial questions
                        questions.append(question)
                elif "?" in line:
                    # If it has Q# format but no question mark at the end, add it
                    content = line.split(":", 1)[
                        1
                    ].strip()  # Get content after first colon
                    if "?" not in content and len(content) > 3:
                        questions.append(f"{content}?")

            # Check for question mark patterns (backup method)
            elif "?" in line:
                # Extract all questions that might be in the line
                parts = line.split("?")
                for i, part in enumerate(parts[:-1]):  # All but the last part
                    # Combine with the next part and add the question mark back
                    question = (part + "?").strip()
                    # Clean up common prefixes
                    question = (
                        question.replace("Q:", "")
                        .replace("Question:", "")
                        .replace("1.", "")
                        .replace("2.", "")
                        .replace("3.", "")
                        .replace("4.", "")
                        .replace("5.", "")
                        .replace("6.", "")
                        .replace("7.", "")
                        .replace("8.", "")
                        .replace("9.", "")
                        .replace("10.", "")
                        .strip()
                    )
                    if question and len(question) > 3:  # Only substantial questions
                        questions.append(question)

            # Alternative: look for numbered questions like "1. What is..." or "2. How does..."
            import re

            numbered_pattern = r"\d+\.\s*(.+?\?)"
            matches = re.findall(numbered_pattern, line)
            for match in matches:
                cleaned_match = match.strip()
                if cleaned_match and len(cleaned_match) > 3:
                    questions.append(cleaned_match)

        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in questions:
            if q not in seen and q.strip():
                seen.add(q)
                unique_questions.append(q.strip())

        return (
            unique_questions
            if unique_questions
            else [f"{text.strip()}?"] if text.strip() and "?" not in text else []
        )

    async def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        pbar=None,
    ) -> Optional[str]:
        """
        Generate an answer to a question based on context using MLX.
        """
        if pbar:
            pbar.set_description("Generating answer (MLX)")

        try:
            # Apply content truncation if needed
            max_content_length = 2048
            if len(context) > max_content_length:
                half_length = max_content_length // 2
                truncated_context = (
                    context[:half_length]
                    + "\n... [Content truncated for model context window] ...\n"
                    + context[-half_length:]
                )
            else:
                truncated_context = context

            # Format using the model's tokenizer chat template which is required for MLX models
            messages = [
                {
                    "role": "system",
                    "content": "You are a precise question-answering expert. You will be given content and a specific question about that content. ANSWER ONLY THE QUESTION ASKED using information from the content. Never give generic answers about the content unrelated to the specific question.",
                },
                {
                    "role": "user",
                    "content": f"""CONTENT FOR REFERENCE:
```
{truncated_context}
```

SPECIFIC QUESTION (ANSWER THIS EXACTLY): {question}

RESPONSE: Answer ONLY and EXACTLY the question above based on the content shown. Your response must directly address what was asked in the question. If the question asks 'HOW', focus on processes/procedures. If it asks 'WHAT', focus on descriptions. If it asks 'WHY', focus on reasons/purposes. If it asks 'WHERE', focus on locations/URLs. Make sure your answer is specific to what was asked, not a general summary of the content.""",
                },
            ]

            # Apply the chat template from the tokenizer if available (required for newer models)
            if hasattr(self.tokenizer, "apply_chat_template"):
                prompt = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            else:
                # Fallback for older tokenizers without apply_chat_template
                # Construct a simple format that should work with most models
                prompt_parts = []
                for message in messages:
                    role = message["role"]
                    content = message["content"]
                    if role == "system":
                        prompt_parts.append(f"System: {content}")
                    elif role == "user":
                        prompt_parts.append(f"User: {content}")
                    elif role == "assistant":
                        prompt_parts.append(f"Assistant: {content}")
                prompt = "\n\n".join(prompt_parts)

            # Log the prompt for debugging
            logging.debug(f"MLX Get Answer Prompt: {prompt[:100]}...")

            # Generate answer
            answer = await asyncio.get_event_loop().run_in_executor(
                None, self._generate_text_sync, prompt, temperature, max_tokens
            )

            # Log the response for debugging
            logging.debug(
                f"MLX Get Answer Response: {answer[:200] if answer else 'None'}..."
            )

            # Clean up answer
            if answer:
                answer = answer.replace("Answer:", "").replace(question, "").strip()

            # Log progress if needed
            if pbar:
                pbar.set_description("Answer generated (MLX)")

            return answer if answer.strip() else None

        except Exception as e:
            logging.error(f"Error generating answer with MLX: {e}")
            import traceback

            logging.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def clear_context(self):
        """
        Clear any cached context or state.
        MLX is stateless for generation, so no specific cleanup needed.
        """
        pass

    def update_model(self, model_name: str):
        """
        Update to a different model.
        """
        try:
            self.model, self.tokenizer = load(model_name, lazy=False)
            self.model_name = model_name
            logging.info(f"Updated MLX model to: {model_name}")
        except Exception as e:
            logging.error(f"Failed to update MLX model to {model_name}: {e}")
            raise
