"""Service layer for repository operations."""

import logging
import os
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from tqdm import tqdm

from src.config import AppConfig
from src.utils import (
    get_repo_urls_from_file,
    get_repos_from_github_page,
    clone_or_update_repos,
)

# Get the dedicated logger for tqdm output
tqdm_logger = logging.getLogger("tqdm_logger")


class RepositoryService:
    """Handles repository cloning, updating, and discovery operations."""

    def __init__(self, config: AppConfig):
        self.config = config

    async def scrape_repositories(self, repos_dir: str):
        """Clone or update repositories based on the repos.txt file."""
        root_logger = logging.getLogger()
        root_logger.info(
            "Starting scrape operation: Cloning or updating repositories..."
        )
        initial_urls = get_repo_urls_from_file()
        all_repos_to_clone = []

        for url in initial_urls:
            parsed_url = urlparse(url)

            if "github.com" in parsed_url.netloc:
                path_segments = [s for s in parsed_url.path.split("/") if s]

                if len(path_segments) == 1:
                    root_logger.info(f"Detected GitHub user/organization page: {url}")
                    discovered_repos = get_repos_from_github_page(url)
                    if discovered_repos:
                        root_logger.info(
                            f"Discovered {len(discovered_repos)} repositories from {url}"
                        )
                        all_repos_to_clone.extend(discovered_repos)
                    else:
                        root_logger.warning(
                            f"No repositories discovered from {url}. It might be empty or my scraping logic needs adjustment."
                        )
                elif len(path_segments) >= 2:
                    root_logger.info(
                        f"Detected direct GitHub repository or path within: {url}"
                    )
                    all_repos_to_clone.append(url)
                else:
                    root_logger.warning(
                        f"Unknown GitHub URL format: {url}. Treating as direct repo."
                    )
                    all_repos_to_clone.append(url)
            else:
                root_logger.info(
                    f"Detected non-GitHub URL: {url}. Treating as direct repo."
                )
                all_repos_to_clone.append(url)

        all_repos_to_clone = list(set(all_repos_to_clone))

        root_logger.info(
            f"Total unique repositories to process: {len(all_repos_to_clone)}"
        )
        await clone_or_update_repos(repos_dir, all_repos_to_clone)

        # After cloning/updating, count the actual number of repositories
        repo_count = 0
        for root, dirs, files in os.walk(repos_dir):
            if ".git" in dirs:
                repo_count += 1
                dirs[:] = []  # Prune search

        # Save the count
        count_file_path = os.path.join(self.config.DATA_DIR, "repo_count.txt")
        with open(count_file_path, "w") as f:
            f.write(str(repo_count))

        root_logger.info(
            f"Found {repo_count} total repositories. Count saved to {count_file_path}."
        )
        root_logger.info("Scrape operation completed.")
