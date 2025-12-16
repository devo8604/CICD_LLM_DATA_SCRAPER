# src/config.py
import os


class AppConfig:
    # --- LLM Client Settings ---
    LLM_BASE_URL: str = "http://localhost:11454"
    LLM_MODEL_NAME: str = (
        "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    )
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: int = 5  # seconds
    LLM_MODEL_CACHE_TTL: int = 300  # 5 minutes

    # --- Data Pipeline Settings ---
    BASE_DIR: str = "."
    DATA_DIR: str = "data"
    REPOS_DIR_NAME: str = (
        "repos"  # Name of the subdirectory within BASE_DIR for repositories
    )
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # Default to 5MB

    # --- Logging Settings ---
    MAX_LOG_FILES: int = 5
    LOG_FILE_PREFIX: str = "pipeline_log"

    # --- LLM Generation Parameters (can be overridden by CLI args) ---
    DEFAULT_MAX_TOKENS: int = 500
    DEFAULT_TEMPERATURE: float = 0.7

    # --- Battery Management Settings ---
    BATTERY_LOW_THRESHOLD: int = 15  # Pause processing below this %
    BATTERY_HIGH_THRESHOLD: int = 90  # Resume processing above this %
    BATTERY_CHECK_INTERVAL: int = 60  # Check every 60 seconds when paused

    # --- File Filtering Settings ---
    EXCLUDED_FILE_EXTENSIONS: tuple = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bin",
        ".zip",
        ".tar",
        ".gz",
        ".svg",
        ".idx",
        ".rev",
        ".pack",
        ".DS_Store",
        ".pdf",
    )

    # --- Chat Templates ---
    QWEN_TEMPLATE: str = (
        "<|im_start|>user\n"
        "{instruction}"
        "<|im_end|>"
        "<|im_start|>assistant\n"
        "{output}"
        "<|im_end|>"
    )

    LLAMA3_CHAT_TEMPLATE: str = (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        "{system_content}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        "{user_content}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        "{assistant_content}<|eot_id|>"
    )

    MISTRAL_CHAT_TEMPLATE: str = (
        "<s>[INST] {system_and_user_content} [/INST]{assistant_content}</s>"
    )

    GEMMA_CHAT_TEMPLATE: str = (
        "<start_of_turn>user\n{user_content}<end_of_turn>"
        "<start_of_turn>model\n{assistant_content}<end_of_turn>"
    )

    # --- State Management Settings ---
    STATE_SAVE_INTERVAL: int = 10  # Save state every N Q&A pairs

    # --- Parallel Processing Settings ---
    MAX_CONCURRENT_FILES: int = 1  # Number of files to process in parallel
    FILE_BATCH_SIZE: int = 10  # Process files in batches of this size

    @property
    def REPOS_DIR(self) -> str:
        return os.path.join(self.BASE_DIR, self.REPOS_DIR_NAME)

    @property
    def DB_PATH(self) -> str:
        return "pipeline.db"
