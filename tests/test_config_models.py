from unittest.mock import MagicMock, patch

import pytest

from src.core.config_models import (
    AppConfigModel,
    LLMConfig,
    PipelineConfig,
    ProcessingConfig,
    load_validated_config,
)


class TestConfigModels:
    def test_llm_config_defaults(self):
        config = LLMConfig()
        assert config.base_url == "http://localhost:11434"
        assert config.model_name == "ollama/llama3.2:1b"
        assert config.max_retries == 3
        assert config.retry_delay == 5.0
        assert config.cache_ttl == 300
        assert config.request_timeout == 300

    def test_llm_config_validation(self):
        with pytest.raises(ValueError, match="Base URL must start with http:// or https://"):
            LLMConfig(base_url="ftp://localhost")

        LLMConfig(base_url="https://api.openai.com")  # Should be valid

    def test_processing_config_validation(self):
        config = ProcessingConfig()
        assert config.max_concurrent_files == 1

        # Test range validation (pydantic usually validates on assignment or init)
        # Note: Pydantic v1 vs v2 might differ slightly on error types, but ValidationError is standard
        # However, we are just testing the model creation here.

        # Pydantic validation errors are raised as pydantic.ValidationError
        # We can just check that valid values work and invalid ones raise *something*
        # (usually ValidationError, but we can catch Exception to be safe or import ValidationError)
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessingConfig(max_concurrent_files=0)

        with pytest.raises(ValidationError):
            ProcessingConfig(max_concurrent_files=11)

    def test_pipeline_config_defaults(self):
        config = PipelineConfig()
        assert config.base_dir == "."
        assert ".py" in config.allowed_extensions  # Check for allowed extension instead of excluded

    def test_app_config_model_defaults(self):
        config = AppConfigModel()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.processing, ProcessingConfig)
        assert config.use_mlx is False

    @patch("platform.system")
    @patch("platform.machine")
    def test_detect_backend_macos_arm(self, mock_machine, mock_system):
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        assert AppConfigModel.detect_backend() is True

    @patch("platform.system")
    @patch("platform.machine")
    def test_detect_backend_other(self, mock_machine, mock_system):
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        assert AppConfigModel.detect_backend() is False

        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"
        assert AppConfigModel.detect_backend() is False

    def test_load_validated_config_from_dict(self):
        config_dict = {
            "llm": {"base_url": "http://test-url", "backend": "ollama"},
            "processing": {"max_concurrent_files": 5},
        }

        config = load_validated_config(config_dict)
        assert config.llm.base_url == "http://test-url"
        assert config.processing.max_concurrent_files == 5
        assert config.use_mlx is False

    @patch("src.core.config_loader.ConfigLoader")
    def test_load_validated_config_no_args(self, mock_loader_cls):
        mock_loader = MagicMock()
        mock_loader.load.return_value = {
            "llm": {"model_name": "test-model"},
            "mlx": {"model_name": "test-mlx-model"},
        }
        mock_loader_cls.return_value = mock_loader

        config = load_validated_config()
        assert config.llm.model_name == "test-model"
        assert config.mlx.model_name == "test-mlx-model"

    def test_load_validated_config_mlx_override(self):
        config_dict = {"llm": {"backend": "mlx"}}
        config = load_validated_config(config_dict)
        assert config.use_mlx is True
