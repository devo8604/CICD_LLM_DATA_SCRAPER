"""Service layer for repository operations."""

import os
from urllib.parse import urlparse

import structlog

from src.core.config import AppConfig
from src.core.utils import (
    clone_or_update_repos,
    get_repo_urls_from_file,
    get_repos_from_github_page,
)

logger = structlog.get_logger(__name__)


class RepositoryService:
    """Handles repository cloning, updating, and discovery operations."""

    def __init__(self, config: AppConfig):
        self.config = config

    def scrape_repositories(self, repos_dir: str, progress_callback=None):
        """Clone or update repositories based on the repos.txt file."""
        logger.info("Starting scrape operation")
        initial_urls = get_repo_urls_from_file()
        all_repos_to_clone = []

        for url in initial_urls:
            parsed_url = urlparse(url)

            if "github.com" in parsed_url.netloc:
                path_segments = [s for s in parsed_url.path.split("/") if s]

                if len(path_segments) == 1:
                    logger.info("Detected GitHub user/organization page", url=url)
                    discovered_repos = get_repos_from_github_page(url)
                    if discovered_repos:
                        logger.info("Discovered repositories", url=url, count=len(discovered_repos))
                        all_repos_to_clone.extend(discovered_repos)
                    else:
                        logger.warning("No repositories discovered from GitHub page", url=url)
                elif len(path_segments) >= 2:
                    logger.info("Detected direct GitHub repository", url=url)
                    all_repos_to_clone.append(url)
                else:
                    logger.warning("Unknown GitHub URL format, treating as direct repo", url=url)
                    all_repos_to_clone.append(url)
            else:
                logger.info("Detected non-GitHub URL, treating as direct repo", url=url)
                all_repos_to_clone.append(url)

        all_repos_to_clone = list(set(all_repos_to_clone))

        logger.info("Unique repositories to process", count=len(all_repos_to_clone))
        clone_or_update_repos(repos_dir, all_repos_to_clone, progress_callback)

        # After cloning/updating, count the actual number of repositories
        repo_count = 0
        for root, dirs, _ in os.walk(repos_dir):
            if ".git" in dirs:
                repo_count += 1
                dirs[:] = []  # Prune search

        # Save the count
        count_file_path = os.path.join(self.config.DATA_DIR, "repo_count.txt")
        with open(count_file_path, "w", encoding="utf-8") as f:
            f.write(str(repo_count))

        logger.info("Scrape operation completed", repo_count=repo_count)