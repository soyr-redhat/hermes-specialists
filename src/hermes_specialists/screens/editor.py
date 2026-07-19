from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TextArea,
)

from hermes_specialists.models.specialist import (
    BUILTIN_PERSONALITIES,
    DEFAULT_TOOLSETS,
    HERMES_TOOLSETS,
    Specialist,
)


class EditorScreen(Screen):
    """Create or edit a specialist configuration."""

    BINDINGS = [
        Binding("escape", "go_back", "back"),
    ]

    CSS = """
    #editor-container {
        padding: 1 2;
    }
    #editor-title {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $primary;
        color: $text;
    }
    #editor-form {
        padding: 1;
    }
    .form-section {
        margin-bottom: 1;
        padding: 1;
        border: solid $primary-background;
    }
    .section-header {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    .form-row {
        height: 3;
        margin-bottom: 1;
    }
    .form-label {
        width: 18;
        padding: 0 1;
    }
    .form-input {
        width: 1fr;
    }
    #toolset-grid {
        height: auto;
        padding: 0 1;
    }
    #toolset-grid Checkbox {
        width: 24;
        height: 3;
    }
    #system-prompt-area {
        height: 8;
    }
    #save-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        align: right middle;
        background: $surface-darken-1;
    }
    #save-bar Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="editor-container"):
            yield Static("new specialist", id="editor-title")
            with VerticalScroll(id="editor-form"):
                with Vertical(classes="form-section"):
                    yield Label("basics", classes="section-header")
                    with Horizontal(classes="form-row"):
                        yield Label("name", classes="form-label")
                        yield Input(placeholder="e.g. llm-compressor-expert", id="sp-name", classes="form-input")
                    with Horizontal(classes="form-row"):
                        yield Label("description", classes="form-label")
                        yield Input(placeholder="short description of this specialist", id="sp-desc", classes="form-input")
                    with Horizontal(classes="form-row"):
                        yield Label("endpoint", classes="form-label")
                        yield Input(placeholder="default", id="sp-endpoint", classes="form-input")
                    with Horizontal(classes="form-row"):
                        yield Label("model", classes="form-label")
                        yield Input(placeholder="model override (optional)", id="sp-model", classes="form-input")

                with Vertical(classes="form-section"):
                    yield Label("personality", classes="section-header")
                    with Horizontal(classes="form-row"):
                        yield Label("preset", classes="form-label")
                        yield Select(
                            [(name, name) for name in ["(custom)", *BUILTIN_PERSONALITIES.keys()]],
                            id="sp-personality",
                            classes="form-input",
                        )
                    yield Label("system prompt", classes="form-label")
                    yield TextArea(id="system-prompt-area")

                with Vertical(classes="form-section"):
                    yield Label("toolsets", classes="section-header")
                    with Horizontal(id="toolset-grid"):
                        for ts in HERMES_TOOLSETS:
                            yield Checkbox(ts, ts in DEFAULT_TOOLSETS, id=f"ts-{ts}")

                with Vertical(classes="form-section"):
                    yield Label("repos & context", classes="section-header")
                    with Horizontal(classes="form-row"):
                        yield Label("git repos", classes="form-label")
                        yield Input(placeholder="comma-separated repo urls to pre-clone", id="sp-repos", classes="form-input")
                    with Horizontal(classes="form-row"):
                        yield Label("context files", classes="form-label")
                        yield Input(placeholder="comma-separated file paths to include", id="sp-context", classes="form-input")

        with Horizontal(id="save-bar"):
            yield Button("save specialist", variant="primary", id="btn-save-specialist")
            yield Button("cancel", variant="default", id="btn-cancel-specialist")
        yield Footer()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sp-personality":
            name = str(event.value)
            if name in BUILTIN_PERSONALITIES:
                self.query_one("#system-prompt-area", TextArea).text = BUILTIN_PERSONALITIES[name]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-specialist":
            self._save()
        elif event.button.id == "btn-cancel-specialist":
            self.action_go_back()

    def _save(self) -> None:
        name = self.query_one("#sp-name", Input).value.strip()
        if not name:
            return

        toolsets = []
        for ts in HERMES_TOOLSETS:
            cb = self.query_one(f"#ts-{ts}", Checkbox)
            if cb.value:
                toolsets.append(ts)

        repos_raw = self.query_one("#sp-repos", Input).value.strip()
        repos = [r.strip() for r in repos_raw.split(",") if r.strip()] if repos_raw else []

        context_raw = self.query_one("#sp-context", Input).value.strip()
        context_files = [f.strip() for f in context_raw.split(",") if f.strip()] if context_raw else []

        specialist = Specialist(
            name=name,
            description=self.query_one("#sp-desc", Input).value.strip(),
            model=self.query_one("#sp-model", Input).value.strip(),
            endpoint=self.query_one("#sp-endpoint", Input).value.strip() or "default",
            system_prompt=self.query_one("#system-prompt-area", TextArea).text,
            toolsets=toolsets,
            repos=repos,
            context_files=context_files,
        )

        specialists_dir = Path.cwd() / "specialists"
        specialist.save(specialists_dir)
        self.action_go_back()

    def action_go_back(self) -> None:
        self.app.switch_screen("dashboard")
