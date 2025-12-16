import json
import logging
import httpx
import asyncio
import time

from src.config import AppConfig

# Initialize config instance
config = AppConfig()


class LLMClient:
    """LLM client with caching and retry logic for OpenAI-compatible APIs."""

    # Class-level cache for model list
    _model_cache: list[str] | None = None
    _model_cache_time: float | None = None
    _model_cache_ttl: int = config.LLM_MODEL_CACHE_TTL

    def __init__(
        self,
        base_url: str,
        model_name: str,
        max_retries: int,
        retry_delay: int,
    ) -> None:
        self.base_url = base_url
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logging.info(
            f"LLMClient initialized. Using model: {self.model_name} at {base_url}"
        )

        try:
            # Call async method from sync __init__ using asyncio.run for initial check
            available_models = asyncio.run(self._get_available_llm_models_sync_wrapper())
        except Exception as e:
            logging.critical(f"An unexpected error occurred during initial model fetch: {e}", exc_info=True)
            available_models = []

        if available_models:
            if self.model_name in available_models:
                logging.info(f"Using specified model: {self.model_name}")
            else:
                logging.warning(
                    f"Specified model '{self.model_name}' not found on the LLM server."
                )
                logging.info(f"Available models: {', '.join(available_models)}")
                if available_models:
                    # Fallback to the first available model
                    original_model_name = self.model_name
                    self.model_name = available_models[0]
                    logging.info(
                        f"Requested model '{original_model_name}' not found. Falling back to first available model: {self.model_name}"
                    )
                else:
                    logging.critical(
                        "No models available on the LLM server. Please load a model."
                    )
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
            raise ValueError(
                "No usable LLM model available or configured. Check LLM server and model loads."
            )

    async def _get_available_llm_models_sync_wrapper(self) -> list[str]:
        """Wrapper to manage async client lifecycle."""
        async with httpx.AsyncClient() as client:
            return await self._get_available_llm_models(client)

    async def _get_available_llm_models(self, client: httpx.AsyncClient) -> list[str]:
        """Fetch available models with caching."""
        # Check cache first
        current_time = time.time()
        if (
            LLMClient._model_cache is not None
            and LLMClient._model_cache_time is not None
            and (current_time - LLMClient._model_cache_time) < LLMClient._model_cache_ttl
        ):
            logging.debug("Using cached model list")
            return LLMClient._model_cache

        models_api_url = f"{self.base_url}/v1/models"
        try:
            response = await client.get(models_api_url, timeout=30)  # 30 second timeout
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            models_data = response.json()
            logging.info(f"Raw models response from server: {models_data}")
            # Assuming OpenAI-compatible API response structure: {"data": [{"id": "model_name", ...}]}
            models = [m["id"] for m in models_data.get("data", [])]

            # Update cache
            LLMClient._model_cache = models
            LLMClient._model_cache_time = current_time

            return models
        except httpx.ConnectError as e:
            logging.error(f"Could not connect to LLM server at {models_api_url}: {e}")
            return []
        except httpx.TimeoutException:
            logging.error(
                f"Timeout while connecting to LLM server at {models_api_url}."
            )
            return []
        except httpx.RequestError as e:  # Catch all httpx request errors
            logging.error(
                f"Failed to retrieve LLM model list from {models_api_url}: {e}"
            )
            return []
        except json.JSONDecodeError:
            logging.error(
                f"Failed to decode JSON from LLM server at {models_api_url}. Response: {response.text[:200]}..."
            )
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred while getting model list: {e}")
            return []

    async def _call_llm_api(
        self,
        messages: list[dict[str, str]],
        options: dict[str, int | float],
        function_name: str,
        pbar: "tqdm | None" = None,
    ) -> dict[str, any] | None:
        """Call LLM API with retry logic and streaming."""
        chat_completions_url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": options.get("temperature", 0.7),
            "max_tokens": options.get("max_tokens", 500),
            "stream": True,  # Enable streaming
        }

        full_response = ""
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                try:
                    async with client.stream(
                        "POST", chat_completions_url, headers=headers, json=payload, timeout=300
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
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
                    logging.info(f"LLM streaming response for {function_name} completed.")
                    # If stream completes successfully, break retry loop
                    break
                except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
                    logging.error(
                        f"LLM API error during {function_name} (Attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        logging.error(f"Failed to complete {function_name} after {self.max_retries} attempts.")
                        return None
                except Exception as e:
                     logging.error(
                        f"An unexpected error occurred during {function_name} stream (Attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                     if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                     else:
                        return None
        logging.info(f"LLM API call for {function_name} finished all retries.")
        if full_response:
            logging.info(f"Returning successful response for {function_name}.")
            # Mimic the non-streaming response structure
            return {"choices": [{"message": {"content": full_response.strip()}}]}
        else:
            logging.warning(f"LLM call for {function_name} resulted in an empty response.")
            return None

    async def generate_questions(
        self,
        text: str,
        temperature: float,
        max_tokens: int,
        pbar: "tqdm | None" = None,
    ) -> list[str] | None:
        """Generate questions from code/text using LLM."""
        system_prompt = """
        You are an expert data generation engine tasked with creating a high-quality,
        diverse dataset for fine-tuning a powerful Code Large Language Model. Your goal
        is to generate as many unique, challenging, and highly relevant questions as
        possible *strictly about the provided code/text*. Each question must be answerable
        *solely and directly from the content of the 'Code/Text to analyze'*. Prioritize
        understanding this specific code/text rather than general knowledge or external
        contexts. While topics like CI/CD, Kubernetes, cloud-native technologies,
        infrastructure as code, related DevOps practices, shell scripting, and automation
        are relevant, questions about them should ONLY be asked if they are *explicitly
        present or strongly implied* within the given code/text. Do NOT generate questions
        that require external knowledge not explicitly present or directly inferable from
        the provided text. Vary the complexity of questions. Include some simple Q&A, some
        medium-difficulty concepts, and at least two complex tasks. Ensure no two questions
        are too similar in topic. Output ONLY the questions, one per line, with no preamble,
        explanations, or text outside the question list.
        """.strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Code/Text to analyze:\n{text}\n\nQuestions:"},
        ]
        options = {"temperature": temperature, "max_tokens": max_tokens}
        response_json = await self._call_llm_api(
            messages, options, "generate_questions", pbar=pbar
        )

        if response_json is None or not response_json.get("choices"):
            logging.warning(
                "No response or choices from LLM API for question generation."
            )
            return None  # Indicate failure instead of fallback string

        generated_text = response_json["choices"][0]["message"]["content"]
        questions = [
            q.strip()
            for q in generated_text.split("\n")
            if q.strip() and q.strip().endswith("?")
        ]
        if not questions:  # Fallback if parsing fails
            logging.warning("LLM generated no valid questions.")
            return None  # Indicate failure
        return questions

    async def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float,
        max_tokens: int,
        pbar: "tqdm | None" = None,
    ) -> str | None:
        """Generate answer for a single question given context."""
        system_prompt = """
        You are a highly intelligent AI assistant specializing in code analysis and
        comprehension. Answer the following question, leveraging both the provided context
        and your broader knowledge base. Prioritize information from the context, but use
        your general knowledge to provide a comprehensive answer if the context is
        insufficient. If the context directly contradicts your broader knowledge, use the
        context's information.
        """.strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"},
        ]
        options = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response_json = await self._call_llm_api(
            messages, options, "get_answer_single", pbar=pbar
        )
        if response_json is None or not response_json.get("choices"):
            logging.warning(
                "No response or choices from LLM API for answer generation."
            )
            return None  # Indicate failure

        return response_json["choices"][0]["message"]["content"].strip()

    async def get_answers_batch(
        self,
        batch_of_question_context_tuples: list[tuple[str, str]],
        temperature: float,
        max_tokens: int
    ) -> list[str | None]:
        """Generate answers for multiple questions in parallel using TaskGroup."""
        results: list[str | None] = [None] * len(batch_of_question_context_tuples)

        # Python 3.11+ TaskGroup for better structured concurrency
        async with asyncio.TaskGroup() as tg:
            tasks = []
            for i, (question, context) in enumerate(batch_of_question_context_tuples):
                task = tg.create_task(
                    self.get_answer_single(question, context, temperature, max_tokens)
                )
                tasks.append((i, task))

        # Collect results
        for i, task in tasks:
            try:
                results[i] = task.result()
            except Exception as e:
                logging.error(f"Error processing question batch item {i}: {e}")
                results[i] = None

        return results

    def clear_context(self) -> None:
        """Clear context (placeholder for future implementation)."""
        pass
