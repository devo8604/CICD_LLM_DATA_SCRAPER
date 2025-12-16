#!/usr/bin/env python3.14

import argparse
import logging
import os
import sys

from src.exporters import DataExporter


def main():
    parser = argparse.ArgumentParser(
        description="Export Q&A data from SQLite database to various formats."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.path.join("data", "pipeline.db"),
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--template",  # Changed from --format
        type=str,
        choices=[
            "llama3",
            "mistral",
            "gemma",
            "alpaca-jsonl",
            "chatml-jsonl",
        ],  # Updated choices
        required=True,
        help="Desired output template for fine-tuning data.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="Path to the output JSONL file.",
    )

    args = parser.parse_args()

    # Configure logging for export_data.py
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    exporter = DataExporter(args.db_path)
    try:
        exporter.export_data(args.template, args.output_file)
    except Exception as e:
        logging.error(f"An error occurred during data export: {e}")
    finally:
        exporter.close()  # Use the close method of DataExporter


if __name__ == "__main__":
    main()
