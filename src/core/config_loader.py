"""Configuration loader for YAML-based configuration files."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Load and merge configuration from YAML files."""

    def __init__(self):
        """Initialize the config loader."""
        self.config_paths = self._get_config_paths()
        self.config_data: dict[str, Any] = {}

    def _get_config_paths(self) -> list[Path]:
        """
        Get list of potential configuration file paths in priority order.

        Returns:
            List of Path objects to check for config files
        """
        paths = []

        # 1. Environment variable (highest priority)
        env_config = os.getenv("CICDLLM_CONFIG")
        if env_config:
            paths.append(Path(env_config))

        # 2. Current directory
        paths.append(Path.cwd() / ".cicdllm.yaml")
        paths.append(Path.cwd() / "cicdllm.yaml")

        # 3. User's home directory config
        home = Path.home()
        paths.append(home / ".config" / "cicdllm" / "config.yaml")
        paths.append(home / ".cicdllm.yaml")

        return paths

    def load(self) -> dict[str, Any]:
        """
        Load configuration from YAML files.

        Checks paths in priority order and uses the first valid file found.

        Returns:
            Dictionary containing configuration data
        """
        for path in self.config_paths:
            if path.exists() and path.is_file():
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        self.config_data = yaml.safe_load(f) or {}
                    logging.info(f"Loaded configuration from: {path}")
                    return self.config_data
                except yaml.YAMLError as e:
                    logging.error(f"Error parsing YAML config at {path}: {e}")
                except Exception as e:
                    logging.error(f"Error reading config file {path}: {e}")

        # No config file found - return empty dict (will use defaults)
        logging.debug("No configuration file found, using defaults")
        return {}

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., 'llm.base_url')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self.config_data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: Section name (e.g., 'llm', 'pipeline')

        Returns:
            Dictionary containing section data, or empty dict if not found
        """
        return self.config_data.get(section, {})

    def set(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value
            value: Value to set
        """
        keys = key_path.split(".")
        target = self.config_data

        # Navigate/create nested structure
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        # Set the final value
        target[keys[-1]] = value

    def save(self, path: Path | None = None) -> None:
        """
        Save current configuration to a YAML file.

        Args:
            path: Path to save to. If None, uses first config path that exists,
                  or creates .cicdllm.yaml in current directory.
        """
        if path is None:
            # Use first existing config path, or default to current directory
            for config_path in self.config_paths:
                if config_path.exists():
                    path = config_path
                    break
            else:
                path = Path.cwd() / ".cicdllm.yaml"

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w") as f:
                yaml.safe_dump(
                    self.config_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                )
            logging.info(f"Configuration saved to: {path}")
        except Exception as e:
            logging.error(f"Error saving configuration to {path}: {e}")
            raise

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the current configuration.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Validate LLM settings
        llm_config = self.get_section("llm")
        if llm_config:
            backend = llm_config.get("backend", "llama_cpp")
            if backend not in ["llama_cpp", "mlx"]:
                errors.append(f"Invalid LLM backend '{backend}'. Must be 'llama_cpp' or 'mlx'")

            if backend == "llama_cpp":
                if not llm_config.get("base_url"):
                    errors.append("llm.base_url is required for llama_cpp backend")
                if not llm_config.get("model_name"):
                    errors.append("llm.model_name is required for llama_cpp backend")

            if backend == "mlx":
                if not llm_config.get("mlx_model_name"):
                    errors.append("llm.mlx_model_name is required for MLX backend")

        # Validate pipeline settings
        pipeline_config = self.get_section("pipeline")
        if pipeline_config:
            max_file_size = pipeline_config.get("max_file_size")
            if max_file_size is not None and max_file_size <= 0:
                errors.append("pipeline.max_file_size must be positive")

        # Validate generation settings
        gen_config = self.get_section("generation")
        if gen_config:
            temp = gen_config.get("default_temperature")
            if temp is not None and (temp < 0 or temp > 2.0):
                errors.append("generation.default_temperature must be between 0 and 2.0")

            max_tokens = gen_config.get("default_max_tokens")
            if max_tokens is not None and max_tokens <= 0:
                errors.append("generation.default_max_tokens must be positive")

        # Validate battery settings
        battery_config = self.get_section("battery")
        if battery_config:
            low = battery_config.get("low_threshold")
            high = battery_config.get("high_threshold")
            if low is not None and (low < 0 or low > 100):
                errors.append("battery.low_threshold must be between 0 and 100")
            if high is not None and (high < 0 or high > 100):
                errors.append("battery.high_threshold must be between 0 and 100")
            if low is not None and high is not None and low >= high:
                errors.append("battery.low_threshold must be less than battery.high_threshold")

        return (len(errors) == 0, errors)
