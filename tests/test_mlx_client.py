"""Unit tests for the MLXClient."""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from src.mlx_client import MLXClient
from src.config import AppConfig


class TestMLXClient:
    """Test cases for MLXClient."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Check if MLX is available, skip tests if not
        try:
            import mlx.core as mx
            self.mlx_available = True
        except ImportError:
            self.mlx_available = False

    def test_mlx_client_initialization(self):
        """Test MLX client initialization."""
        if not self.mlx_available:
            # Test that proper error is raised when MLX is not available
            with patch('src.mlx_client.MLX_AVAILABLE', False):
                with pytest.raises(ImportError):
                    MLXClient(model_name="test-model")
            return

        # If MLX is available, test normal initialization
        # For this test, we'll mock the MLX library to avoid actual model loading
        # and mock the platform check to allow initialization in test environment
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            config = AppConfig()
            client = MLXClient(
                model_name="test-model",
                config=config
            )

            assert client.model_name == "test-model"
            assert client.config == config
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_questions(self):
        """Test question generation."""
        if not self.mlx_available:
            # Skip if MLX not available
            return

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch('src.mlx_client.MLXClient._generate_text_sync', return_value="What does this function do?"):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                content = "def hello(): print('Hello World')"
                result = await client.generate_questions(content, temperature=0.7, max_tokens=100)

                assert result is not None
                assert len(result) >= 1
                assert "What does this function do?" in result

    @pytest.mark.asyncio
    async def test_get_answer_single(self):
        """Test single answer generation."""
        if not self.mlx_available:
            # Skip if MLX not available
            return

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch('src.mlx_client.MLXClient._generate_text_sync', return_value="This function prints Hello World"):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                question = "What does this function do?"
                context = "def hello(): print('Hello World')"
                result = await client.get_answer_single(question, context, temperature=0.7, max_tokens=100)

                assert result is not None
                assert "Hello World" in result

    def test_clear_context(self):
        """Test clear context method."""
        if not self.mlx_available:
            # Skip if MLX not available
            return

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            # This should not raise any exceptions
            client.clear_context()
            # MLX is stateless for generation, so no specific action needed