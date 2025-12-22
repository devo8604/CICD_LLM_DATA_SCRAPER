"""Command palette screen for the TUI."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static


class CommandPalette(ModalScreen[str]):
    """A searchable command palette for quick access to functionality."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("up", "cursor_up", "Move Up"),
        ("down", "cursor_down", "Move Down"),
        ("enter", "select_command", "Execute"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.all_commands = [
            ("Scrape Repositories", "Clone or update repos from repos.txt", "scrape"),
            ("Prepare Data", "Process files and generate Q&A pairs", "prepare"),
            ("Export Data", "Export processed data to JSONL", "export"),
            ("Open Configuration", "Edit application settings", "show_config"),
            ("Reload Prompts", "Reload system and user prompts from disk", "reload_prompts"),
            ("Refresh Dashboard", "Force update all stats and metrics", "refresh"),
            ("Toggle Dark Mode", "Switch between light and dark themes", "toggle_dark"),
            ("Force Quit", "Immediately terminate the application", "force_quit"),
            ("Graceful Quit", "Safely shutdown and exit", "quit"),
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="command-palette-container"):
            yield Label("Command Palette", id="palette-title")
            yield Input(placeholder="Search commands...", id="palette-input")
            yield ListView(id="palette-list")
            yield Static("Use arrow keys to navigate, Enter to select, ESC to close", id="palette-footer")

    def on_mount(self) -> None:
        self.update_list("")
        self.query_one("#palette-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_list(event.value)

    def update_list(self, search_text: str) -> None:
        list_view = self.query_one("#palette-list", ListView)
        list_view.clear()

        search_text = search_text.lower()
        for name, desc, action in self.all_commands:
            if not search_text or search_text in name.lower() or search_text in desc.lower():
                list_view.append(ListItem(Static(f"[bold]{name}[/bold]\n[dim]{desc}[/dim]"), id=f"cmd_{action}"))

    def action_select_command(self) -> None:
        list_view = self.query_one("#palette-list", ListView)
        if list_view.highlighted_child:
            action_id = list_view.highlighted_child.id.replace("cmd_", "")
            self.dismiss(action_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        action_id = event.item.id.replace("cmd_", "")
        self.dismiss(action_id)
