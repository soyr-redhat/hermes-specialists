from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.theme import Theme

from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint
from hermes_specialists.models.specialist import HERMES_TOOLSETS, DEFAULT_TOOLSETS, BUILTIN_PERSONALITIES

CONFIG_FILE = "config.yaml"

theme = Theme({
    "prompt": "bold cyan",
    "info": "dim white",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "header": "bold white",
    "muted": "dim",
})

console = Console(theme=theme)


class HermesSpecialistsApp:
    """Command-driven interface for managing Hermes specialist configs."""

    def __init__(self) -> None:
        self.project_root = Path.cwd()
        self.config_path = self.project_root / CONFIG_FILE
        self.config = GlobalConfig.load(self.config_path)
        self.specialists_dir = self.project_root / "specialists"
        self.running = True

    def run(self) -> None:
        self._banner()
        while self.running:
            try:
                raw = console.input("[prompt]>[/prompt] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if not raw:
                continue
            parts = raw.split()
            cmd, args = parts[0].lower(), parts[1:]
            self._dispatch(cmd, args)

    def _banner(self) -> None:
        console.print()
        console.print("[header]hermes specialists[/header] [muted]v0.1.0[/muted]")
        console.print("[muted]manage specialist agent configs for enterprise serving[/muted]")
        console.print("[muted]type [bold]help[/bold] to get started[/muted]")
        console.print()

    def _dispatch(self, cmd: str, args: list[str]) -> None:
        commands = {
            "help": self._help,
            "list": self._list,
            "ls": self._list,
            "new": self._new,
            "edit": self._edit,
            "delete": self._delete,
            "rm": self._delete,
            "show": self._show,
            "endpoints": self._endpoints,
            "build": self._build,
            "deploy": self._deploy,
            "config": self._show_config,
            "quit": self._quit,
            "exit": self._quit,
        }
        handler = commands.get(cmd)
        if handler:
            handler(args)
        else:
            console.print(f"[error]unknown command:[/error] {cmd}")
            console.print("[muted]type [bold]help[/bold] for available commands[/muted]")

    def _help(self, args: list[str]) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column(style="bold cyan", min_width=24)
        table.add_column(style="dim")
        table.add_row("list, ls", "show all specialists")
        table.add_row("new", "create a new specialist")
        table.add_row("show <name>", "show specialist details")
        table.add_row("edit <name>", "edit a specialist")
        table.add_row("delete, rm <name>", "remove a specialist")
        table.add_row("endpoints", "manage vllm endpoints")
        table.add_row("endpoints add", "add a new endpoint")
        table.add_row("endpoints rm <name>", "remove an endpoint")
        table.add_row("build <name|all>", "build container image")
        table.add_row("deploy <name>", "deploy to openshift")
        table.add_row("config", "show current config")
        table.add_row("quit, exit", "exit")
        console.print()
        console.print(table)
        console.print()

    def _list(self, args: list[str]) -> None:
        specialists = Specialist.discover(self.specialists_dir)
        if not specialists:
            console.print("[muted]no specialists configured yet. type [bold]new[/bold] to create one.[/muted]")
            return
        table = Table(box=None, padding=(0, 2, 0, 0), show_edge=False)
        table.add_column("name", style="bold cyan")
        table.add_column("description", style="dim")
        table.add_column("endpoint", style="dim")
        table.add_column("model", style="dim")
        for s in specialists:
            table.add_row(
                s.name,
                s.description[:50] or "-",
                s.endpoint,
                s.model or "(default)",
            )
        console.print()
        console.print(table)
        console.print(f"\n[muted]{len(specialists)} specialist{'s' if len(specialists) != 1 else ''}[/muted]")

    def _new(self, args: list[str]) -> None:
        console.print("\n[header]new specialist[/header]\n")

        name = Prompt.ask("[prompt]name[/prompt]", console=console).strip()
        if not name:
            console.print("[error]name is required[/error]")
            return
        name = name.lower().replace(" ", "-")

        desc = Prompt.ask("[prompt]description[/prompt]", default="", console=console).strip()
        endpoint = Prompt.ask("[prompt]endpoint[/prompt]", default="default", console=console).strip()
        model = Prompt.ask("[prompt]model[/prompt]", default="", console=console).strip()

        console.print(f"\n[muted]available toolsets: {', '.join(HERMES_TOOLSETS)}[/muted]")
        console.print(f"[muted]defaults: {', '.join(DEFAULT_TOOLSETS)}[/muted]")
        toolsets_raw = Prompt.ask(
            "[prompt]toolsets[/prompt]",
            default=", ".join(DEFAULT_TOOLSETS),
            console=console,
        ).strip()
        toolsets = [t.strip() for t in toolsets_raw.split(",") if t.strip()]

        console.print(f"\n[muted]personality presets: {', '.join(BUILTIN_PERSONALITIES.keys())}[/muted]")
        personality = Prompt.ask("[prompt]personality preset[/prompt]", default="(custom)", console=console).strip()

        if personality in BUILTIN_PERSONALITIES:
            system_prompt = BUILTIN_PERSONALITIES[personality]
            console.print(f"[muted]using preset: {personality}[/muted]")
        else:
            system_prompt = Prompt.ask("[prompt]system prompt[/prompt]", default="", console=console).strip()

        repos_raw = Prompt.ask("[prompt]git repos (comma-separated)[/prompt]", default="", console=console).strip()
        repos = [r.strip() for r in repos_raw.split(",") if r.strip()] if repos_raw else []

        context_raw = Prompt.ask("[prompt]context files (comma-separated)[/prompt]", default="", console=console).strip()
        context_files = [f.strip() for f in context_raw.split(",") if f.strip()] if context_raw else []

        specialist = Specialist(
            name=name,
            description=desc,
            model=model,
            endpoint=endpoint,
            system_prompt=system_prompt,
            toolsets=toolsets,
            repos=repos,
            context_files=context_files,
        )
        specialist.save(self.specialists_dir)
        console.print(f"\n[success]created specialist: {name}[/success]")

    def _show(self, args: list[str]) -> None:
        if not args:
            console.print("[error]usage: show <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"[error]specialist not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print()
        console.print(f"[header]{s.name}[/header]")
        console.print(f"[muted]description:[/muted]  {s.description or '-'}")
        console.print(f"[muted]endpoint:[/muted]     {s.endpoint}")
        console.print(f"[muted]model:[/muted]        {s.model or '(default)'}")
        console.print(f"[muted]toolsets:[/muted]     {', '.join(s.toolsets)}")
        if s.system_prompt:
            console.print(f"[muted]system prompt:[/muted] {s.system_prompt[:80]}{'...' if len(s.system_prompt) > 80 else ''}")
        if s.repos:
            console.print(f"[muted]repos:[/muted]        {', '.join(s.repos)}")
        if s.context_files:
            console.print(f"[muted]context:[/muted]      {', '.join(s.context_files)}")
        console.print()

    def _edit(self, args: list[str]) -> None:
        if not args:
            console.print("[error]usage: edit <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"[error]specialist not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print(f"\n[header]editing {s.name}[/header]")
        console.print("[muted]press enter to keep current value[/muted]\n")

        s.description = Prompt.ask("[prompt]description[/prompt]", default=s.description, console=console).strip()
        s.endpoint = Prompt.ask("[prompt]endpoint[/prompt]", default=s.endpoint, console=console).strip()
        s.model = Prompt.ask("[prompt]model[/prompt]", default=s.model, console=console).strip()

        toolsets_raw = Prompt.ask(
            "[prompt]toolsets[/prompt]",
            default=", ".join(s.toolsets),
            console=console,
        ).strip()
        s.toolsets = [t.strip() for t in toolsets_raw.split(",") if t.strip()]

        s.system_prompt = Prompt.ask(
            "[prompt]system prompt[/prompt]",
            default=s.system_prompt,
            console=console,
        ).strip()

        s.save(self.specialists_dir)
        console.print(f"\n[success]updated: {s.name}[/success]")

    def _delete(self, args: list[str]) -> None:
        if not args:
            console.print("[error]usage: delete <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not specialist_dir.exists():
            console.print(f"[error]specialist not found: {name}[/error]")
            return
        if Confirm.ask(f"[warning]delete {name}?[/warning]", console=console):
            shutil.rmtree(specialist_dir)
            console.print(f"[success]deleted: {name}[/success]")

    def _endpoints(self, args: list[str]) -> None:
        if args and args[0] == "add":
            self._endpoints_add()
            return
        if args and args[0] == "rm" and len(args) > 1:
            self._endpoints_rm(args[1])
            return

        table = Table(box=None, padding=(0, 2, 0, 0), show_edge=False)
        table.add_column("name", style="bold cyan")
        table.add_column("base url", style="dim")
        table.add_column("api key env", style="dim")
        table.add_column("model", style="dim")

        ep = self.config.default_endpoint
        table.add_row(ep.name, ep.base_url, ep.api_key_env or "-", ep.model or "(auto)")
        for ep in self.config.endpoints:
            table.add_row(ep.name, ep.base_url, ep.api_key_env or "-", ep.model or "(auto)")

        console.print()
        console.print(table)
        console.print(f"\n[muted]use [bold]endpoints add[/bold] or [bold]endpoints rm <name>[/bold][/muted]")

    def _endpoints_add(self) -> None:
        console.print("\n[header]add endpoint[/header]\n")
        name = Prompt.ask("[prompt]name[/prompt]", console=console).strip()
        if not name:
            return
        url = Prompt.ask("[prompt]base url[/prompt]", default="http://localhost:8000/v1", console=console).strip()
        key_env = Prompt.ask("[prompt]api key env var[/prompt]", default="", console=console).strip()
        model = Prompt.ask("[prompt]model[/prompt]", default="", console=console).strip()

        endpoint = VLLMEndpoint(name=name, base_url=url, api_key_env=key_env, model=model)
        if name == "default":
            self.config.default_endpoint = endpoint
        else:
            self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name]
            self.config.endpoints.append(endpoint)

        self.config.save(self.config_path)
        console.print(f"\n[success]saved endpoint: {name}[/success]")

    def _endpoints_rm(self, name: str) -> None:
        if name == "default":
            console.print("[error]can't remove the default endpoint[/error]")
            return
        self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name]
        self.config.save(self.config_path)
        console.print(f"[success]removed endpoint: {name}[/success]")

    def _build(self, args: list[str]) -> None:
        if not args:
            console.print("[error]usage: build <name|all>[/error]")
            return

        from hermes_specialists.builder.container import build_image

        if args[0] == "all":
            specialists = Specialist.discover(self.specialists_dir)
            if not specialists:
                console.print("[muted]no specialists to build[/muted]")
                return
            for s in specialists:
                console.print(f"\n[header]building {s.name}...[/header]")
                ok = build_image(s, self.config, self.project_root, log_callback=console.print)
                if ok:
                    console.print(f"[success]built: {s.name}[/success]")
                else:
                    console.print(f"[error]failed: {s.name}[/error]")
        else:
            name = args[0]
            specialist_dir = self.specialists_dir / name
            if not (specialist_dir / "specialist.yaml").exists():
                console.print(f"[error]specialist not found: {name}[/error]")
                return
            s = Specialist.load(specialist_dir)
            console.print(f"\n[header]building {s.name}...[/header]")
            ok = build_image(s, self.config, self.project_root, log_callback=console.print)
            if ok:
                console.print(f"[success]built: {s.name}[/success]")
            else:
                console.print(f"[error]failed: {s.name}[/error]")

    def _deploy(self, args: list[str]) -> None:
        if not args:
            console.print("[error]usage: deploy <name>[/error]")
            return

        from hermes_specialists.builder.deployer import deploy

        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"[error]specialist not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print(f"\n[header]deploying {s.name}...[/header]")
        ok = deploy(s, self.config, self.project_root, log_callback=console.print)
        if ok:
            console.print(f"[success]deployed: {s.name}[/success]")
        else:
            console.print(f"[error]deploy failed: {s.name}[/error]")

    def _show_config(self, args: list[str]) -> None:
        console.print(f"\n[muted]config file:[/muted]      {self.config_path}")
        console.print(f"[muted]specialists dir:[/muted]  {self.specialists_dir}")
        console.print(f"[muted]registry:[/muted]         {self.config.registry.url}")
        console.print(f"[muted]base image:[/muted]       {self.config.registry.base_image}")
        console.print(f"[muted]default endpoint:[/muted] {self.config.default_endpoint.display}")
        console.print()

    def _quit(self, args: list[str]) -> None:
        self.running = False
