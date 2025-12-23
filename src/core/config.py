"""Application configuration with Pydantic validation."""

import platform
from pathlib import Path
from typing import Any

import psutil

from src.core.config_loader import ConfigLoader
from src.core.config_models import (
    AppConfigModel,
    BatteryConfig,
    GenerationConfig,
    LLMConfig,
    LoggingConfig,
    MLXConfig,
    PerformanceConfig,
    PipelineConfig,
    ProcessingConfig,
)


class AppConfig:
    """
    Application configuration facade providing access to configuration settings
    via the Pydantic-based AppConfigModel.

    Use config.model.<section>.<attribute> to access configuration values
    (e.g., config.model.llm.base_url) for type-safe, validated configuration access.
    """

    def __init__(self, config_file: str | None = None):
        """
        Initialize application configuration.

        Args:
            config_file: Optional path to YAML config file. If None, auto-detects.
        """
        # Load YAML configuration
        self.config_loader = ConfigLoader()
        if config_file:
            # Override config paths if specific file provided
            self.config_loader.config_paths = [Path(config_file)]

        yaml_config = self.config_loader.load()

        # Detect if running on Apple Silicon
        is_apple_silicon = self._is_apple_silicon()

        # Calculate default MLX memory if on Apple Silicon
        if is_apple_silicon and "mlx" in yaml_config:
            mlx_config = yaml_config["mlx"]
            if "max_ram_gb" not in mlx_config:
                # Calculate 80% of total system memory as default
                total_memory_gb = psutil.virtual_memory().total / (1024**3)
                mlx_config["max_ram_gb"] = int(total_memory_gb * 0.8)
                yaml_config["mlx"] = mlx_config

        # Determine backend from YAML or default
        llm_config = yaml_config.get("llm", {})
        backend = llm_config.get("backend", "llama_cpp" if not is_apple_silicon else "mlx")

        # Update YAML config with backend decision
        if "llm" not in yaml_config:
            yaml_config["llm"] = {}
        yaml_config["llm"]["backend"] = backend

        # Load and validate configuration using Pydantic model
        self._model = self._load_config_model(yaml_config)

        # Set USE_MLX based on backend
        self._model.use_mlx = backend == "mlx"

        # Computed properties
        self._base_dir = Path(self._model.pipeline.base_dir)
        self._data_dir = self._base_dir / self._model.pipeline.data_dir
        self._repos_dir = self._data_dir / self._model.pipeline.repos_dir_name
        self._db_path = self._data_dir / "pipeline.db"

    def _is_apple_silicon(self) -> bool:
        """Detect if running on Apple Silicon."""
        machine = platform.machine()
        system = platform.system()
        return system == "Darwin" and ("arm" in machine or "ARM" in machine or "aarch64" in machine)

    def _load_config_model(self, yaml_config: dict[str, Any]) -> AppConfigModel:
        """Load and validate configuration from YAML."""
        # Prepare config data with YAML overrides
        config_dict = {}

        # Map YAML sections to config structure
        if "llm" in yaml_config:
            config_dict["llm"] = {**LLMConfig().model_dump(), **yaml_config["llm"]}
        if "pipeline" in yaml_config:
            config_dict["pipeline"] = {**PipelineConfig().model_dump(), **yaml_config["pipeline"]}
        if "processing" in yaml_config:
            config_dict["processing"] = {
                **ProcessingConfig().model_dump(),
                **yaml_config["processing"],
            }
        if "performance" in yaml_config:
            config_dict["performance"] = {
                **PerformanceConfig().model_dump(),
                **yaml_config["performance"],
            }
        if "generation" in yaml_config:
            config_dict["generation"] = {**GenerationConfig().model_dump(), **yaml_config["generation"]}
        if "battery" in yaml_config:
            config_dict["battery"] = {**BatteryConfig().model_dump(), **yaml_config["battery"]}
        if "logging" in yaml_config:
            config_dict["logging"] = {**LoggingConfig().model_dump(), **yaml_config["logging"]}
        if "mlx" in yaml_config:
            config_dict["mlx"] = {**MLXConfig().model_dump(), **yaml_config["mlx"]}

        # Detect backend
        use_mlx = AppConfigModel.detect_backend()
        if "llm" in yaml_config and "backend" in yaml_config["llm"]:
            use_mlx = yaml_config["llm"]["backend"] == "mlx"

        # Create validated config
        return AppConfigModel(**config_dict, use_mlx=use_mlx)

    # Access to underlying Pydantic model (for new code)
    @property
    def model(self) -> AppConfigModel:
        """Access to the underlying Pydantic model for new code."""
        return self._model

    def get_section_config(self, section: str) -> dict[str, Any]:
        """
        Get configuration for a specific section.

        Args:
            section: Section name (llm, pipeline, processing, etc.)

        Returns:
            Dictionary of configuration values for the section

        Raises:
            ValueError: If section is unknown
        """
        section_map = {
            "llm": self._model.llm,
            "pipeline": self._model.pipeline,
            "processing": self._model.processing,
            "performance": self._model.performance,
            "battery": self._model.battery,
            "logging": self._model.logging,
            "mlx": self._model.mlx,
            "templates": self._model.templates,
        }

        if section not in section_map:
            raise ValueError(f"Unknown section: {section}")

        # Return as dict with prefixed keys
        section_obj = section_map[section]
        section_dict = section_obj.model_dump()

        # Add section prefix to keys
        if section == "llm":
            return {f"llm_{k}": v for k, v in section_dict.items()}
        else:
            return section_dict
