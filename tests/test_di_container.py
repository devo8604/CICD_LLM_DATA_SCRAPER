from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.data.file_manager import FileManager
from src.llm.llm_client import LLMClient
from src.pipeline.batch_processing_service import BatchProcessingService
from src.pipeline.di_container import (
    DIContainer,
    create_batch_processing_service,
    create_db_manager,
    create_export_service,
    create_file_manager,
    create_file_processing_service,
    create_llm_client,
    create_orchestration_service,
    create_preparation_service,
    create_repository_service,
    create_retry_service,
    create_scraping_service,
    create_state_management_service,
    setup_container,
)
from src.pipeline.file_processing_service import FileProcessingService
from src.pipeline.repository_service import RepositoryService
from src.pipeline.state_management_service import StateManagementService


class TestDIContainer:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.DATA_DIR = "data"
        config.DB_PATH = "pipeline.db"
        config.REPOS_DIR = "repos"
        config.MAX_FILE_SIZE = 1024
        config.USE_MLX = False
        config.LLM_BASE_URL = "http://localhost"
        config.LLM_MODEL_NAME = "test-model"
        config.LLM_MAX_RETRIES = 3
        config.LLM_RETRY_DELAY = 1
        config.LLM_REQUEST_TIMEOUT = 10

        # Mock model properties
        config.model.use_mlx = False
        config.model.llm.base_url = "http://localhost"
        config.model.llm.model_name = "test-model"
        config.model.llm.max_retries = 3
        config.model.llm.retry_delay = 1
        config.model.llm.request_timeout = 10
        config.model.mlx.model_name = "mlx-model"
        config.model.pipeline.data_dir = "data"
        config.REPOS_DIR = "repos"
        config.model.pipeline.repos_dir_name = "repos"
        config.model.pipeline.max_file_size = 1024
        config.model.pipeline.allowed_extensions = []
        config.model.pipeline.allowed_json_md_files = []

        return config

    @pytest.fixture
    def container(self, mock_config):
        container = DIContainer()
        container.register_config(mock_config)
        return container

    def test_register_and_get_singleton(self, container):
        instance = MagicMock()
        container.register_singleton(str, instance)
        assert container.get(str) is instance

    def test_register_and_get_factory(self, container):
        factory = MagicMock(return_value="test_string")
        container.register_factory(str, factory)

        result = container.get(str)
        assert result == "test_string"
        factory.assert_called_with(container)

    def test_get_unregistered_raises_error(self, container):
        with pytest.raises(ValueError):
            container.get(int)

    def test_is_singleton_caching(self, container):
        # Use AppConfig as it's already in singleton_types
        # We don't patch the class globally to avoid breaking 'is' checks in DIContainer
        mock_instance = MagicMock(spec=AppConfig)
        factory = MagicMock(return_value=mock_instance)

        # Reset container state
        container._services.pop(AppConfig, None)
        container._config = None

        container.register_factory(AppConfig, factory)

        # First access via get() should trigger factory
        instance1 = container.get(AppConfig)
        # Second access via config property should return same instance without factory call
        instance2 = container.config

        assert instance1 is instance2
        factory.assert_called_once()

    def test_config_property_creates_default(self):
        with patch("src.pipeline.di_container.AppConfig", spec=AppConfig) as mock_config_cls:
            container = DIContainer()
            # Ensure _config is None
            container._config = None
            _ = container.config
            mock_config_cls.assert_called_once()

    def test_register_config_loads_validated(self):
        container = DIContainer()
        config = MagicMock(spec=AppConfig)

        with (
            patch("src.core.config_loader.ConfigLoader") as mock_loader,
            patch("src.pipeline.di_container.load_validated_config") as mock_validate,
        ):
            container.register_config(config)
            mock_loader.return_value.load.assert_called()
            mock_validate.assert_called()
            assert container.validated_config is not None

    def test_create_db_manager(self, container):
        with patch("src.pipeline.di_container.DBManager") as mock_cls:
            manager = create_db_manager(container)
            mock_cls.assert_called()
            assert manager == mock_cls.return_value

    def test_create_file_manager(self, container):
        with patch("src.pipeline.di_container.FileManager") as mock_cls:
            manager = create_file_manager(container)
            mock_cls.assert_called()
            assert manager == mock_cls.return_value

    def test_create_llm_client_standard(self, container):
        container.config.USE_MLX = False
        container.config.model.use_mlx = False
        with patch("src.pipeline.di_container.LLMClient") as mock_cls:
            client = create_llm_client(container)
            mock_cls.assert_called()
            assert client == mock_cls.return_value

    def test_create_llm_client_mlx(self, container):
        container.config.USE_MLX = True
        container.config.model.use_mlx = True
        container.config.MLX_MODEL_NAME = "mlx-model"
        container.config.model.mlx.model_name = "mlx-model"
        with patch("src.pipeline.di_container.MLXClient") as mock_cls:
            client = create_llm_client(container)
            mock_cls.assert_called()
            assert client == mock_cls.return_value

    def test_create_llm_client_mlx_invalid(self, container):
        container.config.USE_MLX = True
        container.config.model.use_mlx = True
        container.config.MLX_MODEL_NAME = "invalid-model"
        container.config.model.mlx.model_name = "invalid-model"

        with patch("src.pipeline.di_container.MLXClient") as mock_cls:
            create_llm_client(container)
            mock_cls.assert_called()

        container.config.MLX_MODEL_NAME = ""
        container.config.model.mlx.model_name = ""
        with pytest.raises(ValueError):
            create_llm_client(container)

    def test_create_file_processing_service(self, container):
        container.register_singleton(LLMClient, MagicMock())
        container.register_singleton(DBManager, MagicMock())

        with patch("src.pipeline.di_container.FileProcessingService") as mock_cls:
            _ = create_file_processing_service(container)
            mock_cls.assert_called()

    def test_create_repository_service(self, container):
        with patch("src.pipeline.di_container.RepositoryService") as mock_cls:
            _ = create_repository_service(container)
            mock_cls.assert_called()

    def test_create_state_management_service(self, container):
        container.register_singleton(DBManager, MagicMock())
        with patch("src.pipeline.di_container.StateManagementService") as mock_cls:
            _ = create_state_management_service(container)
            mock_cls.assert_called()

    def test_create_batch_processing_service(self, container):
        container.register_singleton(FileProcessingService, MagicMock())
        container.register_singleton(DBManager, MagicMock())
        with patch("src.pipeline.di_container.BatchProcessingService") as mock_cls:
            _ = create_batch_processing_service(container)
            mock_cls.assert_called()

    def test_create_scraping_service(self, container):
        container.register_singleton(RepositoryService, MagicMock())
        with patch("src.pipeline.di_container.ScrapingService") as mock_cls:
            _ = create_scraping_service(container)
            mock_cls.assert_called()

    def test_create_preparation_service(self, container):
        container.register_singleton(DBManager, MagicMock())
        container.register_singleton(FileManager, MagicMock())
        container.register_singleton(FileProcessingService, MagicMock())
        container.register_singleton(BatchProcessingService, MagicMock())
        container.register_singleton(StateManagementService, MagicMock())

        with patch("src.pipeline.di_container.PreparationService") as mock_cls:
            _ = create_preparation_service(container)
            mock_cls.assert_called()

    def test_create_retry_service(self, container):
        container.register_singleton(DBManager, MagicMock())
        container.register_singleton(FileProcessingService, MagicMock())
        with patch("src.pipeline.di_container.RetryService") as mock_cls:
            _ = create_retry_service(container)
            mock_cls.assert_called()

    def test_create_export_service(self, container):
        container.register_singleton(DBManager, MagicMock())
        with patch("src.pipeline.di_container.ExportService") as mock_cls:
            _ = create_export_service(container)
            mock_cls.assert_called()

    def test_create_orchestration_service(self, container):
        with patch("src.pipeline.di_container.OrchestrationService") as mock_cls:
            _ = create_orchestration_service(container)
            mock_cls.assert_called()

    def test_setup_container(self, mock_config):
        container = setup_container(mock_config)
        assert container.config is mock_config
        assert DBManager in container._factories
        assert LLMClient in container._factories
