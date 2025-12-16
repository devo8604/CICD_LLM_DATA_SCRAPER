"""Comprehensive unit tests for the LLMClient class."""

import pytest
import asyncio
import json
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from src.llm_client import LLMClient
from src.config import AppConfig


class MockAsyncClient:
    """Mock async context manager for httpx.AsyncClient."""

    def __init__(self, mock_response=None, side_effect=None):
        self.mock_response = mock_response
        self.side_effect = side_effect
        self.get_called = False
        self.post_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url):
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

    async def __aenter__(self):
        if self.side_effect:
            raise self.side_effect
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=Mock(), response=Mock())

    async def aiter_lines(self):
        for line in self.mock_data:
            yield line


class TestLLMClientInitialization:
    """Test cases for LLMClient initialization."""

    @patch('src.llm_client.asyncio.run')
    def test_successful_initialization(self, mock_run):
        """Test successful LLMClient initialization with available models."""
        # Mock the model list response
        mock_run.return_value = ["model1", "model2", "test-model"]

        client = LLMClient(
            base_url="http://localhost:8000",
            model_name="test-model",
            max_retries=3,
            retry_delay=5
        )

        assert client.base_url == "http://localhost:8000"
        assert client.model_name == "test-model"
        assert client.max_retries == 3
        assert client.retry_delay == 5

    @patch('src.llm_client.asyncio.run')
    def test_initialization_with_unavailable_model(self, mock_run):
        """Test initialization when specified model is not available."""
        # Mock the model list response without the requested model
        mock_run.return_value = ["model1", "model2"]

        client = LLMClient(
            base_url="http://localhost:8000",
            model_name="unavailable-model",
            max_retries=3,
            retry_delay=5
        )

        # Should fall back to first available model
        assert client.model_name == "model1"

    @patch('src.llm_client.asyncio.run')
    def test_initialization_with_no_models(self, mock_run):
        """Test initialization when no models are available."""
        # Mock empty model list
        mock_run.return_value = []

        with pytest.raises(ValueError, match="No usable LLM model available"):
            LLMClient(
                base_url="http://localhost:8000",
                model_name="test-model",
                max_retries=3,
                retry_delay=5
            )

    @patch('src.llm_client.asyncio.run')
    def test_initialization_with_connection_error(self, mock_run):
        """Test initialization when unable to connect to server."""
        # Mock connection failure
        mock_run.return_value = []

        with pytest.raises(ValueError, match="No usable LLM model available"):
            LLMClient(
                base_url="http://localhost:8000",
                model_name="test-model",
                max_retries=3,
                retry_delay=5
            )


class TestLLMClientModelList:
    """Test cases for model list retrieval."""

    @pytest.mark.asyncio
    async def test_get_available_models_success(self):
        """Test successful retrieval of model list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "model1"},
                {"id": "model2"},
                {"id": "model3"}
            ]
        }
        mock_client = MockAsyncClient(mock_response=mock_response)

        with patch('src.llm_client.asyncio.run', return_value=["model1", "model2"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Create a real async client for testing
        with patch('httpx.AsyncClient', return_value=mock_client):
            async with httpx.AsyncClient() as async_client:
                models = await client._get_available_llm_models(async_client)

        assert models == ["model1", "model2", "model3"]
        assert mock_client.get_called

    @pytest.mark.asyncio
    async def test_get_available_models_with_cache(self):
        """Test that model list is cached."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "model1"}]}

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Set cache
        LLMClient._model_cache = ["cached_model1", "cached_model2"]
        LLMClient._model_cache_time = asyncio.get_event_loop().time()

        mock_client = MockAsyncClient(mock_response=mock_response)

        with patch('httpx.AsyncClient', return_value=mock_client):
            async with httpx.AsyncClient() as async_client:
                models = await client._get_available_llm_models(async_client)

        # Should return cached models, not make new request
        assert models == ["cached_model1", "cached_model2"]

    @pytest.mark.asyncio
    async def test_get_available_models_connection_error(self):
        """Test handling of connection errors when fetching models."""
        mock_client = MockAsyncClient(side_effect=httpx.ConnectError("Connection refused"))

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            async with httpx.AsyncClient() as async_client:
                models = await client._get_available_llm_models(async_client)

        assert models == []

    @pytest.mark.asyncio
    async def test_get_available_models_timeout(self):
        """Test handling of timeout when fetching models."""
        mock_client = MockAsyncClient(side_effect=httpx.ReadTimeout("Timeout"))

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            async with httpx.AsyncClient() as async_client:
                models = await client._get_available_llm_models(async_client)

        assert models == []

    @pytest.mark.asyncio
    async def test_get_available_models_json_decode_error(self):
        """Test handling of JSON decode errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Error", "", 0)
        mock_response.text = "Invalid JSON"

        mock_client = MockAsyncClient(mock_response=mock_response)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Clear cache
        LLMClient._model_cache = None
        LLMClient._model_cache_time = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            async with httpx.AsyncClient() as async_client:
                models = await client._get_available_llm_models(async_client)

        assert models == []


class TestLLMClientAPICall:
    """Test cases for LLM API calls."""

    @pytest.mark.asyncio
    async def test_successful_api_call_with_streaming(self):
        """Test successful API call with streaming response."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            'data: [DONE]'
        ]

        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = mock_stream
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = await client._call_llm_api(messages, options, "test_function")

        assert result is not None
        assert result["choices"][0]["message"]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_api_call_with_retry_on_connection_error(self):
        """Test API call retries on connection errors."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=1  # Short delay for testing
            )

        call_count = 0

        async def mock_stream_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            # Succeed on third attempt
            return MockStreamResponse(mock_data=['data: {"choices": [{"delta": {"content": "Success"}}]}'])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream = mock_stream_side_effect
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = await client._call_llm_api(messages, options, "test_function")

        assert call_count == 3
        assert result is not None

    @pytest.mark.asyncio
    async def test_api_call_max_retries_exceeded(self):
        """Test API call returns None after max retries exceeded."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=2,
                retry_delay=0.1
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.side_effect = httpx.ConnectError("Connection failed")
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = await client._call_llm_api(messages, options, "test_function")

        assert result is None

    @pytest.mark.asyncio
    async def test_api_call_handles_empty_stream(self):
        """Test API call handles empty streaming response."""
        stream_data = ['data: [DONE]']
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = mock_stream
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            messages = [{"role": "user", "content": "Test"}]
            options = {"temperature": 0.7, "max_tokens": 100}

            result = await client._call_llm_api(messages, options, "test_function")

        # Should return None for empty response
        assert result is None


