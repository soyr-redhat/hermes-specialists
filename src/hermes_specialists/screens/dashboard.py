from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from hermes_specialists.models import Specialist


class DashboardScreen(Screen):
    """Overview of all configured specialists."""

    BINDINGS = [
        Binding("n", "new_specialist", "new"),
        Binding("enter", "edit_specialist", "edit"),
        Binding("backspace", "delete_specialist", "delete"),
        Binding("b", "build_specialist", "build"),
    ]

    CSS = """
    #dashboard-container {
        padding: 1 2;
    }
    #title-bar {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $primary;
        color: $text;
    }
    #specialist-table {
        height: 1fr;
        margin-top: 1;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard-container"):
            yield Static("specialists", id="title-bar")
            yield DataTable(id="specialist-table")
            yield Label("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#specialist-table", DataTable)
        table.clear(columns=True)
        table.add_columns("name", "description", "model", "endpoint", "toolsets")
        table.cursor_type = "row"

        specialists_dir = Path.cwd() / "specialists"
        specialists = Specialist.discover(specialists_dir)

        for s in specialists:
            toolset_str = ", ".join(s.toolsets[:3])
            if len(s.toolsets) > 3:
                toolset_str += f" +{len(s.toolsets) - 3}"
            table.add_row(
                s.name,
                s.description[:40],
                s.model or "(default)",
                s.endpoint,
                toolset_str,
                key=s.dir_name,
            )

        status = self.query_one("#status-bar", Label)
        count = len(specialists)
        status.update(f"{count} specialist{'s' if count != 1 else ''} configured")

    def action_new_specialist(self) -> None:
        self.app.push_screen("editor")

    def action_edit_specialist(self) -> None:
        table = self.query_one("#specialist-table", DataTable)
        if table.row_count > 0 and table.cursor_row is not None:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            self.app.push_screen("editor")

    def action_delete_specialist(self) -> None:
        table = self.query_one("#specialist-table", DataTable)
        if table.row_count > 0 and table.cursor_row is not None:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            specialist_dir = Path.cwd() / "specialists" / str(row_key)
            if specialist_dir.exists():
                import shutil
                shutil.rmtree(specialist_dir)
            self._refresh_table()

    def action_build_specialist(self) -> None:
        self.app.push_screen("deploy")
