import os

from src.core.config import AppConfig
from src.pipeline.repository_service import RepositoryService


class ScrapingService:
    def __init__(self, repository_service: RepositoryService, config: AppConfig):
        self.repository_service = repository_service
        self.config = config
        self.repos_dir = os.path.join(self.config.BASE_DIR, "repos")

    def scrape(self, progress_callback=None):
        self.repository_service.scrape_repositories(self.repos_dir, progress_callback)
