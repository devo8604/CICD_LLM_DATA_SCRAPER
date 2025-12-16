"""Factory for creating pipeline components."""

from pathlib import Path

from src.config import AppConfig
from src.cli import parse_arguments
from src.data_pipeline import DataPipeline
from src.llm_client import LLMClient
from src.mlx_client import MLXClient
from src.db_manager import DBManager
from src.file_manager import FileManager


class PipelineFactory:
    """Factory class for creating pipeline components with proper dependency injection."""

    def __init__(self, config: AppConfig):
        self.config = config

    def create_llm_client(self):
        """Create appropriate LLM client based on configuration."""
        if self.config.USE_MLX:
            # Import MLX client and create instance
            return MLXClient(
                model_name=self.config.MLX_MODEL_NAME,
                max_retries=self.config.LLM_MAX_RETRIES,
                retry_delay=self.config.LLM_RETRY_DELAY,
                config=self.config,
            )
        else:
            # Use the standard LLM client
            return LLMClient(
                base_url=self.config.LLM_BASE_URL,
                model_name=self.config.LLM_MODEL_NAME,
                max_retries=self.config.LLM_MAX_RETRIES,
                retry_delay=self.config.LLM_RETRY_DELAY,
            )

    def create_db_manager(self, data_dir: Path) -> DBManager:
        """Create database manager with configured settings."""
        return DBManager(data_dir / self.config.DB_PATH)

    def create_file_manager(self, repos_dir: str) -> FileManager:
        """Create file manager with configured settings."""
        return FileManager(
            repos_dir=repos_dir,
            max_file_size=self.config.MAX_FILE_SIZE,
        )

    def create_data_pipeline(
        self,
        data_dir: Path,
        repos_dir: str,
        max_tokens: int = None,
        temperature: float = None,
        lazy_llm: bool = False,
    ) -> DataPipeline:
        """
        Create a complete data pipeline with all dependencies.

        Args:
            data_dir: Directory for data storage
            repos_dir: Directory for repositories
            max_tokens: Maximum tokens for LLM generation
            temperature: Temperature for LLM generation
            lazy_llm: If True, LLM client will be created lazily when first accessed

        Returns:
            DataPipeline instance
        """
        # Only create LLM client upfront if not using lazy initialization
        llm_client = None if lazy_llm else self.create_llm_client()
        db_manager = self.create_db_manager(data_dir)
        file_manager = self.create_file_manager(repos_dir)

        return DataPipeline(
            db_manager=db_manager,
            file_manager=file_manager,
            llm_client=llm_client,
            max_tokens=max_tokens or self.config.DEFAULT_MAX_TOKENS,
            temperature=temperature or self.config.DEFAULT_TEMPERATURE,
            config=self.config,
        )
