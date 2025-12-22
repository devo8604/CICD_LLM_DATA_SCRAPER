"""Configuration editing screen for the TUI."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from src.core.config import AppConfig
from src.ui.tui_widgets import InputDialog, LogPanel


class ConfigScreen(ModalScreen[None]):
    """Configuration screen for editing settings."""

    BINDINGS = [
        ("escape", "close_screen", "Close"),
        ("q", "close_screen", "Close"),
        ("up", "cursor_up", "Move up"),
        ("down", "cursor_down", "Move down"),
        ("enter", "edit_value", "Edit value"),
        ("s", "save_config", "Save config"),
        ("r", "reset_config", "Reset config"),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.original_values = {}
        self.current_row_index = 0
        self.previous_row_index = -1
        self.editing_mode = False
        self.row_keys = {}

        # Define settings
        self.settings_list = [
            ("LLM Settings", None, None),
            ("llm.base_url", "Base URL", "text"),
            ("llm.model_name", "Model Name", "text"),
            ("llm.max_retries", "Max Retries", "integer"),
            ("llm.request_timeout", "Request Timeout", "integer"),
        ]

        if self.config.model.use_mlx:
            self.settings_list.extend(
                [
                    ("MLX Settings", None, None),
                    ("llm.mlx_model_name", "MLX Model Name", "text"),
                    ("llm.mlx_max_ram_gb", "MLX Max RAM (GB)", "integer"),
                    ("llm.mlx_quantize", "MLX Quantize", "boolean"),
                    ("llm.mlx_temperature", "MLX Temperature", "float"),
                ]
            )

        self.settings_list.extend(
            [
                ("Pipeline Settings", None, None),
                ("pipeline.base_dir", "Base Directory", "text"),
                ("pipeline.data_dir", "Data Directory", "text"),
                ("pipeline.repos_dir_name", "Repos Directory", "text"),
                ("pipeline.max_file_size", "Max File Size", "integer"),
                ("Logging Settings", None, None),
                ("logging.max_log_files", "Max Log Files", "integer"),
                ("logging.log_file_prefix", "Log File Prefix", "text"),
                ("Generation Settings", None, None),
                ("generation.default_max_tokens", "Default Max Tokens", "integer"),
                ("generation.default_temperature", "Default Temperature", "float"),
                ("Battery Settings", None, None),
                ("battery.low_threshold", "Low Threshold %", "integer"),
                ("battery.high_threshold", "High Threshold %", "integer"),
                ("battery.check_interval", "Check Interval (sec)", "integer"),
                ("State Settings", None, None),
                ("state.save_interval", "Save Interval", "integer"),
                ("Processing Settings", None, None),
                ("processing.max_concurrent_files", "Max Concurrent Files", "integer"),
                ("processing.file_batch_size", "File Batch Size", "integer"),
                ("Performance Settings", None, None),
                ("performance.file_hash_cache_size", "File Hash Cache Size", "integer"),
                ("performance.database_connection_pool_size", "DB Connection Pool Size", "integer"),
                ("performance.chunk_read_size", "Chunk Read Size", "integer"),
            ]
        )

        self.config_values = {}
        for item in self.settings_list:
            if item[1] is not None:
                key, _, value_type = item
                current_value = self._get_config_attr(key)
                self.config_values[key] = (current_value, value_type)
                self.original_values[key] = current_value

    def _get_config_attr(self, key: str):
        """Get config attribute."""
        attr_map = {
            "llm.base_url": "LLM_BASE_URL",
            "llm.model_name": "LLM_MODEL_NAME",
            "llm.max_retries": "LLM_MAX_RETRIES",
            "llm.request_timeout": "LLM_REQUEST_TIMEOUT",
            "llm.mlx_model_name": "MLX_MODEL_NAME",
            "llm.mlx_max_ram_gb": "MLX_MAX_RAM_GB",
            "llm.mlx_quantize": "MLX_QUANTIZE",
            "llm.mlx_temperature": "MLX_TEMPERATURE",
            "pipeline.base_dir": "BASE_DIR",
            "pipeline.data_dir": "DATA_DIR",
            "pipeline.repos_dir_name": "REPOS_DIR_NAME",
            "pipeline.max_file_size": "MAX_FILE_SIZE",
            "logging.max_log_files": "MAX_LOG_FILES",
            "logging.log_file_prefix": "LOG_FILE_PREFIX",
            "generation.default_max_tokens": "DEFAULT_MAX_TOKENS",
            "generation.default_temperature": "DEFAULT_TEMPERATURE",
            "battery.low_threshold": "BATTERY_LOW_THRESHOLD",
            "battery.high_threshold": "BATTERY_HIGH_THRESHOLD",
            "battery.check_interval": "BATTERY_CHECK_INTERVAL",
            "state.save_interval": "STATE_SAVE_INTERVAL",
            "processing.max_concurrent_files": "MAX_CONCURRENT_FILES",
            "processing.file_batch_size": "FILE_BATCH_SIZE",
            "performance.file_hash_cache_size": "FILE_HASH_CACHE_SIZE",
            "performance.database_connection_pool_size": "DATABASE_CONNECTION_POOL_SIZE",
            "performance.chunk_read_size": "CHUNK_READ_SIZE",
        }
        attr_name = attr_map.get(key)
        return getattr(self.config, attr_name, None) if attr_name else None

    def compose(self) -> ComposeResult:
        """Compose layout."""
        yield Static("Configuration Settings", classes="config-title")

        with ScrollableContainer(id="config-options-container", classes="config-options-container"):
            row_index = 0
            for item in self.settings_list:
                key, display_name, _ = item
                if display_name is None:
                    yield Label(key, classes="config-section-title")
                else:
                    try:
                        current_value = self._get_config_attr(key)
                        if current_value is None:
                            current_value = "N/A"
                        label_text = f"  {display_name}: {current_value}"
                        yield Label(label_text, id=f"row_{row_index}", classes="config-row")
                        self.row_keys[row_index] = key
                        row_index += 1
                    except Exception as e:
                        error_text = f"  {display_name}: ERROR ({str(e)})"
                        yield Label(error_text, id=f"row_{row_index}", classes="config-row")
                        row_index += 1

        with Horizontal(classes="config-buttons"):
            yield Static(
                "Press 'Enter' to edit values, 'S' to save, 'R' to reset, 'Q' to close",
                classes="config-status",
            )

    def on_mount(self) -> None:
        """Initialize row highlight."""
        self.highlight_current_row()
        self.can_focus = True
        self.focus()

    def has_unsaved_changes(self, key: str) -> bool:
        """Check for unsaved changes."""
        current_value = self._get_config_attr(key)
        original_value = self.original_values.get(key)
        return current_value != original_value

    def highlight_current_row(self):
        """Update row highlights."""
        if self.previous_row_index >= 0 and self.previous_row_index != self.current_row_index:
            try:
                prev_row = self.query_one(f"#row_{self.previous_row_index}", Label)
                prev_row.set_class(False, "config-row-selected")
                prev_row.set_class(True, "config-row")
            except Exception:
                pass

        try:
            current_row = self.query_one(f"#row_{self.current_row_index}", Label)
            current_row.set_class(False, "config-row")
            current_row.set_class(True, "config-row-selected")
            self.previous_row_index = self.current_row_index
        except Exception:
            pass

    def action_cursor_up(self):
        if not self.editing_mode and self.current_row_index > 0:
            self.current_row_index -= 1
            self.highlight_current_row()

    def action_cursor_down(self):
        if not self.editing_mode:
            max_index = len(self.row_keys) - 1
            if self.current_row_index < max_index:
                self.current_row_index += 1
                self.highlight_current_row()

    async def action_edit_value(self):
        key = self.row_keys.get(self.current_row_index)
        if not key:
            return

        current_value, value_type = self.config_values[key]
        display_name = self.get_display_name(key)

        if value_type == "boolean":
            new_value = not current_value
            self._update_config_value(key, new_value, value_type)
            self.update_display()
            return

        def handle_dialog_result(result: str | None):
            if result is None:
                return
            try:
                if value_type == "integer":
                    new_val = int(result)
                elif value_type == "float":
                    new_val = float(result)
                else:
                    new_val = result
                self._update_config_value(key, new_val, value_type)
                self.update_display()
            except ValueError:
                try:
                    self.app.query_one("#log-widget", LogPanel).log_message(
                        f"Invalid {value_type} value: {result}", "error"
                    )
                except Exception:
                    pass

        self.app.push_screen(InputDialog(display_name, str(current_value), value_type), handle_dialog_result)

    def _update_config_value(self, key: str, new_value, value_type: str):
        attr_map = {
            "llm.base_url": "LLM_BASE_URL",
            "llm.model_name": "LLM_MODEL_NAME",
            "llm.max_retries": "LLM_MAX_RETRIES",
            "llm.request_timeout": "LLM_REQUEST_TIMEOUT",
            "llm.mlx_model_name": "MLX_MODEL_NAME",
            "llm.mlx_max_ram_gb": "MLX_MAX_RAM_GB",
            "llm.mlx_quantize": "MLX_QUANTIZE",
            "llm.mlx_temperature": "MLX_TEMPERATURE",
            "pipeline.base_dir": "BASE_DIR",
            "pipeline.data_dir": "DATA_DIR",
            "pipeline.repos_dir_name": "REPOS_DIR_NAME",
            "pipeline.max_file_size": "MAX_FILE_SIZE",
            "logging.max_log_files": "MAX_LOG_FILES",
            "logging.log_file_prefix": "LOG_FILE_PREFIX",
            "generation.default_max_tokens": "DEFAULT_MAX_TOKENS",
            "generation.default_temperature": "DEFAULT_TEMPERATURE",
            "battery.low_threshold": "BATTERY_LOW_THRESHOLD",
            "battery.high_threshold": "BATTERY_HIGH_THRESHOLD",
            "battery.check_interval": "BATTERY_CHECK_INTERVAL",
            "state.save_interval": "STATE_SAVE_INTERVAL",
            "processing.max_concurrent_files": "MAX_CONCURRENT_FILES",
            "processing.file_batch_size": "FILE_BATCH_SIZE",
            "performance.file_hash_cache_size": "FILE_HASH_CACHE_SIZE",
            "performance.database_connection_pool_size": "DATABASE_CONNECTION_POOL_SIZE",
            "performance.chunk_read_size": "CHUNK_READ_SIZE",
        }
        attr_name = attr_map.get(key)
        if attr_name:
            setattr(self.config, attr_name, new_value)
        self.config_values[key] = (new_value, value_type)

    def update_display(self):
        for idx, key in self.row_keys.items():
            try:
                current_value = self._get_config_attr(key)
                asterisk = " *" if self.has_unsaved_changes(key) else ""
                label = self.query_one(f"#row_{idx}", Label)
                display_name = self.get_display_name(key)
                label.update(f"  {display_name}: {current_value}{asterisk}")
            except Exception:
                continue

    def get_display_name(self, key: str) -> str:
        for item in self.settings_list:
            if item[0] == key and item[1] is not None:
                return item[1]
        return key.split(".")[-1]

    def action_save_config(self):
        try:
            for key, (value, _) in self.config_values.items():
                self.config.config_loader.set(key, value)
            config_path = Path.cwd() / "cicdllm.yaml"
            self.config.config_loader.save(config_path)
            try:
                self.app.query_one("#log-widget", LogPanel).log_message("Configuration saved successfully", "success")
            except Exception:
                pass
            for key in self.config_values:
                self.original_values[key] = self.config_values[key][0]
            self.dismiss()
        except Exception as e:
            try:
                self.app.query_one("#log-widget", LogPanel).log_message(f"Error saving config: {e}", "error")
            except Exception:
                pass

    def action_reset_config(self) -> None:
        try:
            default_config = AppConfig()
            for key in self.config_values.keys():
                default_value = self._get_default_value_for_key(key, default_config)
                if default_value is not None:
                    self._update_config_value(key, default_value, self.config_values[key][1])
            self.update_display()
            try:
                self.app.query_one("#log-widget", LogPanel).log_message("Configuration reset to defaults", "info")
            except Exception:
                pass
        except Exception as e:
            try:
                self.app.query_one("#log-widget", LogPanel).log_message(f"Error resetting config: {e}", "error")
            except Exception:
                pass

    def _get_default_value_for_key(self, key: str, default_config: AppConfig):
        attr_map = {
            "llm.base_url": "LLM_BASE_URL",
            "llm.model_name": "LLM_MODEL_NAME",
            "llm.max_retries": "LLM_MAX_RETRIES",
            "llm.request_timeout": "LLM_REQUEST_TIMEOUT",
            "llm.mlx_model_name": "MLX_MODEL_NAME",
            "llm.mlx_max_ram_gb": "MLX_MAX_RAM_GB",
            "llm.mlx_quantize": "MLX_QUANTIZE",
            "llm.mlx_temperature": "MLX_TEMPERATURE",
            "pipeline.base_dir": "BASE_DIR",
            "pipeline.data_dir": "DATA_DIR",
            "pipeline.repos_dir_name": "REPOS_DIR_NAME",
            "pipeline.max_file_size": "MAX_FILE_SIZE",
            "logging.max_log_files": "MAX_LOG_FILES",
            "logging.log_file_prefix": "LOG_FILE_PREFIX",
            "generation.default_max_tokens": "DEFAULT_MAX_TOKENS",
            "generation.default_temperature": "DEFAULT_TEMPERATURE",
            "battery.low_threshold": "BATTERY_LOW_THRESHOLD",
            "battery.high_threshold": "BATTERY_HIGH_THRESHOLD",
            "battery.check_interval": "BATTERY_CHECK_INTERVAL",
            "state.save_interval": "STATE_SAVE_INTERVAL",
            "processing.max_concurrent_files": "MAX_CONCURRENT_FILES",
            "processing.file_batch_size": "FILE_BATCH_SIZE",
            "performance.file_hash_cache_size": "FILE_HASH_CACHE_SIZE",
            "performance.database_connection_pool_size": "DATABASE_CONNECTION_POOL_SIZE",
            "performance.chunk_read_size": "CHUNK_READ_SIZE",
        }
        attr_name = attr_map.get(key)
        return getattr(default_config, attr_name, None) if attr_name else None

    def action_close_screen(self) -> None:
        self.dismiss()
