"""Unit tests for the exporters module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config import AppConfig
from src.pipeline.exporters import DataExporter


class TestDataExporter:
    """Test the DataExporter class."""

    def setup_method(self):
        """Set up for each test."""
        self.mock_db_manager = patch("src.pipeline.exporters.DBManager").start().return_value
        self.mock_db_manager.db_path = "test.db"
        self.mock_config = MagicMock(spec=AppConfig)
        # Set up default config values needed by DataExporter
        self.mock_config.LLAMA3_CHAT_TEMPLATE = "{system_content}{user_content}{assistant_content}"
        self.mock_config.MISTRAL_CHAT_TEMPLATE = "{system_and_user_content}{assistant_content}"
        self.mock_config.GEMMA_CHAT_TEMPLATE = "<start_of_turn>{user_content}<end_of_turn>{assistant_content}"
        self.exporter = DataExporter(self.mock_db_manager, self.mock_config)

    def teardown_method(self):
        """Clean up after each test."""
        patch.stopall()

    def test_initialization(self):
        """Test that DataExporter initializes properly."""
        assert self.exporter is not None
        assert self.exporter.db_manager == self.mock_db_manager

    def test_export_method_invalid_template(self):
        """Test export method with invalid template."""
        # This should raise an exception or handle the invalid template
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with pytest.raises(ValueError):
                self.exporter.export_data("invalid-template", "output.jsonl")

    @patch("builtins.open", new_callable=mock_open)
    @patch("csv.writer")
    def test_export_csv_template(self, mock_csv_writer, mock_file):
        """Test export with CSV template."""
        # Mock the _get_all_conversations method to return test data
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value={
                    "user_content": "test input",
                    "assistant_content": "test output",
                },
            ):
                self.exporter.export_data("csv", "output.csv")

                # Verify the file was opened in write mode
                mock_file.assert_called_once_with("output.csv", "w", encoding="utf-8", newline="")

    @patch("builtins.open", new_callable=mock_open)
    def test_export_alpaca_jsonl_template(self, mock_file):
        """Test export with alpaca-jsonl template."""
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value={
                    "instruction": "test input",
                    "input": "",
                    "output": "test output",
                },
            ):
                self.exporter.export_data("alpaca-jsonl", "output.jsonl")

                # Verify the file was opened
                mock_file.assert_called_once_with("output.jsonl", "w", encoding="utf-8")

    @patch("builtins.open", new_callable=mock_open)
    def test_export_llama3_template(self, mock_file):
        """Test export with Llama3 template."""
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value="formatted llama3 content",
            ):
                self.exporter.export_data("llama3", "output.txt")

                # Verify the file was opened
                mock_file.assert_called_once_with("output.txt", "w", encoding="utf-8")

    @patch("builtins.open", new_callable=mock_open)
    def test_export_mistral_template(self, mock_file):
        """Test export with Mistral template."""
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value="formatted mistral content",
            ):
                self.exporter.export_data("mistral", "output.txt")

                # Verify the file was opened
                mock_file.assert_called_once_with("output.txt", "w", encoding="utf-8")

    @patch("builtins.open", new_callable=mock_open)
    def test_export_gemma_template(self, mock_file):
        """Test export with Gemma template."""
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value="formatted gemma content",
            ):
                self.exporter.export_data("gemma", "output.txt")

                # Verify the file was opened
                mock_file.assert_called_once_with("output.txt", "w", encoding="utf-8")

    @patch("builtins.open", new_callable=mock_open)
    def test_export_chatml_jsonl_template(self, mock_file):
        """Test export with ChatML JSONL template."""
        mock_conversation = {
            "sample_id": 1,
            "dataset_source": "test_source",
            "creation_date": "2023-01-01",
            "model_type_intended": "test",
            "sample_quality_score": 0.8,
            "is_multiturn": False,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content": "test input",
                    "is_label": False,
                    "metadata_json": None,
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content": "test output",
                    "is_label": True,
                    "metadata_json": None,
                },
            ],
        }

        with patch.object(self.exporter, "_get_all_conversations", return_value=[mock_conversation]):
            with patch.object(
                self.exporter,
                "_format_conversation_to_template",
                return_value={"messages": [{"role": "user", "content": "test input"}]},
            ):
                self.exporter.export_data("chatml-jsonl", "output.jsonl")

                # Verify the file was opened
                mock_file.assert_called_once_with("output.jsonl", "w", encoding="utf-8")