class TestLLMClientQuestionGeneration:
    """Test cases for question generation."""

    @pytest.mark.asyncio
    async def test_generate_questions_success(self):
        """Test successful question generation."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "What is this?"}}]}',
            'data: {"choices": [{"delta": {"content": "\\nHow does it work?"}}]}',
            'data: [DONE]'
        ]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = mock_stream
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            questions = await client.generate_questions(
                text="Test code snippet",
                temperature=0.7,
                max_tokens=100
            )

        assert questions is not None
        assert len(questions) == 2
        assert "What is this?" in questions
        assert "How does it work?" in questions

    @pytest.mark.asyncio
    async def test_generate_questions_no_response(self):
        """Test question generation with no LLM response."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch.object(client, '_call_llm_api', return_value=None):
            questions = await client.generate_questions(
                text="Test code snippet",
                temperature=0.7,
                max_tokens=100
            )

        assert questions is None

    @pytest.mark.asyncio
    async def test_generate_questions_filters_non_questions(self):
        """Test that non-question lines are filtered out."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "What is this?"}}]}',
            'data: {"choices": [{"delta": {"content": "\\nThis is a statement"}}]}',
            'data: {"choices": [{"delta": {"content": "\\nHow does it work?"}}]}',
            'data: [DONE]'
        ]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = mock_stream
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            questions = await client.generate_questions(
                text="Test code snippet",
                temperature=0.7,
                max_tokens=100
            )

        # Should only include lines ending with '?'
        assert len(questions) == 2
        assert all(q.endswith("?") for q in questions)


class TestLLMClientAnswerGeneration:
    """Test cases for answer generation."""

    @pytest.mark.asyncio
    async def test_get_answer_single_success(self):
        """Test successful single answer generation."""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "This is"}}]}',
            'data: {"choices": [{"delta": {"content": " the answer."}}]}',
            'data: [DONE]'
        ]
        mock_stream = MockStreamResponse(mock_data=stream_data)

        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = mock_stream
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            answer = await client.get_answer_single(
                question="What is this?",
                context="Test context",
                temperature=0.7,
                max_tokens=100
            )

        assert answer == "This is the answer."

    @pytest.mark.asyncio
    async def test_get_answer_single_no_response(self):
        """Test single answer generation with no response."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        with patch.object(client, '_call_llm_api', return_value=None):
            answer = await client.get_answer_single(
                question="What is this?",
                context="Test context",
                temperature=0.7,
                max_tokens=100
            )

        assert answer is None

    @pytest.mark.asyncio
    async def test_get_answers_batch(self):
        """Test batch answer generation."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Mock get_answer_single to return different answers
        async def mock_get_answer(question, context, temperature, max_tokens):
            return f"Answer to: {question}"

        with patch.object(client, 'get_answer_single', side_effect=mock_get_answer):
            batch = [
                ("Question 1?", "Context 1"),
                ("Question 2?", "Context 2"),
                ("Question 3?", "Context 3")
            ]

            answers = await client.get_answers_batch(
                batch_of_question_context_tuples=batch,
                temperature=0.7,
                max_tokens=100
            )

        assert len(answers) == 3
        assert answers[0] == "Answer to: Question 1?"
        assert answers[1] == "Answer to: Question 2?"
        assert answers[2] == "Answer to: Question 3?"


class TestLLMClientUtilities:
    """Test utility methods."""

    def test_clear_context(self):
        """Test clear_context method (placeholder)."""
        with patch('src.llm_client.asyncio.run', return_value=["model1"]):
            client = LLMClient(
                base_url="http://localhost:8000",
                model_name="model1",
                max_retries=3,
                retry_delay=5
            )

        # Should not raise any errors
        client.clear_context()
