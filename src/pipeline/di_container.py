"""Dependency injection container for the application."""

import logging
from pathlib import Path
from typing import Any, Protocol, TypeVar

from src.core.config import AppConfig
from src.core.config_models import AppConfigModel, load_validated_config
from src.data.db_manager import DBManager
from src.data.file_manager import FileManager
from src.llm.llm_client import LLMClient
from src.llm.mlx_client import MLXClient
from src.pipeline.batch_processing_service import BatchProcessingService
from src.pipeline.export_service import ExportService
from src.pipeline.file_processing_service import FileProcessingService
from src.pipeline.orchestration_service import OrchestrationService
from src.pipeline.preparation_service import PreparationService
from src.pipeline.repository_service import RepositoryService
from src.pipeline.retry_service import RetryService
from src.pipeline.scraping_service import ScrapingService
from src.pipeline.state_management_service import StateManagementService

# Type variable for generic types
T = TypeVar("T")


# Protocol for service factories
class ServiceFactory(Protocol):
    def __call__(self, container: "DIContainer") -> Any: ...


class DIContainer:
    """Dependency injection container for managing service instances."""

    def __init__(self):
        self._services: dict[type, Any] = {}
        self._factories: dict[type, ServiceFactory] = {}
        self._config: AppConfig | None = None
        self._validated_config: AppConfigModel | None = None

    def register_config(self, config: AppConfig) -> None:
        """Register the application configuration."""
        self._config = config
        # Also load the validated configuration model
        try:
            from src.core.config_loader import ConfigLoader

            loader = ConfigLoader()
            yaml_config = loader.load()
            self._validated_config = load_validated_config(yaml_config)
        except Exception as e:
            logging.warning(f"Could not load validated config: {e}")

    def register_singleton(self, service_type: type[T], instance: T) -> None:
        """Register a singleton service instance."""
        self._services[service_type] = instance

    def register_factory(self, service_type: type[T], factory: ServiceFactory) -> None:
        """Register a service factory."""
        self._factories[service_type] = factory

    def get(self, service_type: type[T]) -> T:
        """Get a service instance, creating it if necessary."""
        # Check for existing singleton
        if service_type in self._services:
            return self._services[service_type]

        # Check for factory and create instance
        if service_type in self._factories:
            instance = self._factories[service_type](self)
            # Register as singleton if it's a singleton service
            if self._is_singleton(service_type):
                self._services[service_type] = instance
            return instance

        raise ValueError(f"No factory or instance registered for {service_type}")

    def _is_singleton(self, service_type: type[T]) -> bool:
        """Check if a service type should be treated as singleton."""
        # Define which services should be singletons
        singleton_types = {AppConfig, AppConfigModel, LLMClient, MLXClient}
        return service_type in singleton_types

    @property
    def config(self) -> AppConfig:
        """Get the application configuration."""
        if self._config is None:
            # Check if we have it in services (registered as singleton)
            if AppConfig in self._services:
                self._config = self._services[AppConfig]
            else:
                self._config = AppConfig()
                # Store in services to ensure singleton behavior
                self._services[AppConfig] = self._config
        return self._config

    @property
    def validated_config(self) -> AppConfigModel | None:
        """Get the validated configuration model."""
        return self._validated_config


# Factory functions
def create_db_manager(container: DIContainer) -> DBManager:
    """Factory function for DBManager."""
    config = container.config
    # Compute db_path as data_dir / "pipeline.db" based on the original config logic
    db_path = Path(config.model.pipeline.data_dir) / "pipeline.db"
    return DBManager(db_path)


def create_file_manager(container: DIContainer) -> FileManager:
    """Factory function for FileManager."""
    config = container.config
    return FileManager(
        repos_dir=config.REPOS_DIR,
        max_file_size=config.model.pipeline.max_file_size,
        allowed_extensions=config.model.pipeline.allowed_extensions,
        allowed_json_md_files=config.model.pipeline.allowed_json_md_files,
    )


