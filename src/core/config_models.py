"""Enhanced configuration models with validation using Pydantic."""

import platform

from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    """Configuration for LLM clients."""

    base_url: str = Field(default="http://localhost:11434", description="Base URL for LLM API")
    model_name: str = Field(default="ollama/llama3.2:1b", description="Model name to use")
    max_retries: int = Field(default=3, ge=0, description="Maximum number of retries for LLM requests")
    retry_delay: float = Field(default=5.0, gt=0, description="Delay between retries in seconds")
    cache_ttl: int = Field(default=300, ge=0, description="Cache time-to-live in seconds")
    request_timeout: int = Field(default=300, gt=0, description="Request timeout in seconds")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v


class ProcessingConfig(BaseModel):
    """Configuration for processing operations."""

    max_concurrent_files: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Maximum number of files to process concurrently",
    )
    file_batch_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of files to process in each batch",
    )
    chunk_read_size: int = Field(
        default=8192,
        ge=1024,
        le=1024 * 1024,
        description="Size of chunks to read files in bytes",
    )
    default_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=100000,  # Effectively unlimited
        description="Default maximum tokens for LLM generation",
    )
    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature for LLM generation",
    )


class PipelineConfig(BaseModel):
    """Configuration for pipeline operations."""

    base_dir: str = Field(default=".", description="Base directory for the application")
    data_dir: str = Field(default="data", description="Directory for data storage")
    repos_dir_name: str = Field(default="repos", description="Name of directory for repositories")
    prompt_theme: str = Field(default="devops", description="Theme directory for prompts under prompts/")
    max_file_size: int = Field(
        default=5 * 1024 * 1024,  # 5MB
        ge=1024,  # At least 1KB
        le=100 * 1024 * 1024,  # Max 100MB
        description="Maximum file size in bytes",
    )
    allowed_extensions: tuple[str, ...] = Field(
        default=(
            # Infrastructure as Code (Terraform, CloudFormation, Ansible, K8s)
            ".tf",
            ".tfvars",
            ".hcl",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            # Scripts & Automation (Shell, PowerShell, Make, Groovy)
            ".sh",
            ".bash",
            ".zsh",
            ".ps1",
            ".bat",
            ".cmd",
            ".mk",
            ".groovy",
            # Config & Build (Docker, CI/CD, Env)
            ".conf",
            ".ini",
            ".env",
            "Dockerfile",
            "Containerfile",
            "Jenkinsfile",
            "Makefile",
            # Application Logic (Common DevOps Languages)
            ".py",
            ".go",
            ".rs",
            ".js",
            ".ts",
            ".rb",
            ".java",
            ".c",
            ".cpp",
        ),
        description="File extensions to allow for processing",
    )
    allowed_json_md_files: tuple[str, ...] = Field(
        default=(
            "readme.md",
            "readme.txt",
            "readme",
            "readme.json",
            "README.md",
            "README.txt",
            "README",
            "README.json",
        ),
        description="Special case files that are allowed even if they would normally be excluded (e.g., README files)",
    )
    state_save_interval: int = Field(default=10, ge=1, le=1000, description="Save state every N Q&A pairs")


class PerformanceConfig(BaseModel):
    """Configuration for performance tuning."""

    file_hash_cache_size: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Number of file hashes to cache in memory",
    )
    database_connection_pool_size: int = Field(default=5, ge=1, le=50, description="Size of database connection pool")


class BatteryConfig(BaseModel):
    """Configuration for battery management."""

    low_threshold: int = Field(
        default=15,
        ge=0,
        le=50,
        description="Pause processing below this battery percentage",
    )
    high_threshold: int = Field(
        default=90,
        ge=50,
        le=100,
        description="Resume processing above this battery percentage",
    )
    check_interval: int = Field(default=60, ge=1, le=3600, description="Check battery level every N seconds")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    max_log_files: int = Field(default=5, ge=1, le=100, description="Maximum number of log files to keep")
    log_file_prefix: str = Field(default="pipeline_log", description="Prefix for log file names")


class MLXConfig(BaseModel):
    """Configuration for MLX backend."""

    model_name: str = Field(
        default="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        description="MLX model name",
    )
    max_ram_gb: int = Field(default=32, ge=4, le=128, description="Maximum RAM to use for MLX in GB")
    quantize: bool = Field(default=True, description="Whether to use quantized models")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for MLX generation")


class TemplateConfig(BaseModel):
    """Configuration for chat templates."""

    qwen_template: str = Field(
        default="```user\n{instruction}\n```\n\n```assistant\n{output}\n```",
        description="Template for Qwen model",
    )
    llama3_template: str = Field(
        default="<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_content}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user_content}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{assistant_content}<|eot_id|>",
        description="Template for Llama3 model",
    )
    mistral_template: str = Field(
        default="<s>[INST] {system_and_user_content} [/INST]{assistant_content}</s>",
        description="Template for Mistral model",
    )
    gemma_template: str = Field(
        default="<start_of_turn>user\n{user_content}<end_of_turn><start_of_turn>model\n{assistant_content}<end_of_turn>",
        description="Template for Gemma model",
    )


class GenerationConfig(BaseModel):
    """Configuration for generation parameters."""

    default_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=100000,  # Effectively unlimited
        description="Default maximum tokens for LLM generation",
    )
    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature for generation",
    )
    min_question_tokens: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Minimum number of tokens for generated questions (target 100-300 chars)",
    )
    max_question_tokens: int = Field(
        default=75,
        ge=1,
        le=200,
        description="Maximum number of tokens for generated questions (target 100-300 chars)",
    )
    min_answer_context_tokens: int = Field(
        default=256,
        ge=100,
        le=2048,
        description="Minimum tokens for answer context (target 1025-4096 chars)",
    )
    max_answer_context_tokens: int = Field(
        default=1024,
        ge=256,
        le=4096,
        description="Maximum tokens for answer context (target 1025-4096 chars)",
    )


class AppConfigModel(BaseModel):
    """Complete application configuration model."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mlx: MLXConfig = Field(default_factory=MLXConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    templates: TemplateConfig = Field(default_factory=TemplateConfig)

    # Auto-detected settings
    use_mlx: bool = Field(default=False, description="Whether to use MLX backend")

    @classmethod
    def detect_backend(cls) -> bool:
        """Detect if we should use MLX backend based on hardware."""
        machine = platform.machine()
        system = platform.system()
        return system == "Darwin" and ("arm" in machine or "ARM" in machine or "aarch64" in machine)


def load_validated_config(yaml_config: dict = None) -> AppConfigModel:
    """Load and validate configuration from YAML."""
    if yaml_config is None:
        from src.core.config_loader import ConfigLoader

        loader = ConfigLoader()
        yaml_config = loader.load()

    # Prepare config data with possible YAML overrides
    config_dict = {}

    # Map YAML sections to our config structure
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
    if "battery" in yaml_config:
        config_dict["battery"] = {**BatteryConfig().model_dump(), **yaml_config["battery"]}
    if "logging" in yaml_config:
        config_dict["logging"] = {**LoggingConfig().model_dump(), **yaml_config["logging"]}
    if "mlx" in yaml_config:
        config_dict["mlx"] = {**MLXConfig().model_dump(), **yaml_config["mlx"]}

    # Detect backend automatically
    use_mlx = AppConfigModel.detect_backend()
    if "llm" in yaml_config and "backend" in yaml_config["llm"]:
        use_mlx = yaml_config["llm"]["backend"] == "mlx"

    # Create the validated config object
    app_config = AppConfigModel(**config_dict, use_mlx=use_mlx)
    return app_config
