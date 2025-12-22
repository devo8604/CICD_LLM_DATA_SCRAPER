"""Unit tests for the MLXClient."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.llm.mlx_client import MLXClient


class TestMLXClient:
    """Test cases for MLXClient."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Check if MLX is available, skip tests if not
        import importlib.util

        if importlib.util.find_spec("mlx.core"):
            self.mlx_available = True
        else:
            self.mlx_available = False

    def test_mlx_client_initialization(self):
        """Test MLX client initialization."""
        if not self.mlx_available:
            # Test that proper error is raised when MLX is not available
            with patch("src.llm.mlx.model_manager.MLX_AVAILABLE", False):
                with pytest.raises(ImportError):
                    MLXClient(model_name="test-model")
            return

        with (
            patch("src.llm.mlx.model_manager.load") as mock_load,
            patch("src.llm.mlx.model_manager.mx.gpu"),
            patch("src.llm.mlx.model_manager.platform.system", return_value="Darwin"),
            patch("src.llm.mlx.model_manager.platform.machine", return_value="arm64"),
        ):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            assert client.model_name == "test-model"
            assert client.config == config
            mock_load.assert_called_once()

    def test_generate_questions(self):
        """Test question generation."""
        if not self.mlx_available:
            return

        with (
            patch("src.llm.mlx.model_manager.load") as mock_load,
            patch("src.llm.mlx.model_manager.mx.gpu"),
            patch("src.llm.mlx.model_manager.platform.system", return_value="Darwin"),
            patch("src.llm.mlx.model_manager.platform.machine", return_value="arm64"),
        ):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch(
                "src.llm.mlx_client.MLXClient._generate_text_sync",
                return_value="Q1: What does this function do?",
            ):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                content = "def hello(): print('Hello World')"
                result = client.generate_questions(content, temperature=0.7, max_tokens=100)

                assert result is not None
                assert len(result) >= 1
                assert "What does this function do?" in result[0]

    def test_get_answer_single(self):
        """Test single answer generation."""
        if not self.mlx_available:
            return

        with (
            patch("src.llm.mlx.model_manager.load") as mock_load,
            patch("src.llm.mlx.model_manager.mx.gpu"),
            patch("src.llm.mlx.model_manager.platform.system", return_value="Darwin"),
            patch("src.llm.mlx.model_manager.platform.machine", return_value="arm64"),
        ):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch(
                "src.llm.mlx_client.MLXClient._generate_text_sync",
                return_value="This function prints Hello World",
            ):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                question = "What does this function do?"
                context = "def hello(): print('Hello World')"
                result = client.get_answer_single(question, context, temperature=0.7, max_tokens=100)

                assert result is not None
                assert "Hello World" in result

    def test_clear_context(self):
        """Test clear context method."""
        if not self.mlx_available:
            return

        with (
            patch("src.llm.mlx.model_manager.load") as mock_load,
            patch("src.llm.mlx.model_manager.mx.gpu"),
            patch("src.llm.mlx.model_manager.platform.system", return_value="Darwin"),
            patch("src.llm.mlx.model_manager.platform.machine", return_value="arm64"),
        ):
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            client.clear_context()