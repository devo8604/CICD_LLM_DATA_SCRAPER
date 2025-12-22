"""Unit tests for configuration loader."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.core.config_loader import ConfigLoader


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Sample configuration dictionary."""
    return {
        "llm": {
            "backend": "llama_cpp",
            "base_url": "http://localhost:8080",
            "model_name": "test-model",
            "max_retries": 5,
        },
        "pipeline": {
            "base_dir": "/test/path",
            "data_dir": "test_data",
            "max_file_size": 1000000,
        },
        "generation": {
            "default_max_tokens": 1000,
            "default_temperature": 0.5,
        },
    }


class TestConfigLoader:
    """Test ConfigLoader class."""

    def test_init(self):
        """Test initialization."""
        loader = ConfigLoader()
        assert loader.config_data == {}
        assert len(loader.config_paths) > 0

    def test_get_config_paths(self):
        """Test config path detection."""
        loader = ConfigLoader()
        paths = loader._get_config_paths()

        # Should include current directory paths
        assert any(".cicdllm.yaml" in str(p) for p in paths)
        assert any("cicdllm.yaml" in str(p) for p in paths)

        # Should include home directory paths
        assert any(str(Path.home()) in str(p) for p in paths)

    def test_get_config_paths_with_env(self, temp_config_dir):
        """Test config path with environment variable."""
        env_config_path = temp_config_dir / "custom_config.yaml"

        with patch.dict(os.environ, {"CICDLLM_CONFIG": str(env_config_path)}):
            loader = ConfigLoader()
            paths = loader._get_config_paths()

            # Environment variable path should be first
            assert paths[0] == env_config_path

    def test_load_no_config_file(self):
        """Test loading when no config file exists."""
        loader = ConfigLoader()
        # Override paths to non-existent files
        loader.config_paths = [Path("/nonexistent/config.yaml")]

        config = loader.load()
        assert config == {}

    def test_load_valid_config(self, temp_config_dir, sample_config):
        """Test loading a valid config file."""
        config_file = temp_config_dir / ".cicdllm.yaml"
        with open(config_file, "w") as f:
            yaml.safe_dump(sample_config, f)

        loader = ConfigLoader()
        loader.config_paths = [config_file]
        config = loader.load()

        assert config == sample_config
        assert config["llm"]["backend"] == "llama_cpp"
        assert config["pipeline"]["data_dir"] == "test_data"

    def test_load_invalid_yaml(self, temp_config_dir):
        """Test loading invalid YAML."""
        config_file = temp_config_dir / ".cicdllm.yaml"
        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [")

        loader = ConfigLoader()
        loader.config_paths = [config_file]
        config = loader.load()

        # Should return empty dict on error
        assert config == {}

    def test_get_simple_key(self, sample_config):
        """Test getting a simple config value."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        assert loader.get("llm.backend") == "llama_cpp"
        assert loader.get("pipeline.data_dir") == "test_data"
        assert loader.get("generation.default_temperature") == 0.5

    def test_get_nested_key(self):
        """Test getting nested config values."""
        loader = ConfigLoader()
        loader.config_data = {"level1": {"level2": {"level3": "value"}}}

        assert loader.get("level1.level2.level3") == "value"

    def test_get_missing_key_default(self, sample_config):
        """Test getting missing key returns default."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        assert loader.get("nonexistent.key") is None
        assert loader.get("nonexistent.key", "default") == "default"
        assert loader.get("llm.missing", 123) == 123

    def test_get_section(self, sample_config):
        """Test getting an entire section."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        llm_section = loader.get_section("llm")
        assert llm_section["backend"] == "llama_cpp"
        assert llm_section["max_retries"] == 5

        missing_section = loader.get_section("nonexistent")
        assert missing_section == {}

    def test_set_simple_key(self):
        """Test setting a simple config value."""
        loader = ConfigLoader()
        loader.set("llm.backend", "mlx")

        assert loader.config_data["llm"]["backend"] == "mlx"

    def test_set_nested_key(self):
        """Test setting nested config values."""
        loader = ConfigLoader()
        loader.set("level1.level2.level3", "value")

        assert loader.config_data["level1"]["level2"]["level3"] == "value"

    def test_set_overwrites_existing(self, sample_config):
        """Test setting overwrites existing values."""
        loader = ConfigLoader()
        loader.config_data = sample_config.copy()

        loader.set("llm.backend", "new_backend")
        assert loader.config_data["llm"]["backend"] == "new_backend"

    def test_save(self, temp_config_dir, sample_config):
        """Test saving configuration."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        save_path = temp_config_dir / "saved_config.yaml"
        loader.save(save_path)

        # Verify file was created and contains correct data
        assert save_path.exists()

        with open(save_path) as f:
            loaded = yaml.safe_load(f)

        assert loaded == sample_config

    def test_save_creates_parent_dir(self, temp_config_dir, sample_config):
        """Test saving creates parent directories."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        save_path = temp_config_dir / "nested" / "dir" / "config.yaml"
        loader.save(save_path)

        assert save_path.exists()
        assert save_path.parent.exists()

    def test_save_default_path(self, temp_config_dir, sample_config):
        """Test saving with default path."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        # Create a config file in temp dir
        config_file = temp_config_dir / ".cicdllm.yaml"
        config_file.touch()

        loader.config_paths = [config_file]
        loader.save()  # Should save to first existing path

        assert config_file.exists()
        with open(config_file) as f:
            loaded = yaml.safe_load(f)
        assert loaded == sample_config

    def test_validate_valid_config(self, sample_config):
        """Test validating a valid configuration."""
        loader = ConfigLoader()
        loader.config_data = sample_config

        is_valid, errors = loader.validate()
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_backend(self):
        """Test validation with invalid backend."""
        loader = ConfigLoader()
        loader.config_data = {"llm": {"backend": "invalid_backend"}}

        is_valid, errors = loader.validate()
        assert not is_valid
        assert len(errors) > 0
        assert "backend" in errors[0].lower()

    def test_validate_missing_llama_cpp_url(self):
        """Test validation with missing llama.cpp URL."""
        loader = ConfigLoader()
        loader.config_data = {
            "llm": {
                "backend": "llama_cpp"
                # Missing base_url
            }
        }

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("base_url" in err for err in errors)

    def test_validate_missing_mlx_model(self):
        """Test validation with missing MLX model name."""
        loader = ConfigLoader()
        loader.config_data = {
            "llm": {
                "backend": "mlx"
                # Missing mlx_model_name
            }
        }

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("mlx_model_name" in err for err in errors)

    def test_validate_invalid_file_size(self):
        """Test validation with invalid file size."""
        loader = ConfigLoader()
        loader.config_data = {"pipeline": {"max_file_size": -1000}}

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("max_file_size" in err for err in errors)

    def test_validate_invalid_temperature(self):
        """Test validation with invalid temperature."""
        loader = ConfigLoader()
        loader.config_data = {"generation": {"default_temperature": 3.0}}  # Too high

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("temperature" in err for err in errors)

    def test_validate_invalid_battery_thresholds(self):
        """Test validation with invalid battery thresholds."""
        loader = ConfigLoader()
        loader.config_data = {
            "battery": {
                "low_threshold": 90,
                "high_threshold": 50,  # High < Low (invalid)
            }
        }

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("threshold" in err.lower() for err in errors)

    def test_validate_battery_out_of_range(self):
        """Test validation with battery threshold out of range."""
        loader = ConfigLoader()
        loader.config_data = {"battery": {"low_threshold": 150}}  # > 100

        is_valid, errors = loader.validate()
        assert not is_valid
        assert any("threshold" in err.lower() for err in errors)

    def test_validate_multiple_errors(self):
        """Test validation with multiple errors."""
        loader = ConfigLoader()
        loader.config_data = {
            "llm": {"backend": "invalid"},
            "pipeline": {"max_file_size": -100},
            "generation": {"default_temperature": -1.0},
        }

        is_valid, errors = loader.validate()
        assert not is_valid
        assert len(errors) >= 3
