from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from hermes_specialists.models import GlobalConfig
from hermes_specialists.screens.dashboard import DashboardScreen
from hermes_specialists.screens.deploy import DeployScreen
from hermes_specialists.screens.editor import EditorScreen
from hermes_specialists.screens.endpoints import EndpointsScreen

CONFIG_FILE = "config.yaml"


class HermesSpecialistsApp(App):
    """TUI for managing Hermes agent specialist configurations."""

    TITLE = "hermes specialists"
    SUB_TITLE = "manage specialist agent configs for openshift"
    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("d", "switch_screen('dashboard')", "dashboard"),
        Binding("e", "switch_screen('endpoints')", "endpoints"),
        Binding("q", "quit", "quit"),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "endpoints": EndpointsScreen,
        "editor": EditorScreen,
        "deploy": DeployScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.project_root = Path.cwd()
        self.config_path = self.project_root / CONFIG_FILE
        self.config = GlobalConfig.load(self.config_path)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen("dashboard")

    def action_switch_screen(self, screen_name: str) -> None:
        if self.screen.name != screen_name:
            self.switch_screen(screen_name)