def create_llm_client(container: DIContainer) -> LLMClient:
    """Factory function for LLMClient or MLXClient."""
    config = container.config
    if config.model.use_mlx:
        # Ensure we have a valid MLX model name to avoid loading incompatible models
        mlx_model_name = config.model.mlx.model_name
        if not mlx_model_name or not mlx_model_name.startswith("mlx-"):
            logging.warning(f"MLX model name appears invalid: {mlx_model_name}. Expected format: 'mlx-...'")
            # Fallback to LLMClient only if MLX model name is completely invalid
            # This should only happen in configuration errors
            if not mlx_model_name:
                raise ValueError("MLX_MODEL_NAME not configured but USE_MLX is True")

        return MLXClient(
            model_name=mlx_model_name,
            max_retries=config.model.llm.max_retries,
            retry_delay=config.model.llm.retry_delay,
            config=config,
        )
    else:
        return LLMClient(
            base_url=config.model.llm.base_url,
            model_name=config.model.llm.model_name,
            max_retries=config.model.llm.max_retries,
            retry_delay=config.model.llm.retry_delay,
            request_timeout=config.model.llm.request_timeout,
            config=config,
        )


def create_file_processing_service(container: DIContainer) -> FileProcessingService:
    """Factory function for FileProcessingService."""
    llm_client = container.get(LLMClient)
    db_manager = container.get(DBManager)
    config = container.config
    return FileProcessingService(
        llm_client=llm_client,
        db_manager=db_manager,
        config=config,
    )


def create_repository_service(container: DIContainer) -> RepositoryService:
    """Factory function for RepositoryService."""
    config = container.config
    return RepositoryService(config=config)


def create_state_management_service(container: DIContainer) -> StateManagementService:
    """Factory function for StateManagementService."""
    db_manager = container.get(DBManager)
    config = container.config
    return StateManagementService(
        db_manager=db_manager,
        config=config,
    )


def create_batch_processing_service(container: DIContainer) -> BatchProcessingService:
    """Factory function for BatchProcessingService."""
    file_processing_service = container.get(FileProcessingService)
    db_manager = container.get(DBManager)
    config = container.config
    return BatchProcessingService(
        file_processing_service=file_processing_service,
        db_manager=db_manager,
        config=config,
    )


def create_scraping_service(container: DIContainer) -> ScrapingService:
    """Factory function for ScrapingService."""
    repository_service = container.get(RepositoryService)
    config = container.config
    return ScrapingService(repository_service, config)


def create_preparation_service(container: DIContainer) -> PreparationService:
    """Factory function for PreparationService."""
    db_manager = container.get(DBManager)
    file_manager = container.get(FileManager)
    file_processing_service = container.get(FileProcessingService)
    batch_processing_service = container.get(BatchProcessingService)
    state_management_service = container.get(StateManagementService)
    config = container.config
    return PreparationService(
        db_manager,
        file_manager,
        file_processing_service,
        batch_processing_service,
        state_management_service,
        config,
    )


def create_retry_service(container: DIContainer) -> RetryService:
    """Factory function for RetryService."""
    db_manager = container.get(DBManager)
    file_processing_service = container.get(FileProcessingService)
    return RetryService(db_manager, file_processing_service)


def create_export_service(container: DIContainer) -> ExportService:
    """Factory function for ExportService."""
    db_manager = container.get(DBManager)
    config = container.config
    return ExportService(db_manager, config)


def create_orchestration_service(container: DIContainer) -> OrchestrationService:
    """Factory function for OrchestrationService."""
    config = container.config
    return OrchestrationService(container, config)


def setup_container(config: AppConfig | None = None) -> DIContainer:
    """Set up the dependency injection container with all services."""
    container = DIContainer()

    # Register configuration
    if config:
        container.register_config(config)

    # Register factories
    container.register_factory(DBManager, create_db_manager)
    container.register_factory(FileManager, create_file_manager)
    container.register_factory(LLMClient, create_llm_client)
    container.register_factory(FileProcessingService, create_file_processing_service)
    container.register_factory(RepositoryService, create_repository_service)
    container.register_factory(StateManagementService, create_state_management_service)
    container.register_factory(BatchProcessingService, create_batch_processing_service)
    container.register_factory(ScrapingService, create_scraping_service)
    container.register_factory(PreparationService, create_preparation_service)
    container.register_factory(RetryService, create_retry_service)
    container.register_factory(ExportService, create_export_service)
    container.register_factory(OrchestrationService, create_orchestration_service)

    return container
