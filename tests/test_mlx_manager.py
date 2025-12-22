from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.llm.mlx_manager import MLXModelManager, handle_mlx_command


class TestMLXManager:
    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, mock_config):
        # Patch Path.home to avoid messing with real user cache
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/tmp/mock_home")
            manager = MLXModelManager(mock_config)
            yield manager

    def test_init(self, manager):
        assert manager.cache_dir == Path("/tmp/mock_home/.cache/huggingface/hub")

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", True)
    def test_list_local_models(self, manager):
        # Mock cache dir existence and iteration
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "iterdir") as mock_iterdir,
            patch.object(manager, "_get_directory_size", return_value=1024),
        ):
            # Setup mock directories
            model_dir = MagicMock()
            model_dir.is_dir.return_value = True
            model_dir.name = "models--org--model"
            model_dir.rglob.return_value = ["file.safetensors"]  # make list valid

            mock_iterdir.return_value = [model_dir]

            models = manager.list_local_models()

            assert len(models) == 1
            assert models[0]["name"] == "org/model"
            assert models[0]["size"] == "1.0 KB"

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", False)
    def test_list_local_models_unavailable(self, manager):
        assert manager.list_local_models() == []

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", True)
    @patch("src.llm.mlx_manager.huggingface_hub")
    def test_download_model_success(self, mock_hub, manager):
        from unittest.mock import ANY

        assert manager.download_model("model-name") is True
        mock_hub.snapshot_download.assert_called_with(repo_id="model-name", local_dir=None, allow_patterns=ANY)

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", True)
    @patch("src.llm.mlx_manager.huggingface_hub")
    def test_download_model_failure(self, mock_hub, manager):
        mock_hub.snapshot_download.side_effect = Exception("Download error")
        assert manager.download_model("model-name") is False

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", False)
    def test_download_model_unavailable(self, manager):
        assert manager.download_model("model-name") is False

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", True)
    @patch("src.llm.mlx_manager.load")
    def test_preload_model_success(self, mock_load, manager):
        mock_load.return_value = (MagicMock(), MagicMock())
        assert manager.preload_model("model-name") is True
        mock_load.assert_called()

    @patch("src.llm.mlx_manager.MLX_AVAILABLE", False)
    def test_preload_model_unavailable(self, manager):
        assert manager.preload_model("model-name") is False

    @patch("src.llm.mlx_manager.shutil")
    @patch("builtins.input", return_value="yes")
    def test_remove_model_success(self, mock_input, mock_shutil, manager):
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(manager, "_get_directory_size", return_value=100),
        ):
            assert manager.remove_model("org/model") is True
            mock_shutil.rmtree.assert_called()

    @patch("builtins.input", return_value="no")
    def test_remove_model_cancel(self, mock_input, manager):
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(manager, "_get_directory_size", return_value=100),
        ):
            assert manager.remove_model("org/model") is False

    def test_remove_model_not_found(self, manager):
        with patch.object(Path, "exists", return_value=False):
            assert manager.remove_model("org/model") is False

    def test_get_model_info_cached(self, manager):
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(manager, "_get_directory_size", return_value=1024),
            patch.object(Path, "rglob") as mock_rglob,
        ):
            mock_file = MagicMock()
            mock_file.is_file.return_value = True
            mock_file.relative_to.return_value = Path("file.txt")
            mock_rglob.return_value = [mock_file]

            info = manager.get_model_info("org/model")

            assert info["name"] == "org/model"
            assert info["cached"] is True
            assert info["file_count"] == 1

    def test_get_model_info_not_cached(self, manager):
        with patch.object(Path, "exists", return_value=False):
            info = manager.get_model_info("org/model")
            assert info["name"] == "org/model"
            assert info["cached"] is False

    def test_format_size(self, manager):
        assert manager._format_size(500) == "500.0 B"
        assert manager._format_size(1024) == "1.0 KB"
        assert manager._format_size(1024 * 1024) == "1.0 MB"
        assert manager._format_size(1024 * 1024 * 1024) == "1.0 GB"

    @patch("src.llm.mlx_manager.MLXModelManager")
    def test_handle_mlx_command(self, mock_manager_cls):
        mock_manager = mock_manager_cls.return_value
        mock_args = MagicMock()

        # Test list command
        mock_args.mlx_command = "list"
        handle_mlx_command(mock_args)
        mock_manager.list_local_models.assert_called()

        # Test download command
        mock_args.mlx_command = "download"
        mock_args.model_name = "test-model"
        handle_mlx_command(mock_args)
        mock_manager.download_model.assert_called_with("test-model")

        # Test remove command
        mock_args.mlx_command = "remove"
        mock_args.model_name = "test-model"
        handle_mlx_command(mock_args)
        mock_manager.remove_model.assert_called_with("test-model")

        # Test info command
        mock_args.mlx_command = "info"
        mock_args.model_name = "test-model"
        handle_mlx_command(mock_args)
        mock_manager.get_model_info.assert_called_with("test-model")
