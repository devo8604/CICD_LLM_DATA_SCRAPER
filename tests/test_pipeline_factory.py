"""Unit tests for the PipelineFactory."""

import tempfile
from unittest.mock import MagicMock, patch
import pytest

from src.pipeline_factory import PipelineFactory
from src.config import AppConfig
from src.data_pipeline import DataPipeline


class TestPipelineFactory:
    """Test cases for PipelineFactory."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.config = AppConfig()
        self.factory = PipelineFactory(config=self.config)

    @patch('src.pipeline_factory.LLMClient')
    def test_create_llm_client(self, mock_llm_client_class):
        """Test creation of LLM client."""
        # Ensure MLX is disabled for this test to use standard LLM client
        original_use_mlx = self.config.USE_MLX
        self.config.USE_MLX = False

        # Mock the LLMClient to avoid actual initialization
        mock_llm_client = MagicMock()
        mock_llm_client_class.return_value = mock_llm_client

        llm_client = self.factory.create_llm_client()

        # Restore original setting
        self.config.USE_MLX = original_use_mlx

        # Verify LLMClient was instantiated with correct parameters
        mock_llm_client_class.assert_called_once_with(
            base_url=self.config.LLM_BASE_URL,
            model_name=self.config.LLM_MODEL_NAME,
            max_retries=self.config.LLM_MAX_RETRIES,
            retry_delay=self.config.LLM_RETRY_DELAY,
        )
        assert llm_client == mock_llm_client

    def test_create_db_manager(self):
        """Test creation of database manager."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            import pathlib
            data_path = pathlib.Path(temp_dir)
            
            db_manager = self.factory.create_db_manager(data_path)
            
            # Verify the DB manager was created with the correct path
            expected_path = data_path / self.config.DB_PATH
            assert db_manager.db_path == expected_path

    def test_create_file_manager(self):
        """Test creation of file manager."""
        test_repos_dir = "/path/to/repos"
        
        file_manager = self.factory.create_file_manager(test_repos_dir)
        
        # Verify the file manager was created with correct settings
        assert file_manager.repos_dir == test_repos_dir
        assert file_manager.max_file_size == self.config.MAX_FILE_SIZE

    @patch('src.pipeline_factory.LLMClient')
    def test_create_data_pipeline(self, mock_llm_client_class):
        """Test creation of complete data pipeline."""
        # Ensure MLX is disabled for this test to use standard LLM client
        original_use_mlx = self.config.USE_MLX
        self.config.USE_MLX = False

        # Mock the LLMClient to avoid actual initialization
        mock_llm_client = MagicMock()
        mock_llm_client_class.return_value = mock_llm_client

        with tempfile.TemporaryDirectory() as temp_dir:
            import pathlib
            data_path = pathlib.Path(temp_dir)
            repos_dir = "/path/to/repos"

            pipeline = self.factory.create_data_pipeline(
                data_dir=data_path,
                repos_dir=repos_dir
            )

            # Restore original setting
            self.config.USE_MLX = original_use_mlx

            # Verify the pipeline was created with proper dependencies
            assert isinstance(pipeline, DataPipeline)
            assert pipeline.max_tokens == self.config.DEFAULT_MAX_TOKENS
            assert pipeline.temperature == self.config.DEFAULT_TEMPERATURE
            assert pipeline.config == self.config

    @patch('src.pipeline_factory.LLMClient')
    def test_create_data_pipeline_with_custom_params(self, mock_llm_client_class):
        """Test creation of data pipeline with custom parameters."""
        # Ensure MLX is disabled for this test to use standard LLM client
        original_use_mlx = self.config.USE_MLX
        self.config.USE_MLX = False

        # Mock the LLMClient to avoid actual initialization
        mock_llm_client = MagicMock()
        mock_llm_client_class.return_value = mock_llm_client

        with tempfile.TemporaryDirectory() as temp_dir:
            import pathlib
            data_path = pathlib.Path(temp_dir)
            repos_dir = "/path/to/repos"

            custom_max_tokens = 1000
            custom_temperature = 0.9

            pipeline = self.factory.create_data_pipeline(
                data_dir=data_path,
                repos_dir=repos_dir,
                max_tokens=custom_max_tokens,
                temperature=custom_temperature
            )

            # Restore original setting
            self.config.USE_MLX = original_use_mlx

            # Verify the pipeline was created with custom parameters
            assert pipeline.max_tokens == custom_max_tokens
            assert pipeline.temperature == custom_temperature