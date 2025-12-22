from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.repository_service import RepositoryService


class TestRepositoryServiceFull:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.DATA_DIR = "data"
        return config

    @pytest.fixture
    def service(self, mock_config):
        return RepositoryService(mock_config)

    @patch("src.pipeline.repository_service.get_repo_urls_from_file")
    @patch("src.pipeline.repository_service.get_repos_from_github_page")
    @patch("src.pipeline.repository_service.clone_or_update_repos")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open)
    def test_scrape_repositories_github_org(
        self, mock_file, mock_walk, mock_clone, mock_get_github, mock_get_urls, service
    ):
        mock_get_urls.return_value = ["https://github.com/org"]
        mock_get_github.return_value = [
            "https://github.com/org/repo1",
            "https://github.com/org/repo2",
        ]
        mock_walk.return_value = [
            ("/repos/repo1", [".git"], []),
            ("/repos/repo2", [".git"], []),
        ]

        service.scrape_repositories("/repos")

        mock_get_github.assert_called_with("https://github.com/org")
        mock_clone.assert_called()
        args, _ = mock_clone.call_args
        assert "/repos" in args
        assert set(args[1]) == {
            "https://github.com/org/repo1",
            "https://github.com/org/repo2",
        }

        # Check file write
        mock_file.assert_called_with("data/repo_count.txt", "w")
        mock_file().write.assert_called_with("2")

    @patch("src.pipeline.repository_service.get_repo_urls_from_file")
    @patch("src.pipeline.repository_service.get_repos_from_github_page")
    @patch("src.pipeline.repository_service.clone_or_update_repos")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open)
    def test_scrape_repositories_direct_repo(
        self, mock_file, mock_walk, mock_clone, mock_get_github, mock_get_urls, service
    ):
        mock_get_urls.return_value = ["https://github.com/org/repo"]
        mock_walk.return_value = [("/repos/repo", [".git"], [])]

        service.scrape_repositories("/repos")

        mock_get_github.assert_not_called()
        mock_clone.assert_called()
        args, _ = mock_clone.call_args
        assert "https://github.com/org/repo" in args[1]

    @patch("src.pipeline.repository_service.get_repo_urls_from_file")
    @patch("src.pipeline.repository_service.get_repos_from_github_page")
    @patch("src.pipeline.repository_service.clone_or_update_repos")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open)
    def test_scrape_repositories_mixed(self, mock_file, mock_walk, mock_clone, mock_get_github, mock_get_urls, service):
        mock_get_urls.return_value = [
            "https://github.com/org",
            "https://github.com/other/repo",
            "https://gitlab.com/group/project",
        ]
        mock_get_github.return_value = ["https://github.com/org/repo1"]

        service.scrape_repositories("/repos")

        mock_clone.assert_called()
        args, _ = mock_clone.call_args
        repos = args[1]
        assert "https://github.com/org/repo1" in repos
        assert "https://github.com/other/repo" in repos
        assert "https://gitlab.com/group/project" in repos

    @patch("src.pipeline.repository_service.get_repo_urls_from_file")
    @patch("src.pipeline.repository_service.get_repos_from_github_page")
    @patch("src.pipeline.repository_service.clone_or_update_repos")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open)
    def test_scrape_repositories_empty_org(
        self, mock_file, mock_walk, mock_clone, mock_get_github, mock_get_urls, service
    ):
        mock_get_urls.return_value = ["https://github.com/empty-org"]
        mock_get_github.return_value = []  # Empty

        service.scrape_repositories("/repos")

        mock_clone.assert_called()
        args, _ = mock_clone.call_args
        assert len(args[1]) == 0  # No repos found

    @patch("src.pipeline.repository_service.get_repo_urls_from_file")
    @patch("src.pipeline.repository_service.clone_or_update_repos")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open)
    def test_scrape_repositories_weird_url(self, mock_file, mock_walk, mock_clone, mock_get_urls, service):
        mock_get_urls.return_value = ["https://github.com"]  # Too short

        service.scrape_repositories("/repos")

        mock_clone.assert_called()
        args, _ = mock_clone.call_args
        assert "https://github.com" in args[1]  # Treated as direct repo
