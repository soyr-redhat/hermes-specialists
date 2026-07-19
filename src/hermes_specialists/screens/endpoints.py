from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static


class EndpointsScreen(Screen):
    """Configure vLLM endpoints (global + per-specialist)."""

    BINDINGS = [
        Binding("escape", "go_back", "back"),
        Binding("n", "new_endpoint", "new"),
        Binding("backspace", "delete_endpoint", "delete"),
    ]

    CSS = """
    #endpoints-container {
        padding: 1 2;
    }
    #section-title {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $primary;
        color: $text;
    }
    #endpoint-table {
        height: 1fr;
        margin-top: 1;
    }
    #endpoint-form {
        dock: bottom;
        height: auto;
        max-height: 14;
        padding: 1;
        background: $surface-darken-1;
        border-top: solid $primary;
    }
    .form-row {
        height: 3;
        margin-bottom: 1;
    }
    .form-label {
        width: 16;
        padding: 0 1;
    }
    .form-input {
        width: 1fr;
    }
    #form-buttons {
        height: 3;
        align: right middle;
    }
    #form-buttons Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="endpoints-container"):
            yield Static("vllm endpoints", id="section-title")
            yield DataTable(id="endpoint-table")
        with Container(id="endpoint-form"):
            with Horizontal(classes="form-row"):
                yield Label("name", classes="form-label")
                yield Input(placeholder="e.g. production", id="ep-name", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("base url", classes="form-label")
                yield Input(placeholder="http://localhost:8000/v1", id="ep-url", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("api key env", classes="form-label")
                yield Input(placeholder="VLLM_API_KEY (optional)", id="ep-key", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("model", classes="form-label")
                yield Input(placeholder="e.g. kimi-k3 (optional)", id="ep-model", classes="form-input")
            with Horizontal(id="form-buttons"):
                yield Button("save", variant="primary", id="btn-save")
                yield Button("cancel", variant="default", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#endpoint-table", DataTable)
        table.clear(columns=True)
        table.add_columns("name", "base url", "api key env", "model")
        table.cursor_type = "row"

        config = self.app.config
        table.add_row(
            config.default_endpoint.name,
            config.default_endpoint.base_url,
            config.default_endpoint.api_key_env or "(none)",
            config.default_endpoint.model or "(auto)",
            key="default",
        )
        for ep in config.endpoints:
            table.add_row(
                ep.name,
                ep.base_url,
                ep.api_key_env or "(none)",
                ep.model or "(auto)",
                key=ep.name,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._save_endpoint()
        elif event.button.id == "btn-cancel":
            self._clear_form()

    def _save_endpoint(self) -> None:
        from hermes_specialists.models import VLLMEndpoint

        name = self.query_one("#ep-name", Input).value.strip()
        url = self.query_one("#ep-url", Input).value.strip()
        if not name or not url:
            return

        endpoint = VLLMEndpoint(
            name=name,
            base_url=url,
            api_key_env=self.query_one("#ep-key", Input).value.strip(),
            model=self.query_one("#ep-model", Input).value.strip(),
        )

        config = self.app.config
        if name == "default":
            config.default_endpoint = endpoint
        else:
            config.endpoints = [ep for ep in config.endpoints if ep.name != name]
            config.endpoints.append(endpoint)

        config.save(self.app.config_path)
        self._clear_form()
        self._refresh_table()

    def _clear_form(self) -> None:
        self.query_one("#ep-name", Input).value = ""
        self.query_one("#ep-url", Input).value = ""
        self.query_one("#ep-key", Input).value = ""
        self.query_one("#ep-model", Input).value = ""

    def action_new_endpoint(self) -> None:
        self.query_one("#ep-name", Input).focus()

    def action_delete_endpoint(self) -> None:
        table = self.query_one("#endpoint-table", DataTable)
        if table.row_count > 0 and table.cursor_row is not None:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            name = str(row_key)
            if name == "default":
                return
            config = self.app.config
            config.endpoints = [ep for ep in config.endpoints if ep.name != name]
            config.save(self.app.config_path)
            self._refresh_table()

    def action_go_back(self) -> None:
        self.app.switch_screen("dashboard")
