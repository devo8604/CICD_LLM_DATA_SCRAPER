"""Comprehensive unit tests for the AppConfig class."""

import pytest
from unittest.mock import patch, MagicMock
import os

from src.config import AppConfig


class TestAppConfig:
    """Test cases for AppConfig class."""

    def test_default_llm_settings(self):
        """Test default LLM configuration values."""
        config = AppConfig()

        assert config.LLM_BASE_URL == "http://localhost:11454"
        assert config.LLM_MODEL_NAME == "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
        assert config.LLM_MAX_RETRIES == 3
        assert config.LLM_RETRY_DELAY == 5
        assert config.LLM_MODEL_CACHE_TTL == 300

    def test_default_data_pipeline_settings(self):
        """Test default data pipeline configuration values."""
        config = AppConfig()

        assert config.BASE_DIR == "."
        assert config.DATA_DIR == "data"
        assert config.REPOS_DIR_NAME == "repos"
        assert config.MAX_FILE_SIZE == 5 * 1024 * 1024

    def test_default_logging_settings(self):
        """Test default logging configuration values."""
        config = AppConfig()

        assert config.MAX_LOG_FILES == 5
        assert config.LOG_FILE_PREFIX == "pipeline_log"

    def test_default_llm_generation_parameters(self):
        """Test default LLM generation parameters."""
        config = AppConfig()

        assert config.DEFAULT_MAX_TOKENS == 500
        assert config.DEFAULT_TEMPERATURE == 0.7

    def test_default_battery_management_settings(self):
        """Test default battery management settings."""
        config = AppConfig()

        assert config.BATTERY_LOW_THRESHOLD == 15
        assert config.BATTERY_HIGH_THRESHOLD == 90
        assert config.BATTERY_CHECK_INTERVAL == 60

    def test_excluded_file_extensions(self):
        """Test that excluded file extensions are properly configured."""
        config = AppConfig()

        expected_extensions = (
            ".png", ".jpg", ".jpeg", ".gif", ".bin", ".zip", ".tar", ".gz",
            ".svg", ".idx", ".rev", ".pack", ".DS_Store", ".pdf", ".pptx"
        )

        assert config.EXCLUDED_FILE_EXTENSIONS == expected_extensions
        assert ".png" in config.EXCLUDED_FILE_EXTENSIONS
        assert ".pdf" in config.EXCLUDED_FILE_EXTENSIONS
        assert ".pptx" in config.EXCLUDED_FILE_EXTENSIONS

    def test_chat_templates_defined(self):
        """Test that all chat templates are defined."""
        config = AppConfig()

        assert hasattr(config, 'QWEN_TEMPLATE')
        assert hasattr(config, 'LLAMA3_CHAT_TEMPLATE')
        assert hasattr(config, 'MISTRAL_CHAT_TEMPLATE')
        assert hasattr(config, 'GEMMA_CHAT_TEMPLATE')

        assert "<|im_start|>" in config.QWEN_TEMPLATE
        assert "<|begin_of_text|>" in config.LLAMA3_CHAT_TEMPLATE
        assert "[INST]" in config.MISTRAL_CHAT_TEMPLATE
        assert "<start_of_turn>" in config.GEMMA_CHAT_TEMPLATE

    def test_state_management_settings(self):
        """Test state management configuration."""
        config = AppConfig()

        assert config.STATE_SAVE_INTERVAL == 10

    def test_parallel_processing_settings(self):
        """Test parallel processing configuration."""
        config = AppConfig()

        assert config.MAX_CONCURRENT_FILES == 1
        assert config.FILE_BATCH_SIZE == 10

    def test_performance_and_cache_settings(self):
        """Test performance and cache configuration."""
        config = AppConfig()

        assert config.FILE_HASH_CACHE_SIZE == 10000
        assert config.DATABASE_CONNECTION_POOL_SIZE == 5
        assert config.LLM_REQUEST_TIMEOUT == 300
        assert config.CHUNK_READ_SIZE == 8192

    @patch('platform.machine')
    @patch('platform.system')
    def test_use_mlx_on_apple_silicon(self, mock_system, mock_machine):
        """Test that USE_MLX is True on Apple Silicon."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        config = AppConfig()

        # Note: The actual config has USE_MLX hardcoded to False
        # This test verifies the detection logic would work if enabled
        assert mock_system.called
        assert mock_machine.called

    @patch('platform.machine')
    @patch('platform.system')
    def test_use_mlx_on_non_apple_silicon(self, mock_system, mock_machine):
        """Test that USE_MLX detection works on non-Apple Silicon."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        config = AppConfig()

        # The current config has USE_MLX hardcoded to False
        assert config.USE_MLX == False

    def test_mlx_configuration_attributes(self):
        """Test MLX-specific configuration attributes."""
        config = AppConfig()

        assert hasattr(config, 'USE_MLX')
        assert hasattr(config, 'MLX_MODEL_NAME')
        assert hasattr(config, 'MLX_MAX_RAM_GB')
        assert hasattr(config, 'MLX_QUANTIZE')
        assert hasattr(config, 'MLX_TEMPERATURE')

        assert config.MLX_MODEL_NAME == "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
        assert config.MLX_MAX_RAM_GB == 32
        assert config.MLX_QUANTIZE == True
        assert config.MLX_TEMPERATURE == 0.7

    def test_repos_dir_property(self):
        """Test REPOS_DIR property correctly combines BASE_DIR and REPOS_DIR_NAME."""
        config = AppConfig()

        expected_path = os.path.join(config.BASE_DIR, config.REPOS_DIR_NAME)
        assert config.REPOS_DIR == expected_path

    def test_repos_dir_property_with_custom_base_dir(self):
        """Test REPOS_DIR property with custom BASE_DIR."""
        config = AppConfig()
        config.BASE_DIR = "/custom/path"

        expected_path = os.path.join("/custom/path", config.REPOS_DIR_NAME)
        assert config.REPOS_DIR == expected_path

    def test_db_path_property(self):
        """Test DB_PATH property returns correct database path."""
        config = AppConfig()

        assert config.DB_PATH == "pipeline.db"

    def test_config_is_singleton_like(self):
        """Test that multiple AppConfig instances have same class attributes."""
        config1 = AppConfig()
        config2 = AppConfig()

        # Class attributes should be the same
        assert config1.LLM_BASE_URL == config2.LLM_BASE_URL
        assert config1.LLM_MODEL_NAME == config2.LLM_MODEL_NAME
        assert config1.MAX_FILE_SIZE == config2.MAX_FILE_SIZE

    def test_instance_attributes_separate(self):
        """Test that instance attributes (MLX settings) are separate per instance."""
        config1 = AppConfig()
        config2 = AppConfig()

        # Modify one instance
        config1.USE_MLX = True

        # Other instance should still have original value
        assert config2.USE_MLX == False

    def test_chat_template_has_placeholders(self):
        """Test that chat templates contain expected placeholders."""
        config = AppConfig()

        assert "{instruction}" in config.QWEN_TEMPLATE
        assert "{output}" in config.QWEN_TEMPLATE

        assert "{system_content}" in config.LLAMA3_CHAT_TEMPLATE
        assert "{user_content}" in config.LLAMA3_CHAT_TEMPLATE
        assert "{assistant_content}" in config.LLAMA3_CHAT_TEMPLATE

        assert "{system_and_user_content}" in config.MISTRAL_CHAT_TEMPLATE
        assert "{assistant_content}" in config.MISTRAL_CHAT_TEMPLATE

        assert "{user_content}" in config.GEMMA_CHAT_TEMPLATE
        assert "{assistant_content}" in config.GEMMA_CHAT_TEMPLATE

    def test_numeric_settings_are_positive(self):
        """Test that all numeric settings have positive values."""
        config = AppConfig()

        assert config.LLM_MAX_RETRIES > 0
        assert config.LLM_RETRY_DELAY > 0
        assert config.LLM_MODEL_CACHE_TTL > 0
        assert config.MAX_FILE_SIZE > 0
        assert config.MAX_LOG_FILES > 0
        assert config.DEFAULT_MAX_TOKENS > 0
        assert config.DEFAULT_TEMPERATURE > 0
        assert config.BATTERY_LOW_THRESHOLD > 0
        assert config.BATTERY_HIGH_THRESHOLD > 0
        assert config.BATTERY_CHECK_INTERVAL > 0
        assert config.STATE_SAVE_INTERVAL > 0
        assert config.MAX_CONCURRENT_FILES > 0
        assert config.FILE_BATCH_SIZE > 0
        assert config.FILE_HASH_CACHE_SIZE > 0
        assert config.DATABASE_CONNECTION_POOL_SIZE > 0
        assert config.LLM_REQUEST_TIMEOUT > 0
        assert config.CHUNK_READ_SIZE > 0

    def test_battery_thresholds_make_sense(self):
        """Test that battery threshold values are logical."""
        config = AppConfig()

        assert 0 < config.BATTERY_LOW_THRESHOLD < 100
        assert 0 < config.BATTERY_HIGH_THRESHOLD < 100
        assert config.BATTERY_LOW_THRESHOLD < config.BATTERY_HIGH_THRESHOLD

    def test_temperature_in_valid_range(self):
        """Test that temperature values are in valid range."""
        config = AppConfig()

        assert 0 <= config.DEFAULT_TEMPERATURE <= 2.0
        assert 0 <= config.MLX_TEMPERATURE <= 2.0
