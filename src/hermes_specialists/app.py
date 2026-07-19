from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
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
    "accent": "cyan",
    "bar": "dim cyan",
})

console = Console(theme=theme)

LOGO = """[accent]
 ╦ ╦╔═╗╦═╗╔╦╗╔═╗╔═╗
 ╠═╣║╣ ╠╦╝║║║║╣ ╚═╗
 ╩ ╩╚═╝╩╚═╩ ╩╚═╝╚═╝[/accent] [muted]specialists[/muted]"""


class HermesSpecialistsApp:
    """Command-driven interface for managing Hermes specialist configs."""

    def __init__(self) -> None:
        self.project_root = Path.cwd()
        self.config_path = self.project_root / CONFIG_FILE
        self.config = GlobalConfig.load(self.config_path)
        self.specialists_dir = self.project_root / "specialists"
        self.running = True

    def _specialist_count(self) -> int:
        return len(Specialist.discover(self.specialists_dir))

    def _prompt_str(self) -> str:
        count = self._specialist_count()
        ep = self.config.default_endpoint.name
        parts = [f"[bar]│[/bar]"]
        if count:
            parts.append(f"[muted]{count} specialist{'s' if count != 1 else ''}[/muted]")
            parts.append("[bar]·[/bar]")
        parts.append(f"[muted]{ep}[/muted]")
        status = " ".join(parts)
        return f"{status}\n[bar]╰─[/bar][prompt]>[/prompt] "

    def run(self) -> None:
        self._banner()
        while self.running:
            try:
                raw = console.input(self._prompt_str()).strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if not raw:
                continue
            parts = raw.split()
            cmd, args = parts[0].lower(), parts[1:]
            self._dispatch(cmd, args)

    def _banner(self) -> None:
        width = min(console.width, 56)
        console.print()
        console.print(LOGO)
        console.print()
        console.print(Panel.fit(
            "[muted]enterprise & multi-tenant agent serving\n"
            "configure, build, and deploy specialist hermes agents[/muted]",
            border_style="dim cyan",
            padding=(0, 2),
        ))
        console.print()
        console.print("[muted]  type [bold cyan]help[/bold cyan] to get started  "
                       "[bar]·[/bar]  [bold cyan]quit[/bold cyan] to exit[/muted]")
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
            "clear": self._clear,
        }
        handler = commands.get(cmd)
        if handler:
            handler(args)
        else:
            console.print(f"  [error]unknown:[/error] {cmd} [muted]— type [bold]help[/bold] for commands[/muted]")

    def _help(self, args: list[str]) -> None:
        console.print()
        console.print("  [header]specialists[/header]")
        help_section([
            ("list, ls", "show all specialists"),
            ("new", "create a new specialist"),
            ("show [accent]<name>[/accent]", "view specialist details"),
            ("edit [accent]<name>[/accent]", "modify a specialist"),
            ("delete [accent]<name>[/accent]", "remove a specialist"),
        ])
        console.print("  [header]infrastructure[/header]")
        help_section([
            ("endpoints", "list vllm endpoints"),
            ("endpoints add", "add a new endpoint"),
            ("endpoints rm [accent]<name>[/accent]", "remove an endpoint"),
            ("build [accent]<name|all>[/accent]", "build container image"),
            ("deploy [accent]<name>[/accent]", "deploy to openshift"),
        ])
        console.print("  [header]general[/header]")
        help_section([
            ("config", "show current configuration"),
            ("clear", "clear the screen"),
            ("quit, exit", "exit hermes specialists"),
        ])

    def _list(self, args: list[str]) -> None:
        specialists = Specialist.discover(self.specialists_dir)
        if not specialists:
            console.print("  [muted]no specialists yet — type [bold]new[/bold] to create one[/muted]")
            return
        console.print()
        for s in specialists:
            toolset_preview = ", ".join(s.toolsets[:4])
            if len(s.toolsets) > 4:
                toolset_preview += f" +{len(s.toolsets) - 4}"
            console.print(f"  [bold cyan]{s.name}[/bold cyan]")
            if s.description:
                console.print(f"    [muted]{s.description}[/muted]")
            console.print(f"    [muted]endpoint:[/muted] {s.endpoint}  "
                          f"[muted]model:[/muted] {s.model or '(default)'}  "
                          f"[muted]tools:[/muted] {toolset_preview}")
            console.print()

    def _new(self, args: list[str]) -> None:
        console.print()
        console.print(Rule("[header]new specialist[/header]", style="dim cyan"))
        console.print()

        name = Prompt.ask("  [prompt]name[/prompt]", console=console).strip()
        if not name:
            console.print("  [error]name is required[/error]")
            return
        name = name.lower().replace(" ", "-")

        desc = Prompt.ask("  [prompt]description[/prompt]", default="", console=console).strip()
        endpoint = Prompt.ask("  [prompt]endpoint[/prompt]", default="default", console=console).strip()
        model = Prompt.ask("  [prompt]model[/prompt]", default="", console=console).strip()

        console.print()
        console.print(f"  [muted]available: {', '.join(HERMES_TOOLSETS)}[/muted]")
        toolsets_raw = Prompt.ask(
            "  [prompt]toolsets[/prompt]",
            default=", ".join(DEFAULT_TOOLSETS),
            console=console,
        ).strip()
        toolsets = [t.strip() for t in toolsets_raw.split(",") if t.strip()]

        console.print()
        console.print(f"  [muted]presets: {', '.join(BUILTIN_PERSONALITIES.keys())}[/muted]")
        personality = Prompt.ask("  [prompt]personality[/prompt]", default="(custom)", console=console).strip()

        if personality in BUILTIN_PERSONALITIES:
            system_prompt = BUILTIN_PERSONALITIES[personality]
            console.print(f"  [muted]→ using preset: {personality}[/muted]")
        else:
            system_prompt = Prompt.ask("  [prompt]system prompt[/prompt]", default="", console=console).strip()

        repos_raw = Prompt.ask("  [prompt]git repos[/prompt]", default="", console=console).strip()
        repos = [r.strip() for r in repos_raw.split(",") if r.strip()] if repos_raw else []

        context_raw = Prompt.ask("  [prompt]context files[/prompt]", default="", console=console).strip()
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
        console.print()
        console.print(f"  [success]✓ created {name}[/success]")
        console.print()

    def _show(self, args: list[str]) -> None:
        if not args:
            console.print("  [error]usage: show <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"  [error]not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print()
        console.print(f"  [bold cyan]{s.name}[/bold cyan]")
        console.print(f"  [muted]{'─' * 40}[/muted]")
        console.print(f"  [muted]description  [/muted] {s.description or '-'}")
        console.print(f"  [muted]endpoint     [/muted] {s.endpoint}")
        console.print(f"  [muted]model        [/muted] {s.model or '(default)'}")
        console.print(f"  [muted]toolsets     [/muted] {', '.join(s.toolsets)}")
        if s.system_prompt:
            preview = s.system_prompt[:80].replace('\n', ' ')
            console.print(f"  [muted]system prompt [/muted] {preview}{'...' if len(s.system_prompt) > 80 else ''}")
        if s.repos:
            console.print(f"  [muted]repos        [/muted] {', '.join(s.repos)}")
        if s.context_files:
            console.print(f"  [muted]context      [/muted] {', '.join(s.context_files)}")
        console.print()

    def _edit(self, args: list[str]) -> None:
        if not args:
            console.print("  [error]usage: edit <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"  [error]not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print()
        console.print(Rule(f"[header]editing {s.name}[/header]", style="dim cyan"))
        console.print("  [muted]enter to keep current value[/muted]\n")

        s.description = Prompt.ask("  [prompt]description[/prompt]", default=s.description, console=console).strip()
        s.endpoint = Prompt.ask("  [prompt]endpoint[/prompt]", default=s.endpoint, console=console).strip()
        s.model = Prompt.ask("  [prompt]model[/prompt]", default=s.model, console=console).strip()

        toolsets_raw = Prompt.ask(
            "  [prompt]toolsets[/prompt]",
            default=", ".join(s.toolsets),
            console=console,
        ).strip()
        s.toolsets = [t.strip() for t in toolsets_raw.split(",") if t.strip()]

        s.system_prompt = Prompt.ask(
            "  [prompt]system prompt[/prompt]",
            default=s.system_prompt,
            console=console,
        ).strip()

        s.save(self.specialists_dir)
        console.print(f"\n  [success]✓ updated {s.name}[/success]\n")

    def _delete(self, args: list[str]) -> None:
        if not args:
            console.print("  [error]usage: delete <name>[/error]")
            return
        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not specialist_dir.exists():
            console.print(f"  [error]not found: {name}[/error]")
            return
        if Confirm.ask(f"  [warning]delete {name}?[/warning]", console=console):
            shutil.rmtree(specialist_dir)
            console.print(f"  [success]✓ deleted {name}[/success]")

    def _endpoints(self, args: list[str]) -> None:
        if args and args[0] == "add":
            self._endpoints_add()
            return
        if args and args[0] == "rm" and len(args) > 1:
            self._endpoints_rm(args[1])
            return

        console.print()
        ep = self.config.default_endpoint
        console.print(f"  [bold cyan]{ep.name}[/bold cyan] [muted](default)[/muted]")
        console.print(f"    [muted]{ep.base_url}[/muted]  "
                       f"[muted]model:[/muted] {ep.model or '(auto)'}  "
                       f"[muted]key:[/muted] {ep.api_key_env or '-'}")
        for ep in self.config.endpoints:
            console.print()
            console.print(f"  [bold cyan]{ep.name}[/bold cyan]")
            console.print(f"    [muted]{ep.base_url}[/muted]  "
                           f"[muted]model:[/muted] {ep.model or '(auto)'}  "
                           f"[muted]key:[/muted] {ep.api_key_env or '-'}")
        console.print()
        console.print("  [muted][bold]endpoints add[/bold] · [bold]endpoints rm <name>[/bold][/muted]\n")

    def _endpoints_add(self) -> None:
        console.print()
        console.print(Rule("[header]add endpoint[/header]", style="dim cyan"))
        console.print()
        name = Prompt.ask("  [prompt]name[/prompt]", console=console).strip()
        if not name:
            return
        url = Prompt.ask("  [prompt]base url[/prompt]", default="http://localhost:8000/v1", console=console).strip()
        key_env = Prompt.ask("  [prompt]api key env var[/prompt]", default="", console=console).strip()
        model = Prompt.ask("  [prompt]model[/prompt]", default="", console=console).strip()

        endpoint = VLLMEndpoint(name=name, base_url=url, api_key_env=key_env, model=model)
        if name == "default":
            self.config.default_endpoint = endpoint
        else:
            self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name]
            self.config.endpoints.append(endpoint)

        self.config.save(self.config_path)
        console.print(f"\n  [success]✓ saved endpoint: {name}[/success]\n")

    def _endpoints_rm(self, name: str) -> None:
        if name == "default":
            console.print("  [error]can't remove the default endpoint[/error]")
            return
        self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name]
        self.config.save(self.config_path)
        console.print(f"  [success]✓ removed: {name}[/success]")

    def _build(self, args: list[str]) -> None:
        if not args:
            console.print("  [error]usage: build <name|all>[/error]")
            return

        from hermes_specialists.builder.container import build_image

        if args[0] == "all":
            specialists = Specialist.discover(self.specialists_dir)
            if not specialists:
                console.print("  [muted]no specialists to build[/muted]")
                return
            for s in specialists:
                console.print(f"\n  [header]building {s.name}...[/header]")
                ok = build_image(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
                status = "[success]✓[/success]" if ok else "[error]✗[/error]"
                console.print(f"  {status} {s.name}")
        else:
            name = args[0]
            specialist_dir = self.specialists_dir / name
            if not (specialist_dir / "specialist.yaml").exists():
                console.print(f"  [error]not found: {name}[/error]")
                return
            s = Specialist.load(specialist_dir)
            console.print(f"\n  [header]building {s.name}...[/header]")
            ok = build_image(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
            status = "[success]✓ built[/success]" if ok else "[error]✗ failed[/error]"
            console.print(f"  {status} {s.name}\n")

    def _deploy(self, args: list[str]) -> None:
        if not args:
            console.print("  [error]usage: deploy <name>[/error]")
            return

        from hermes_specialists.builder.deployer import deploy

        name = args[0]
        specialist_dir = self.specialists_dir / name
        if not (specialist_dir / "specialist.yaml").exists():
            console.print(f"  [error]not found: {name}[/error]")
            return
        s = Specialist.load(specialist_dir)
        console.print(f"\n  [header]deploying {s.name}...[/header]")
        ok = deploy(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
        status = "[success]✓ deployed[/success]" if ok else "[error]✗ deploy failed[/error]"
        console.print(f"  {status} {s.name}\n")

    def _show_config(self, args: list[str]) -> None:
        console.print()
        console.print(f"  [muted]config file    [/muted] {self.config_path}")
        console.print(f"  [muted]specialists    [/muted] {self.specialists_dir}")
        console.print(f"  [muted]registry       [/muted] {self.config.registry.url}")
        console.print(f"  [muted]base image     [/muted] {self.config.registry.base_image}")
        console.print(f"  [muted]endpoint       [/muted] {self.config.default_endpoint.display}")
        console.print()

    def _clear(self, args: list[str]) -> None:
        os.system("cls" if os.name == "nt" else "clear")
        self._banner()

    def _quit(self, args: list[str]) -> None:
        self.running = False


def help_section(rows: list[tuple[str, str]]) -> None:
    for cmd, desc in rows:
        console.print(f"    {cmd:<36} [muted]{desc}[/muted]")
    console.print()
