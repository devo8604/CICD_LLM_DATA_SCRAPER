"Comprehensive unit tests for the LLMClient class."

import json
import time
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import httpx
import pytest

from src.core.config import AppConfig
from src.llm.llm_client import LLMClient


def create_test_config():
    """Create a configured mock config for testing."""
    config = MagicMock(spec=AppConfig)
    config.model.generation.default_max_tokens = 4096
    config.model.generation.min_answer_context_tokens = 256
    config.model.generation.max_answer_context_tokens = 1024
    config.model.generation.min_question_tokens = 25
    config.model.generation.max_question_tokens = 75
    config.model.pipeline.prompt_theme = "devops"
    config.model.llm.model_cache_ttl = 300
    config.model.llm.request_timeout = 300
    return config


class MockClient:
    """Mock context manager for httpx.Client."""

    def __init__(self, mock_response=None, side_effect=None):
        self.mock_response = mock_response
        self.side_effect = side_effect
        self.get_called = False
        self.post_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get(self, url):
        self.get_called = True
        if self.side_effect:
            raise self.side_effect
        return self.mock_response

    def stream(self, method, url, **kwargs):
        self.post_called = True
        return MockStreamResponse(self.mock_response, self.side_effect)


class MockStreamResponse:
    """Mock streaming response context manager."""

    def __init__(self, mock_data=None, side_effect=None):
        self.mock_data = mock_data or []
        self.side_effect = side_effect
        self.status_code = 200

    def __enter__(self):
        if self.side_effect:
            raise self.side_effect
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=Mock(), response=Mock())

    def iter_lines(self):
        yield from self.mock_data


class TestLLMClientInitialization:
    """Test cases for LLMClient initialization."""

    def test_lazy_initialization(self):
        """Test that LLMClient does not fetch models during __init__."""
        with patch("src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper") as mock_wrapper:
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="test-model",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            assert client.base_url == "http://localhost:8000"
            assert client.model_name == "test-model"
            assert client._initialized is False
            mock_wrapper.assert_not_called()

    @patch("src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper")
    def test_initialization_with_unavailable_model(self, mock_wrapper):
        """Test initialization when specified model is not available."""
        # Mock the model list response without the requested model
        mock_wrapper.return_value = ["model1", "model2"]

        client = LLMClient(
            base_url="http://localhost:8000",
            model_name="unavailable-model",
            max_retries=3,
            retry_delay=5,
            config=create_test_config(),
        )

        # Access property to trigger lazy initialization
        _ = client.context_window

        # Should fall back to first available model
        assert client.model_name == "model1"
        assert client._initialized is True

    @patch("src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper")
    def test_initialization_with_no_models(self, mock_wrapper):
        """Test initialization fails when no models are available."""
        # Mock empty model list
        mock_wrapper.return_value = []

        client = LLMClient(
            base_url="http://localhost:8000",
            model_name="test-model",
            max_retries=3,
            retry_delay=5,
            config=create_test_config(),
        )

        with pytest.raises(ValueError, match="No usable LLM model available"):
            # Access property to trigger lazy initialization
            _ = client.context_window

    @patch("src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper")
    def test_initialization_with_connection_error(self, mock_wrapper):
        """Test initialization fails when unable to connect to server."""
        # Mock connection failure
        mock_wrapper.side_effect = Exception("Connection failed")

        client = LLMClient(
            base_url="http://localhost:8000",
            model_name="test-model",
            max_retries=3,
            retry_delay=5,
            config=create_test_config(),
        )

        with pytest.raises(Exception, match="Connection failed"):
            # Access property to trigger lazy initialization
            _ = client.context_window


