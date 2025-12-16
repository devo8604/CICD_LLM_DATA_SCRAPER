"""Comprehensive unit tests for the CLI argument parsing."""

import pytest
import sys
from unittest.mock import patch

from src.cli import parse_arguments
from src.config import AppConfig


class TestCLIScrapeCommand:
    """Test cases for scrape command parsing."""

    def test_scrape_command(self):
        """Test parsing scrape command."""
        with patch.object(sys, 'argv', ['prog', 'scrape']):
            args = parse_arguments()
            assert args.command == 'scrape'


class TestCLIPrepareCommand:
    """Test cases for prepare command parsing."""

    def test_prepare_command_defaults(self):
        """Test prepare command with default arguments."""
        with patch.object(sys, 'argv', ['prog', 'prepare']):
            args = parse_arguments()
            assert args.command == 'prepare'
            config = AppConfig()
            assert args.max_tokens == config.DEFAULT_MAX_TOKENS
            assert args.temperature == config.DEFAULT_TEMPERATURE

    def test_prepare_command_with_max_tokens(self):
        """Test prepare command with custom max_tokens."""
        with patch.object(sys, 'argv', ['prog', 'prepare', '--max-tokens', '1000']):
            args = parse_arguments()
            assert args.max_tokens == 1000

    def test_prepare_command_with_temperature(self):
        """Test prepare command with custom temperature."""
        with patch.object(sys, 'argv', ['prog', 'prepare', '--temperature', '0.9']):
            args = parse_arguments()
            assert args.temperature == 0.9

    def test_prepare_command_with_all_options(self):
        """Test prepare command with all options."""
        with patch.object(sys, 'argv', [
            'prog', 'prepare',
            '--max-tokens', '2000',
            '--temperature', '0.5'
        ]):
            args = parse_arguments()
            assert args.max_tokens == 2000
            assert args.temperature == 0.5


class TestCLIRetryCommand:
    """Test cases for retry command parsing."""

    def test_retry_command(self):
        """Test parsing retry command."""
        with patch.object(sys, 'argv', ['prog', 'retry']):
            args = parse_arguments()
            assert args.command == 'retry'


class TestCLIExportCommand:
    """Test cases for export command parsing."""

    def test_export_command_csv(self):
        """Test export command with CSV template."""
        with patch.object(sys, 'argv', [
            'prog', 'export',
            '--template', 'csv',
            '--output-file', 'output.csv'
        ]):
            args = parse_arguments()
            assert args.command == 'export'
            assert args.template == 'csv'
            assert args.output_file == 'output.csv'

    def test_export_command_llama3(self):
        """Test export command with llama3 template."""
        with patch.object(sys, 'argv', [
            'prog', 'export',
            '--template', 'llama3',
            '--output-file', 'output.txt'
        ]):
            args = parse_arguments()
            assert args.template == 'llama3'

    def test_export_command_alpaca_jsonl(self):
        """Test export command with alpaca-jsonl template."""
        with patch.object(sys, 'argv', [
            'prog', 'export',
            '--template', 'alpaca-jsonl',
            '--output-file', 'output.jsonl'
        ]):
            args = parse_arguments()
            assert args.template == 'alpaca-jsonl'

    def test_export_command_all_templates(self):
        """Test that all template choices are accepted."""
        templates = ['csv', 'llama3', 'mistral', 'gemma', 'alpaca-jsonl', 'chatml-jsonl']

        for template in templates:
            with patch.object(sys, 'argv', [
                'prog', 'export',
                '--template', template,
                '--output-file', 'output.txt'
            ]):
                args = parse_arguments()
                assert args.template == template

    def test_export_command_requires_template(self):
        """Test that export command requires template argument."""
        with patch.object(sys, 'argv', ['prog', 'export', '--output-file', 'out.txt']):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_export_command_requires_output_file(self):
        """Test that export command requires output-file argument."""
        with patch.object(sys, 'argv', ['prog', 'export', '--template', 'csv']):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestCLIMLXCommands:
    """Test cases for MLX management commands."""

    def test_mlx_list_command(self):
        """Test MLX list command."""
        with patch.object(sys, 'argv', ['prog', 'mlx', 'list']):
            args = parse_arguments()
            assert args.command == 'mlx'
            assert args.mlx_command == 'list'

    def test_mlx_list_with_all_flag(self):
        """Test MLX list command with --all flag."""
        with patch.object(sys, 'argv', ['prog', 'mlx', 'list', '--all']):
            args = parse_arguments()
            assert args.all is True

    def test_mlx_download_command(self):
        """Test MLX download command."""
        with patch.object(sys, 'argv', [
            'prog', 'mlx', 'download',
            'mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit'
        ]):
            args = parse_arguments()
            assert args.command == 'mlx'
            assert args.mlx_command == 'download'
            assert args.model_name == 'mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit'

    def test_mlx_remove_command(self):
        """Test MLX remove command."""
        with patch.object(sys, 'argv', [
            'prog', 'mlx', 'remove',
            'some-model-name'
        ]):
            args = parse_arguments()
            assert args.command == 'mlx'
            assert args.mlx_command == 'remove'
            assert args.model_name == 'some-model-name'

    def test_mlx_info_command(self):
        """Test MLX info command."""
        with patch.object(sys, 'argv', [
            'prog', 'mlx', 'info',
            'some-model-name'
        ]):
            args = parse_arguments()
            assert args.command == 'mlx'
            assert args.mlx_command == 'info'
            assert args.model_name == 'some-model-name'


