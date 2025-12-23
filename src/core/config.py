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

    # Internal computed properties still needed for application functionality
    @property
    def backend(self) -> str:
        """Return the current LLM backend name."""
        return "mlx" if self._model.use_mlx else "llama_cpp"

    @property
    def BASE_DIR(self) -> str:
        """Base directory for the application (needed for internal file operations)."""
        return str(self._base_dir)

    @property
    def REPOS_DIR_NAME(self) -> str:
        """Repository directory name (needed for internal operations)."""
        return self._model.pipeline.repos_dir_name

    @property
    def DATA_DIR(self) -> str:
        """Data directory (needed for internal operations)."""
        return self._model.pipeline.data_dir

    @property
    def DB_PATH(self) -> str:
        """Database path (needed for internal operations)."""
        return str(self._db_path)

    @property
    def REPOS_DIR(self) -> str:
        """Repository directory path (needed for internal operations)."""
        return str(self._repos_dir)

    @property
    def LLM_BASE_URL(self) -> str:
        """LLM base URL (needed for internal operations)."""
        return self._model.llm.base_url

    @property
    def LLM_MODEL_NAME(self) -> str:
        """LLM model name (needed for internal operations)."""
        return self._model.llm.model_name

    @property
    def LLM_MAX_RETRIES(self) -> int:
        """LLM max retries (needed for internal operations)."""
        return self._model.llm.max_retries

    @property
    def LLM_RETRY_DELAY(self) -> float:
        """LLM retry delay (needed for internal operations)."""
        return self._model.llm.retry_delay

    @property
    def LLM_REQUEST_TIMEOUT(self) -> int:
        """LLM request timeout (needed for internal operations)."""
        return self._model.llm.request_timeout

    @property
    def LLM_MODEL_CACHE_TTL(self) -> int:
        """LLM model cache TTL (needed for internal operations)."""
        return self._model.llm.cache_ttl

    @property
    def DEFAULT_MAX_TOKENS(self) -> int:
        """Default max tokens (needed for internal operations)."""
        return self._model.generation.default_max_tokens

    @property
    def DEFAULT_TEMPERATURE(self) -> float:
        """Default temperature (needed for internal operations)."""
        return self._model.generation.default_temperature

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Max file size (needed for internal operations)."""
        return self._model.pipeline.max_file_size

    @property
    def CHUNK_READ_SIZE(self) -> int:
        """Chunk read size (needed for internal operations)."""
        return self._model.processing.chunk_read_size

    @property
    def USE_MLX(self) -> bool:
        """Use MLX flag (needed for internal operations)."""
        return self._model.use_mlx

    @property
    def MLX_MODEL_NAME(self) -> str:
        """MLX model name (needed for internal operations)."""
        return self._model.mlx.model_name

    @property
    def PROMPT_THEME(self) -> str:
        """Prompt theme (needed for internal operations)."""
        return self._model.pipeline.prompt_theme

    @property
    def MAX_LOG_FILES(self) -> int:
        """Max log files (needed for internal operations)."""
        return self._model.logging.max_log_files

    @property
    def LOG_FILE_PREFIX(self) -> str:
        """Log file prefix (needed for internal operations)."""
        return self._model.logging.log_file_prefix

    @property
    def MIN_QUESTION_TOKENS(self) -> int:
        """Min question tokens (needed for internal operations)."""
        return self._model.generation.min_question_tokens

    @property
    def MAX_QUESTION_TOKENS(self) -> int:
        """Max question tokens (needed for internal operations)."""
        return self._model.generation.max_question_tokens

    @property
    def MIN_ANSWER_CONTEXT_TOKENS(self) -> int:
        """Min answer context tokens (needed for internal operations)."""
        return self._model.generation.min_answer_context_tokens

    @property
    def MAX_ANSWER_CONTEXT_TOKENS(self) -> int:
        """Max answer context tokens (needed for internal operations)."""
        return self._model.generation.max_answer_context_tokens

    @property
    def BATTERY_LOW_THRESHOLD(self) -> int:
        """Battery low threshold (needed for internal operations)."""
        return self._model.battery.low_threshold

    @property
    def BATTERY_HIGH_THRESHOLD(self) -> int:
        """Battery high threshold (needed for internal operations)."""
        return self._model.battery.high_threshold

    @property
    def BATTERY_CHECK_INTERVAL(self) -> int:
        """Battery check interval (needed for internal operations)."""
        return self._model.battery.check_interval

    @property
    def ALLOWED_EXTENSIONS(self) -> tuple:
        """Allowed extensions (needed for internal operations)."""
        return self._model.pipeline.allowed_extensions

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