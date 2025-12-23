"""Unit tests for reset_utils command handling."""

import unittest
from unittest.mock import MagicMock, patch

from src.utils.reset_utils import cleanup_disk, handle_reset_command


class TestResetUtilsCommand(unittest.TestCase):
    @patch("src.utils.reset_utils.DiskCleanupManager")
    def test_cleanup_disk(self, MockManager):
        """Test cleanup_disk function."""
        mock_instance = MockManager.return_value
        mock_instance.force_cleanup.return_value = {"deleted": 10}

        config = MagicMock()
        stats = cleanup_disk(config)

        MockManager.assert_called_with(config)
        mock_instance.force_cleanup.assert_called_once()
        self.assertEqual(stats, {"deleted": 10})

    @patch("src.utils.reset_utils.reset_database")
    @patch("src.utils.reset_utils.reset_logs")
    @patch("src.utils.reset_utils.reset_repos")
    @patch("src.utils.reset_utils.reset_all")
    @patch("src.utils.reset_utils.cleanup_disk")
    def test_handle_reset_command(self, mock_cleanup, mock_all, mock_repos, mock_logs, mock_db):
        """Test handle_reset_command for various subcommands."""
        config = MagicMock()
        config.model.pipeline.data_dir = "data"

        # Helper to create args
        def create_args(cmd):
            args = MagicMock()
            args.reset_command = cmd
            args.data_dir = "data"
            return args

        # Test 'db'
        mock_db.return_value = True
        code = handle_reset_command(create_args("db"), config)
        self.assertEqual(code, 0)
        mock_db.assert_called()

        # Test 'logs'
        mock_logs.return_value = True
        code = handle_reset_command(create_args("logs"), config)
        self.assertEqual(code, 0)
        mock_logs.assert_called()

        # Test 'repos'
        mock_repos.return_value = True
        code = handle_reset_command(create_args("repos"), config)
        self.assertEqual(code, 0)
        mock_repos.assert_called()

        # Test 'all'
        mock_all.return_value = True
        code = handle_reset_command(create_args("all"), config)
        self.assertEqual(code, 0)
        mock_all.assert_called()

        # Test 'cleanup'
        mock_cleanup.return_value = {}
        code = handle_reset_command(create_args("cleanup"), config)
        self.assertEqual(code, 0)
        mock_cleanup.assert_called()

        # Test invalid
        code = handle_reset_command(create_args("invalid"), config)
        self.assertEqual(code, 1)

    @patch("src.utils.reset_utils.reset_database")
    def test_handle_reset_command_failure(self, mock_db):
        """Test handle_reset_command failure case."""
        config = MagicMock()
        config.model.pipeline.data_dir = "data"

        args = MagicMock()
        args.reset_command = "db"

        mock_db.return_value = False
        code = handle_reset_command(args, config)
        self.assertEqual(code, 1)

    @patch("src.utils.reset_utils.Path.mkdir")
    def test_handle_reset_command_defaults(self, mock_mkdir):
        """Test handle_reset_command uses config defaults if args missing."""
        config = MagicMock()
        config.model.pipeline.data_dir = "default_data"
        config.DATA_DIR = "default_data"

        args = MagicMock()
        # No data_dir attribute
        del args.data_dir
        args.reset_command = "db"

        with patch("src.utils.reset_utils.reset_database") as mock_db:
            handle_reset_command(args, config)
            # Verify it constructed path using default_data
            # Since data_dir is calculated as Path.cwd() / "default_data"
            # We can check the call args to reset_database
            call_arg = mock_db.call_args[0][0]
            self.assertTrue(str(call_arg).endswith("default_data/pipeline.db"))
