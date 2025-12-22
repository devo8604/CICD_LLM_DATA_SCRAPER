import logging

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.pipeline.exporters import DataExporter

tqdm_logger = logging.getLogger("tqdm_logger")


class ExportService:
    def __init__(self, db_manager: DBManager, config: AppConfig):
        if config is None:
            raise ValueError("Config must be provided")
        self.db_manager = db_manager
        self.config = config

    def export(self, template_name: str, output_file: str):
        tqdm_logger.info(f"Starting data export with template '{template_name}' to '{output_file}'...")
        exporter = DataExporter(self.db_manager, self.config)
        try:
            exporter.export_data(template_name, output_file)
        except Exception as e:
            tqdm_logger.error(f"An error occurred during data export: {e}", exc_info=True)
