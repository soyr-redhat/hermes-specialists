from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, RichLog, Static

from hermes_specialists.models import Specialist


class DeployScreen(Screen):
    """Build container images and deploy to OpenShift."""

    BINDINGS = [
        Binding("escape", "go_back", "back"),
        Binding("b", "build_selected", "build"),
        Binding("a", "build_all", "build all"),
        Binding("p", "deploy_selected", "deploy"),
    ]

    CSS = """
    #deploy-container {
        padding: 1 2;
    }
    #deploy-title {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $primary;
        color: $text;
    }
    #deploy-table {
        height: 40%;
        margin-top: 1;
    }
    #log-panel {
        height: 1fr;
        margin-top: 1;
        border: solid $primary-background;
        padding: 1;
    }
    #action-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        align: center middle;
        background: $surface-darken-1;
    }
    #action-bar Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="deploy-container"):
            yield Static("build & deploy", id="deploy-title")
            yield DataTable(id="deploy-table")
            yield RichLog(id="log-panel", highlight=True, markup=True)
        with Horizontal(id="action-bar"):
            yield Button("build selected", variant="primary", id="btn-build")
            yield Button("build all", variant="warning", id="btn-build-all")
            yield Button("deploy selected", variant="success", id="btn-deploy")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#deploy-table", DataTable)
        table.clear(columns=True)
        table.add_columns("specialist", "image", "status")
        table.cursor_type = "row"

        specialists_dir = Path.cwd() / "specialists"
        registry = self.app.config.registry.url

        for s in Specialist.discover(specialists_dir):
            image = f"{registry}/{s.dir_name}:latest"
            table.add_row(s.name, image, "not built", key=s.dir_name)

    def _log(self, msg: str) -> None:
        self.query_one("#log-panel", RichLog).write(msg)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-build":
            self.action_build_selected()
        elif event.button.id == "btn-build-all":
            self.action_build_all()
        elif event.button.id == "btn-deploy":
            self.action_deploy_selected()

    def action_build_selected(self) -> None:
        table = self.query_one("#deploy-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        name = str(row_key)
        self._log(f"[bold]building {name}...[/bold]")
        self._log("(container build not yet implemented)")

    def action_build_all(self) -> None:
        specialists_dir = Path.cwd() / "specialists"
        specialists = Specialist.discover(specialists_dir)
        if not specialists:
            self._log("[yellow]no specialists to build[/yellow]")
            return
        for s in specialists:
            self._log(f"[bold]building {s.name}...[/bold]")
        self._log("(container build not yet implemented)")

    def action_deploy_selected(self) -> None:
        table = self.query_one("#deploy-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        name = str(row_key)
        self._log(f"[bold]deploying {name}...[/bold]")
        self._log("(deployment not yet implemented)")

    def action_go_back(self) -> None:
        self.app.switch_screen("dashboard")
