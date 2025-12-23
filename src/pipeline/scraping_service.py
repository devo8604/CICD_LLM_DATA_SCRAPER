from pathlib import Path

from src.core.config import AppConfig
from src.pipeline.repository_service import RepositoryService


class ScrapingService:
    def __init__(self, repository_service: RepositoryService, config: AppConfig):
        self.repository_service = repository_service
        self.config = config
        # Compute repos_dir from config.model.*
        base_dir = Path(self.config.model.pipeline.base_dir)
        data_dir = base_dir / self.config.model.pipeline.data_dir
        self.repos_dir = str(data_dir / self.config.model.pipeline.repos_dir_name)

    def scrape(self, progress_callback=None):
        self.repository_service.scrape_repositories(self.repos_dir, progress_callback)
