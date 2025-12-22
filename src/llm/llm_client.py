import json
import logging
import time
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from tqdm import tqdm

from src.core.config import AppConfig
from src.core.protocols import LLMInterface
from src.llm.prompt_utils import get_prompt_manager
from src.core.tokenizer_cache import get_pretokenizer
from typing import Tuple, Optional


class LLMClient(LLMInterface):
    """LLM client with caching and retry logic for OpenAI-compatible APIs."""

    # Class-level cache for model list
    _model_cache: list[str] | None = None
    _model_cache_time: float | None = None

    def __init__(
        self,
        base_url: str,
        model_name: str,
        max_retries: int,
        retry_delay: int,
        config: AppConfig,
        request_timeout: int = 300,
    ) -> None:
        if config is None:
            raise ValueError("Config must be provided")
        self.config = config
        self.base_url = base_url
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout
        self.prompt_manager = get_prompt_manager(theme=self.config.model.pipeline.prompt_theme)
        self.model_cache_ttl = self.config.model.llm.model_cache_ttl

        logging.info(f"LLMClient initialized. Using model: {self.model_name} at {base_url}")

        try:
            # Call sync method for initial check
            logging.info("Calling _get_available_llm_models_sync_wrapper in __init__.")
            available_models = self._get_available_llm_models_sync_wrapper()
            logging.info(
                f"Finished _get_available_llm_models_sync_wrapper in __init__. Found models: {available_models}"
            )
        except Exception as e:
            logging.critical(
                f"An unexpected error occurred during initial model fetch: {e}",
                exc_info=True,
            )
            available_models = []

        if available_models:
            if self.model_name in available_models:
                logging.info(f"Using specified model: {self.model_name}")
            else:
                logging.warning(f"Specified model '{self.model_name}' not found on the LLM server.")
                logging.info(f"Available models: {', '.join(available_models)}")
                if available_models:
                    # Fallback to the first available model
                    original_model_name = self.model_name
                    self.model_name = available_models[0]
                    logging.info(
                        f"Requested model '{original_model_name}' not found. "
                        f"Falling back to first available model: {self.model_name}"
                    )
                else:
                    logging.critical("No models available on the LLM server. Please load a model.")
                    self.model_name = None  # Indicate no usable model
        else:
            logging.critical(
                "Could not connect to LLM server or retrieve model list. Please ensure the server is running."
            )
            self.model_name = None  # Indicate no usable model

        if not self.model_name:
            logging.critical(
                "LLMClient is not initialized with a usable model. Raising an exception to halt processing."
            )
            raise ValueError("No usable LLM model available or configured. Check LLM server and model loads.")

        # Detect context window
        self._context_window = self._detect_context_window()
        logging.info(f"Context window for {self.model_name}: {self._context_window}")

        # Initialize pre-tokenizer for efficient token operations
        self.pretokenizer = get_pretokenizer(self.model_name)

        logging.info("LLMClient successfully initialized with a usable model.")

    def _get_available_llm_models_sync_wrapper(self) -> list[str]:
        """Wrapper to manage sync client lifecycle."""
        # Use the configured timeout for the client to cover connection, read, and write
        timeout = httpx.Timeout(self.request_timeout, connect=10.0)  # Use configured timeout
        with httpx.Client(timeout=timeout) as client:
            return self._get_available_llm_models(client)

    def _get_available_llm_models(self, client: httpx.Client) -> list[str]:
        """Fetch available models with caching."""
        logging.info("Attempting to get available LLM models.")
        # Check cache first
        current_time = time.time()
        if (
            LLMClient._model_cache is not None
            and LLMClient._model_cache_time is not None
            and (current_time - LLMClient._model_cache_time) < self.model_cache_ttl
        ):
            logging.debug("Using cached model list")
            return LLMClient._model_cache

        models_api_url = f"{self.base_url}/v1/models"
        try:
            logging.info(f"Sending GET request to {models_api_url} for model list.")
            response = client.get(models_api_url)  # Timeout is now handled by the client instance
            logging.info(f"Received response from {models_api_url}. Status: {response.status_code}")
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            models_data = response.json()
            logging.info(f"Raw models response from server: {models_data}")
            # Assuming OpenAI-compatible API response structure: {"data": [{"id": "model_name", ...}]}
            models = [m["id"] for m in models_data.get("data", [])]

            # Update cache
            LLMClient._model_cache = models
            LLMClient._model_cache_time = current_time

            logging.info(f"Successfully retrieved and parsed model list: {models}")
            return models
        except httpx.ConnectError as e:
            logging.error(f"Connection error to LLM server at {models_api_url}: {e}")
            return []
        except httpx.ReadTimeout:
            logging.error(
                f"Read timeout while waiting for response from LLM server at {models_api_url}. "
                "The server accepted the connection but did not send a complete response within the timeout period."
            )
            return []
        except httpx.RequestError as e:  # Catch all other httpx request errors
            logging.error(f"Failed to retrieve LLM model list from {models_api_url}: {e}")
            return []
        except json.JSONDecodeError:
            logging.error(
                f"Failed to decode JSON from LLM server at {models_api_url}. Response: {response.text[:200]}..."
            )
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred while getting model list: {e}")
            return []

    def _call_llm_api(
        self,
        messages: list[dict[str, str]],
        options: dict[str, int | float],
        function_name: str,
        pbar: tqdm | None = None,
    ) -> dict[str, any] | None:
        """Call LLM API with retry logic and streaming."""
        chat_completions_url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": options.get("temperature", 0.7),
            "max_tokens": options.get("max_tokens", self.config.model.generation.default_max_tokens),
            "stream": True,  # Enable streaming
        }

        full_response = ""
        with httpx.Client() as client:
            for attempt in range(self.max_retries):
                try:
                    logging.debug(f"Sending POST request to {chat_completions_url} with payload: {json.dumps(payload)}")
                    with client.stream(
                        "POST",
                        chat_completions_url,
                        headers=headers,
                        json=payload,
                        timeout=self.request_timeout,
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line:
                                try:
                                    if line.startswith("data: "):
                                        chunk_str = line[6:].strip()
                                        if chunk_str == "[DONE]":
                                            continue
                                        if not chunk_str:
                                            continue

                                        data = json.loads(chunk_str)
                                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if delta:
                                            full_response += delta
                                except json.JSONDecodeError:
                                    logging.warning(f"Failed to decode JSON chunk: {line}")
                                    continue
                                except Exception as e:
                                    logging.error(f"Error processing stream chunk: {e}")
                                    continue
                    # If stream completes successfully, break retry loop
                    break
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RequestError,
                ) as e:
                    logging.error(
                        f"LLM API error during {function_name} (Attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        logging.error(f"Failed to complete {function_name} after {self.max_retries} attempts.")
                        return None
                except Exception as e:
                    logging.error(
                        f"An unexpected error occurred during {function_name} stream "
                        f"(Attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        return None

        if full_response:
            # Mimic the non-streaming response structure
            return {"choices": [{"message": {"content": full_response.strip()}}]}
        else:
            logging.warning(f"LLM call for {function_name} resulted in an empty response.")
            return None

    def generate_questions(
        self,
        text: str,
        temperature: float,
        max_tokens: int,
        pbar: tqdm | None = None,
    ) -> list[str] | None:
        """Generate questions from code/text using LLM."""
        system_prompt = self.prompt_manager.get_prompt("question_system")
        user_prompt_template = self.prompt_manager.get_prompt("question_user")

        # Truncate input text to fit in context window
        safe_limit = self.context_window - max_tokens - 1000
        if safe_limit < 500:
            safe_limit = 500
        truncated_text = self._truncate_content(text, safe_limit)

        # Format user prompt with context
        user_prompt = user_prompt_template.replace(
            "[The actual code/text content will be inserted here by the system]",
            truncated_text,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Use configured token limits for questions
        min_question_tokens = self.config.model.generation.min_question_tokens
        max_question_tokens = self.config.model.generation.max_question_tokens
        # Use the average as a target for question generation
        question_token_limit = (min_question_tokens + max_question_tokens) // 2
        options = {"temperature": temperature, "max_tokens": question_token_limit}
        response_json = self._call_llm_api(messages, options, "generate_questions", pbar=pbar)

        if response_json is None or not response_json.get("choices"):
            logging.warning("No response or choices from LLM API for question generation.")
            return None

        generated_text = response_json["choices"][0]["message"]["content"]
        # Split by newline and filter for valid questions
        all_questions = [
            q.strip()
            for q in generated_text.split("\n")
            if q.strip() and len(q.strip()) >= 100 and len(q.strip()) <= 300 and (q.strip().endswith("?") or "?" in q)
        ]

        # Enforce strict limit of 5 high-quality questions
        questions = all_questions[:5]

        if not questions:
            logging.warning("LLM generated no valid questions or questions don't meet length requirements (100-300 chars).")
            return None
        return questions

    def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float,
        max_tokens: int,
        pbar: tqdm | None = None,
    ) -> str | None:
        """Generate answer for a single question given context."""
        instructional_part = self.prompt_manager.get_prompt("answer_system")

        # Use configured token limits for answer context
        min_answer_context_tokens = self.config.model.generation.min_answer_context_tokens
        max_answer_context_tokens = self.config.model.generation.max_answer_context_tokens

        # Calculate appropriate context window for answer generation
        safe_limit = self.context_window - max_tokens - 500
        if safe_limit < 500:
            safe_limit = 500

        # Ensure context is within our target range
        min_context = min_answer_context_tokens
        max_context = min(max_answer_context_tokens, safe_limit)
        final_context_limit = min(max_context, max(min_context, safe_limit))  # Ensure it's within both bounds

        truncated_context = self._truncate_content(context, final_context_limit)

        system_prompt = f"""
You are a highly intelligent AI assistant specializing in code analysis and
comprehension.

{instructional_part}
        """.strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{truncated_context}\n\nQuestion: {question}\n\nAnswer:",
            },
        ]
        # Use configured token limits for answer generation
        answer_token_limit = max_tokens
        options = {
            "temperature": temperature,
            "max_tokens": answer_token_limit,
        }
        response_json = self._call_llm_api(messages, options, "get_answer_single", pbar=pbar)
        if response_json is None or not response_json.get("choices"):
            logging.warning("No response or choices from LLM API for answer generation.")
            return None  # Indicate failure

        return response_json["choices"][0]["message"]["content"].strip()

    def get_answers_batch(
        self,
        batch_of_question_context_tuples: list[tuple[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> list[str | None]:
        """Generate answers for multiple questions sequentially."""
        results: list[str | None] = []

        # Process sequentially (single-threaded as requested)
        for i, (question, context) in enumerate(batch_of_question_context_tuples):
            try:
                result = self.get_answer_single(question, context, temperature, max_tokens)
                results.append(result)
            except Exception as e:
                logging.error(f"Error processing question batch item {i}: {e}")
                results.append(None)

        return results

    def clear_context(self) -> None:
        """Clear context (placeholder for future implementation)."""
        pass

    @property
    def context_window(self) -> int:
        """Return the context window size."""
        return self._context_window

    def _detect_context_window(self) -> int:
        """Attempt to detect context window from the LLM server (e.g., Ollama)."""
        # Default fallback
        default_window = 4096

        # If it looks like Ollama, try to get more details
        if "11434" in self.base_url:
            try:
                show_url = f"{self.base_url}/api/show"
                # Use the configured timeout for consistency
                timeout = httpx.Timeout(self.request_timeout, connect=10.0)
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(show_url, json={"name": self.model_name})
                    if response.status_code == 200:
                        data = response.json()
                        # Ollama sometimes provides this in model_info or parameters
                        # This is a best-effort detection
                        params = data.get("parameters", "")
                        if "num_ctx" in params:
                            import re
                            match = re.search(r"num_ctx\s+(\d+)", params)
                            if match:
                                return int(match.group(1))
            except Exception as e:
                logging.debug(f"Failed to fetch model details from Ollama: {e}")

        return default_window

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """
        Truncate content based on actual tokenization when possible.
        Uses pre-tokenizer for more accurate truncation.
        """
        if not content:
            return ""

        # Use the pre-tokenizer for accurate truncation
        return self.pretokenizer.cache.truncate_to_tokens(content, max_tokens)

    def validate_request_size(self,
                            prompt: str,
                            expected_output_tokens: int = 100) -> Tuple[bool, str]:
        """
        Validate if a request will fit within context limits before sending to LLM.

        Args:
            prompt: The prompt to validate
            expected_output_tokens: Expected output tokens to reserve

        Returns:
            Tuple of (is_valid, message)
        """
        return self.pretokenizer.validate_request_size(
            prompt,
            self._context_window,
            expected_output_tokens
        )

    def prepare_and_validate_request(self,
                                   system_message: str,
                                   user_message: str,
                                   expected_output_tokens: int = 100) -> Tuple[bool, str, Optional[str]]:
        """
        Prepare and validate a complete request in one step.

        Args:
            system_message: System message content
            user_message: User message content
            expected_output_tokens: Expected output tokens to reserve

        Returns:
            Tuple of (is_valid, message, prepared_prompt_or_none)
        """
        return self.pretokenizer.prepare_and_validate(
            system_message,
            user_message,
            self._context_window,
            expected_output_tokens
        )