class TestLLMClientModelList:
    """Test cases for model list retrieval."""

    def test_get_available_models_success(self):
        """Test successful retrieval of model list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "model1"}, {"id": "model2"}, {"id": "model3"}]}
        mock_client = MockClient(mock_response=mock_response)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1", "model2"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Create a client for testing
        with patch("httpx.Client", return_value=mock_client):
            with httpx.Client() as sync_client:
                models = client._get_available_llm_models(sync_client)

        assert models == ["model1", "model2", "model3"]
        assert mock_client.get_called

    def test_get_available_models_fetch_and_cache(self):
        """Test that model list is fetched and cached when cache is empty/expired."""
        mock_response_payload = {"data": [{"id": "model1"}, {"id": "model2"}]}
        mock_http_response = MagicMock(status_code=200)
        mock_http_response.json.return_value = mock_response_payload

        mock_client_instance = MockClient(mock_response=mock_http_response)

        # Ensure cache is empty initially
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        with patch("httpx.Client", return_value=mock_client_instance):
            with httpx.Client() as sync_client:
                models = client._get_available_llm_models(sync_client)

        assert models == ["model1", "model2"]
        assert mock_client_instance.get_called  # Ensure HTTP call was made
        assert LLMClient._model_cache == ["model1", "model2"]
        assert LLMClient._model_cache_time is not None

    def test_get_available_models_use_cache(self):
        """Test that model list uses cache when available and not expired."""
        cached_models = ["cached_model1", "cached_model2"]

        # This patch for asyncio.run is for the LLMClient.__init__ call
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=cached_models,
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Now, for the actual _get_available_llm_models call, we mock its internal cache state
        # We need to explicitly set _model_cache_ttl as well, as it's used in the check
        with (
            patch("src.llm.llm_client.LLMClient._model_cache", new=cached_models),
            patch("src.llm.llm_client.LLMClient._model_cache_time", new=time.time()),
            patch(
                "src.core.config.AppConfig.LLM_MODEL_CACHE_TTL",
                new_callable=PropertyMock,
                return_value=300,
            ),
            patch("time.time", side_effect=[time.time(), time.time() + 1]),
        ):  # ensure current_time > _model_cache_time but within TTL
            mock_get = MagicMock(side_effect=AssertionError("HTTP GET should not be called"))
            mock_client_instance = MagicMock()
            mock_client_instance.get = mock_get
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)

            with patch("httpx.Client", return_value=mock_client_instance):
                with httpx.Client() as sync_client:
                    models = client._get_available_llm_models(sync_client)

            assert models == cached_models
            mock_get.assert_not_called()  # Ensure HTTP GET was NOT called

    def test_get_available_models_connection_error(self):
        """Test handling of connection errors when fetching models."""
        mock_client = MockClient(side_effect=httpx.ConnectError("Connection refused"))

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch("httpx.Client", return_value=mock_client):
            with httpx.Client() as sync_client:
                models = client._get_available_llm_models(sync_client)

        assert models == []

    def test_get_available_models_timeout(self):
        """Test handling of timeout when fetching models."""
        mock_client = MockClient(side_effect=httpx.ReadTimeout("Timeout"))

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch("httpx.Client", return_value=mock_client):
            with httpx.Client() as sync_client:
                models = client._get_available_llm_models(sync_client)

        assert models == []

    def test_get_available_models_json_decode_error(self):
        """Test handling of JSON decode errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Error", "", 0)
        mock_response.text = "Invalid JSON"

        mock_client = MockClient(mock_response=mock_response)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch("httpx.Client", return_value=mock_client):
            with httpx.Client() as sync_client:
                models = client._get_available_llm_models(sync_client)

        assert models == []


