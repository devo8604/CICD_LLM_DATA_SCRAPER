from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.export_service import ExportService
from src.pipeline.preparation_service import PreparationService
from src.pipeline.retry_service import RetryService
from src.pipeline.scraping_service import ScrapingService
from src.pipeline.state_management_service import StateManagementService

if TYPE_CHECKING:
    from src.pipeline.di_container import DIContainer


class OrchestrationService:
    def __init__(self, container: DIContainer, config: AppConfig):
        self.container = container
        self.config = config
        self.state_management_service = self.container.get(StateManagementService)

    def scrape(self, progress_callback=None):
        scraping_service = self.container.get(ScrapingService)
        scraping_service.scrape(progress_callback)

    def prepare(self, processing_started_callback=None, cancellation_event=None):
        preparation_service = self.container.get(PreparationService)
        preparation_service.prepare(processing_started_callback, cancellation_event)

    def retry(self):
        retry_service = self.container.get(RetryService)
        retry_service.retry()

    def export(self, template: str, output_file: str):
        export_service = self.container.get(ExportService)
        export_service.export(template, output_file)

    def close(self):
        db_manager = self.container.get(DBManager)
        db_manager.close_db()