class TestCLIGlobalArguments:
    """Test cases for global arguments."""

    def test_max_file_size_default(self):
        """Test default max-file-size."""
        with patch.object(sys, 'argv', ['prog', 'scrape']):
            args = parse_arguments()
            config = AppConfig()
            assert args.max_file_size == config.MAX_FILE_SIZE

    def test_max_file_size_custom(self):
        """Test custom max-file-size."""
        with patch.object(sys, 'argv', ['prog', 'scrape', '--max-file-size', '10000000']):
            args = parse_arguments()
            assert args.max_file_size == 10000000

    def test_data_dir_default(self):
        """Test default data-dir."""
        with patch.object(sys, 'argv', ['prog', 'scrape']):
            args = parse_arguments()
            config = AppConfig()
            assert args.data_dir == config.DATA_DIR

    def test_data_dir_custom(self):
        """Test custom data-dir."""
        with patch.object(sys, 'argv', ['prog', 'scrape', '--data-dir', 'custom_data']):
            args = parse_arguments()
            assert args.data_dir == 'custom_data'

    def test_max_log_files_default(self):
        """Test default max-log-files."""
        with patch.object(sys, 'argv', ['prog', 'scrape']):
            args = parse_arguments()
            config = AppConfig()
            assert args.max_log_files == config.MAX_LOG_FILES

    def test_max_log_files_custom(self):
        """Test custom max-log-files."""
        with patch.object(sys, 'argv', ['prog', 'scrape', '--max-log-files', '10']):
            args = parse_arguments()
            assert args.max_log_files == 10

    def test_global_args_with_prepare(self):
        """Test global arguments combined with prepare command."""
        with patch.object(sys, 'argv', [
            'prog', 'prepare',
            '--max-file-size', '5000000',
            '--data-dir', 'my_data',
            '--max-log-files', '3',
            '--max-tokens', '1000',
            '--temperature', '0.8'
        ]):
            args = parse_arguments()
            assert args.command == 'prepare'
            assert args.max_file_size == 5000000
            assert args.data_dir == 'my_data'
            assert args.max_log_files == 3
            assert args.max_tokens == 1000
            assert args.temperature == 0.8


class TestCLIErrorCases:
    """Test error cases and invalid inputs."""

    def test_no_command(self):
        """Test that no command raises SystemExit."""
        with patch.object(sys, 'argv', ['prog']):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_invalid_command(self):
        """Test that invalid command raises SystemExit."""
        with patch.object(sys, 'argv', ['prog', 'invalid']):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_invalid_template_choice(self):
        """Test that invalid template choice raises SystemExit."""
        with patch.object(sys, 'argv', [
            'prog', 'export',
            '--template', 'invalid_template',
            '--output-file', 'out.txt'
        ]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_mlx_missing_subcommand(self):
        """Test that MLX command without subcommand raises SystemExit."""
        with patch.object(sys, 'argv', ['prog', 'mlx']):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_mlx_download_missing_model_name(self):
        """Test that MLX download without model name raises SystemExit."""
        with patch.object(sys, 'argv', ['prog', 'mlx', 'download']):
            with pytest.raises(SystemExit):
                parse_arguments()