class TestLLMClientAPICall:
    """Test cases for LLM API calls."""

    def test_successful_api_call_with_streaming(self):
        """Test successful API call with streaming response."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            "data: [DONE]",
        ]

        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        with patch("httpx.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            # `stream` method should return an async context manager
            mock_stream_ctx_manager = MagicMock()
            mock_stream_ctx_manager.__enter__.return_value = mock_stream
            mock_client_instance.stream.return_value = mock_stream_ctx_manager

            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = client._call_llm_api(messages, options, "test_function")

        assert result is not None
        assert result["choices"][0]["message"]["content"] == "Hello world"

    def test_api_call_with_retry_on_connection_error(self):
        """Test API call retries on connection errors."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=1,
                config=create_test_config(),  # Short delay for testing
            )

        call_count = 0

        def mock_stream_enter_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            return MockStreamResponse(mock_data=['data: {"choices": [{"delta": {"content": "Success"}}]}'])

        with patch("httpx.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_stream_ctx_manager = MagicMock()
            mock_stream_ctx_manager.__enter__.side_effect = mock_stream_enter_side_effect
            mock_stream_ctx_manager.__exit__ = MagicMock(return_value=None)
            mock_client_instance.stream.return_value = mock_stream_ctx_manager

            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = client._call_llm_api(messages, options, "test_function")

        assert call_count == 3
        assert result is not None

    def test_api_call_max_retries_exceeded(self):
        """Test API call returns None after max retries exceeded."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=2,
                retry_delay=0.1,
                config=create_test_config(),
            )

        with patch("httpx.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_stream_ctx_manager = MagicMock()
            mock_stream_ctx_manager.__enter__.side_effect = httpx.ConnectError("Connection failed")
            mock_stream_ctx_manager.__exit__ = MagicMock(return_value=None)
            mock_client_instance.stream.return_value = mock_stream_ctx_manager

            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = client._call_llm_api(messages, options, "test_function")

        assert result is None

    def test_api_call_handles_empty_stream(self):
        """Test API call handles empty streaming response."""
        stream_data = ["data: [DONE]"]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        with patch("httpx.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_stream_ctx_manager = MagicMock()
            mock_stream_ctx_manager.__enter__.return_value = mock_stream
            mock_stream_ctx_manager.__exit__ = MagicMock(return_value=None)
            mock_client_instance.stream.return_value = mock_stream_ctx_manager

            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = client._call_llm_api(messages, options, "test_function")

        # Should return None for empty response
        assert result is None


class TestLLMClientQuestionGeneration:
    """Test cases for question generation."""

    def test_generate_questions_success(self):
        """Test successful question generation."""
        # Use longer questions (> 100 chars) to pass length filter
        q1 = "How does the initialization of the LLMClient handle the case where the requested model is not found on the server?"
        q2 = "What is the primary difference between the streaming and non-streaming response handling in the internal API call method?"

        # Construct data strings manually to avoid f-string escaping issues
        d1 = "data: " + json.dumps({"choices": [{"delta": {"content": q1}}]})
        d2 = "data: " + json.dumps({"choices": [{"delta": {"content": "\n" + q2}}]})

        stream_data = [d1, d2, "data: [DONE]"]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch("httpx.Client") as mock_client_class:
                mock_client_instance = MagicMock()
                mock_stream_ctx_manager = MagicMock()
                mock_stream_ctx_manager.__enter__.return_value = mock_stream
                mock_client_instance.stream.return_value = mock_stream_ctx_manager

                mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
                mock_client_instance.__exit__ = MagicMock(return_value=None)
                mock_client_class.return_value = mock_client_instance

                questions = client.generate_questions(text="Test code snippet", temperature=0.7, max_tokens=100)

        assert questions is not None
        assert len(questions) == 2
        assert q1 in questions
        assert q2 in questions

    def test_generate_questions_no_response(self):
        """Test question generation with no LLM response."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch.object(client, "_call_llm_api", return_value=None):
                questions = client.generate_questions(text="Test code snippet", temperature=0.7, max_tokens=100)

        assert questions is None

    def test_generate_questions_filters_non_questions(self):
        """Test that non-question lines are filtered out."""
        q1 = "How does the initialization of the LLMClient handle the case where the requested model is not found on the server?"
        q2 = "What is the primary difference between the streaming and non-streaming response handling in the internal API call method?"
        statement = "This is a very long statement that is definitely longer than one hundred characters but it does not end with a question mark so it should be filtered."

        d1 = "data: " + json.dumps({"choices": [{"delta": {"content": q1}}]})
        ds = "data: " + json.dumps({"choices": [{"delta": {"content": "\n" + statement}}]})
        d2 = "data: " + json.dumps({"choices": [{"delta": {"content": "\n" + q2}}]})

        stream_data = [d1, ds, d2, "data: [DONE]"]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch("httpx.Client") as mock_client_class:
                mock_client_instance = MagicMock()
                mock_stream_ctx_manager = MagicMock()
                mock_stream_ctx_manager.__enter__.return_value = mock_stream
                mock_client_instance.stream.return_value = mock_stream_ctx_manager

                mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
                mock_client_instance.__exit__ = MagicMock(return_value=None)
                mock_client_class.return_value = mock_client_instance

                questions = client.generate_questions(text="Test code snippet", temperature=0.7, max_tokens=100)

        # Should only include lines ending with '?'
        assert len(questions) == 2
        assert all(q.endswith("?") for q in questions)

    def test_generate_questions_enforces_limit(self):
        """Test that question generation strictly enforces a maximum of 5 questions."""
        qs = [f"This is question number {i} and it is long enough to pass the length requirement filter, don't you think?" for i in range(1, 7)]
        content = "\n".join(qs)

        d = "data: " + json.dumps({"choices": [{"delta": {"content": content}}]})
        stream_data = [d, "data: [DONE]"]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch("httpx.Client") as mock_client_class:
                mock_client_instance = MagicMock()
                mock_stream_ctx_manager = MagicMock()
                mock_stream_ctx_manager.__enter__.return_value = mock_stream
                mock_client_instance.stream.return_value = mock_stream_ctx_manager

                mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
                mock_client_instance.__exit__ = MagicMock(return_value=None)
                mock_client_class.return_value = mock_client_instance

                questions = client.generate_questions(text="Test content", temperature=0.7, max_tokens=100)

        # Should be exactly 5 even if LLM provided 6
        assert len(questions) == 5
        assert questions == qs[:5]


class TestLLMClientAnswerGeneration:
    """Test cases for answer generation."""

    def test_get_answer_single_success(self):
        """Test successful single answer generation."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "This is"}}]}',
            'data: {"choices": [{"delta": {"content": " the answer."}}]}',
            "data: [DONE]",
        ]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch("httpx.Client") as mock_client_class:
                mock_client_instance = MagicMock()
                mock_stream_ctx_manager = MagicMock()
                mock_stream_ctx_manager.__enter__.return_value = mock_stream
                mock_client_instance.stream.return_value = mock_stream_ctx_manager

                mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
                mock_client_instance.__exit__ = MagicMock(return_value=None)
                mock_client_class.return_value = mock_client_instance

                answer = client.get_answer_single(
                    question="What is this?",
                    context="Test context",
                    temperature=0.7,
                    max_tokens=100,
                )

        assert answer == "This is the answer."

    def test_get_answer_single_no_response(self):
        """Test single answer generation with no response."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

            with patch.object(client, "_call_llm_api", return_value=None):
                answer = client.get_answer_single(
                    question="What is this?",
                    context="Test context",
                    temperature=0.7,
                    max_tokens=100,
                )

        assert answer is None

    def test_get_answers_batch(self):
        """Test batch answer generation."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Mock get_answer_single to return different answers
        def mock_get_answer(question, context, temperature, max_tokens):
            return f"Answer to: {question}"

        with patch.object(client, "get_answer_single", side_effect=mock_get_answer):
            batch = [
                ("Question 1?", "Context 1"),
                ("Question 2?", "Context 2"),
                ("Question 3?", "Context 3"),
            ]

            answers = client.get_answers_batch(batch_of_question_context_tuples=batch, temperature=0.7, max_tokens=100)

        assert len(answers) == 3
        assert answers[0] == "Answer to: Question 1?"
        assert answers[1] == "Answer to: Question 2?"
        assert answers[2] == "Answer to: Question 3?"


class TestLLMClientUtilities:
    """Test utility methods."""

    def test_clear_context(self):
        """Test clear_context method (placeholder)."""
        with patch(
            "src.llm.llm_client.LLMClient._get_available_llm_models_sync_wrapper",
            return_value=["model1"],
        ):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5,
                config=create_test_config(),
            )

        # Should not raise any errors
        client.clear_context()
