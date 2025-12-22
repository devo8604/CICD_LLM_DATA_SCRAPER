"""Unit tests for the AppConfig module."""

from unittest.mock import patch

import pytest

from src.core.config import AppConfig


class TestAppConfig:
    """Test cases for AppConfig."""

    @pytest.fixture(autouse=True)
    def mock_config_loader(self):
        """Mock ConfigLoader to return empty config by default."""
        with patch("src.core.config.ConfigLoader") as mock_loader_cls:
            mock_loader = mock_loader_cls.return_value
            mock_loader.load.return_value = {}
            mock_loader.config_paths = []
            yield mock_loader

    def test_default_values(self):
        """Test that AppConfig has correct default values."""
        config = AppConfig()

        assert config.LLM_BASE_URL == "http://localhost:11434"
        assert config.LLM_MAX_RETRIES == 3
        assert config.BASE_DIR == "."
        assert config.DATA_DIR == "data"
        assert config.MAX_FILE_SIZE == 5 * 1024 * 1024

    def test_repos_dir_property(self, mock_config_loader):
        """Test the REPOS_DIR property."""
        # Mock config with custom values
        mock_config_loader.load.return_value = {
            "pipeline": {
                "base_dir": "/tmp/test",
                "repos_dir_name": "my_repos",
            }
        }

        config = AppConfig()

        assert config.BASE_DIR == "/tmp/test"
        assert config.REPOS_DIR_NAME == "my_repos"
        assert "/tmp/test" in config.REPOS_DIR
        assert "my_repos" in config.REPOS_DIR

    def test_db_path_property(self):
        """Test the DB_PATH property."""
        config = AppConfig()
        # DB_PATH now returns full path: data/pipeline.db
        assert "pipeline.db" in config.DB_PATH
        assert config.DB_PATH == "data/pipeline.db"

    def test_get_section_config(self):
        """Test getting configuration for a specific section."""
        config = AppConfig()

        llm_config = config.get_section_config("llm")
        assert "llm_base_url" in llm_config
        assert "llm_model_name" in llm_config
        assert llm_config["llm_base_url"] == "http://localhost:11434"

        pipeline_config = config.get_section_config("pipeline")
        assert "base_dir" in pipeline_config
        assert "data_dir" in pipeline_config

    def test_get_section_config_invalid(self):
        """Test getting config for an invalid section."""
        config = AppConfig()
        with pytest.raises(ValueError, match="Unknown section"):
            config.get_section_config("invalid_section")

    def test_yaml_overrides(self, mock_config_loader):
        """Test that YAML settings override defaults."""
        mock_config_loader.load.return_value = {
            "llm": {"base_url": "http://remote-server:8080", "max_retries": 10},
            "pipeline": {"base_dir": "/custom/path"},
        }

        config = AppConfig()

        assert config.LLM_BASE_URL == "http://remote-server:8080"
        assert config.LLM_MAX_RETRIES == 10
        assert config.BASE_DIR == "/custom/path"

    def test_allowed_extensions_tuple_conversion(self, mock_config_loader):
        """Test that allowed_extensions is converted to tuple from list in YAML."""
        mock_config_loader.load.return_value = {"filtering": {"allowed_extensions": [".py", ".js", ".ts"]}}

        config = AppConfig()

        assert isinstance(config.ALLOWED_EXTENSIONS, tuple)
        assert ".py" in config.ALLOWED_EXTENSIONS
        assert ".js" in config.ALLOWED_EXTENSIONS
        assert ".ts" in config.ALLOWED_EXTENSIONS

    @patch("platform.machine")
    @patch("platform.system")
    def test_backend_detection_apple_silicon(self, mock_system, mock_machine):
        """Test that MLX is detected on Apple Silicon."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        config = AppConfig()

        # Check if detected as Apple Silicon
        assert config._is_apple_silicon() is True

    @patch("platform.machine")
    @patch("platform.system")
    def test_use_mlx_on_non_apple_silicon(self, mock_system, mock_machine):
        """Test that USE_MLX detection works on non-Apple Silicon."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        config = AppConfig()

        # Should default to llama_cpp (USE_MLX = False)
        assert config.USE_MLX is False

    def test_mlx_configuration_attributes(self):
        """Test MLX-specific configuration attributes."""
        config = AppConfig()

        assert hasattr(config, "USE_MLX")
        assert hasattr(config, "MLX_MODEL_NAME")
        assert hasattr(config, "MLX_MAX_RAM_GB")
        assert hasattr(config, "MLX_QUANTIZE")
        assert hasattr(config, "MLX_TEMPERATURE")

        # The current default in src/config.py
        assert config.MLX_MODEL_NAME == "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"

    def test_mlx_ram_calculation(self, mock_config_loader):
        """Test automatic MLX RAM calculation (80% of total)."""
        # Provide MLX config without max_ram_gb to trigger calculation
        mock_config_loader.load.return_value = {
            "llm": {"backend": "mlx"},
            "mlx": {}  # Empty MLX config triggers auto-calculation
        }

        with patch("psutil.virtual_memory") as mock_vmem, \
             patch("platform.machine", return_value="arm64"), \
             patch("platform.system", return_value="Darwin"):
            # Mock 16GB total RAM
            mock_vmem.return_value.total = 16 * 1024 * 1024 * 1024

            config = AppConfig()

            # 80% of 16GB is 12.8GB, int is 12
            expected_limit = 12
            assert config.MLX_MAX_RAM_GB == expected_limit
            assert config.MLX_QUANTIZE is True
            assert config.MLX_TEMPERATURE == 0.7
