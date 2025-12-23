"""Screen for displaying failed files."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from src.data.db_manager import DBManager


class FailedFilesScreen(ModalScreen[None]):
    """Modal screen to display failed files and errors."""

    CSS = """
    FailedFilesScreen {
        align: center middle;
    }

    #failed-files-container {
        width: 90%;
        height: 80%;
        background: $nf-panel;
        border: solid $nf-accent;
        padding: 1;
    }

    #failed-files-title {
        text-align: center;
        color: $nf-accent;
        text-style: bold;
        margin-bottom: 1;
    }

    DataTable {
        height: 1fr;
        border: solid $nf-border;
        background: $nf-bg;
    }

    Button {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = db_path

    def compose(self) -> ComposeResult:
        with Vertical(id="failed-files-container"):
            yield Label("Failed Files Report", id="failed-files-title")
            yield DataTable(id="failed-files-table")
            yield Button("Close", variant="primary", id="close-btn")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("File Path", "Error Reason")
        self.load_failed_files()

    def load_failed_files(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        try:
            db_manager = DBManager(self.db_path)
            failed_files = db_manager.get_failed_files()
            db_manager.close_db()

            if not failed_files:
                table.add_row("No failed files found", "")
                return

            for file_path, reason in failed_files:
                table.add_row(file_path, reason)
        except Exception as e:
            table.add_row("Error loading failed files", str(e))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss()
