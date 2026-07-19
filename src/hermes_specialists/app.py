from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from InquirerPy.utils import InquirerPyStyle
from rich.console import Console

from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint

CONFIG_FILE = "config.yaml"
BACK = "__back__"

console = Console(highlight=False)

STYLE = InquirerPyStyle({
    "questionmark": "#ee0000",
    "answermark": "#ee0000",
    "answer": "#ffffff bold",
    "input": "#ffffff",
    "question": "#ffffff bold",
    "answered_question": "#808080",
    "instruction": "#808080",
    "long_instruction": "#808080",
    "pointer": "#ee0000 bold",
    "checkbox": "#ee0000",
    "separator": "#4a4a4a",
    "skipped": "#4a4a4a",
    "marker": "#ee0000",
    "fuzzy_prompt": "#ee0000",
    "fuzzy_info": "#808080",
    "fuzzy_border": "#4a4a4a",
    "fuzzy_match": "#ee0000 bold",
})

BANNER = """\033[31m
               -###########*.
            -###*====+====+####
          =####*=========+==+####
         ######==*#**========#####+
        ####***===============#####*
       ##======##*============*#####-
       ##*=======*####===========*###
      *####+==========+============##
      *######*=====================##
      -#####+   #================+###
       *    *      ##*+=======+#####*
                             *######
                       -.    ######
                            ##
                          *\033[0m

  \033[1mhermes specialists\033[0m
  \033[2menterprise & multi-tenant agent serving\033[0m
"""


def _sep() -> None:
    console.print(f"  [dim]{'─' * 40}[/dim]")


def _select(message: str, choices: list, back: bool = True) -> str | None:
    if back:
        choices = list(choices) + [Separator(), Choice(BACK, name="← back")]
    _sep()
    try:
        result = inquirer.select(
            message=message,
            choices=choices,
            pointer="›",
            qmark="▸",
            amark="▸",
            style=STYLE,
            mandatory=False,
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return None
    return None if result == BACK else result


def _fuzzy(message: str, choices: list) -> str | None:
    _sep()
    try:
        return inquirer.fuzzy(
            message=message,
            choices=choices,
            pointer="›",
            qmark="▸",
            amark="▸",
            style=STYLE,
            mandatory=False,
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return None


def _text(message: str, default: str = "") -> str | None:
    try:
        return inquirer.text(
            message=message,
            default=default,
            qmark="▸",
            amark="▸",
            style=STYLE,
            mandatory=False,
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return None


def _confirm(message: str, default: bool = False) -> bool:
    try:
        return inquirer.confirm(
            message=message,
            default=default,
            qmark="▸",
            amark="▸",
            style=STYLE,
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return False


class HermesSpecialistsApp:

    def __init__(self) -> None:
        self.project_root = Path.cwd()
        self.config_path = self.project_root / CONFIG_FILE
        self.config = GlobalConfig.load(self.config_path)
        self.specialists_dir = self.project_root / "specialists"

    def run(self) -> None:
        print(BANNER)
        self._status()

        while True:
            action = _select("what do you want to do?", [
                Choice("specialists", name="manage specialists"),
                Choice("skills", name="manage skills"),
                Choice("endpoints", name="configure vllm endpoints"),
                Choice("build", name="build & deploy containers"),
                Choice("config", name="view configuration"),
            ], back=False)

            if action is None:
                break

            {
                "specialists": self._specialists,
                "skills": self._skills,
                "endpoints": self._endpoints,
                "build": self._build,
                "config": self._show_config,
            }[action]()

    def _status(self) -> None:
        count = len(Specialist.discover(self.specialists_dir))
        ep = self.config.default_endpoint
        parts = [f"{count} specialist{'s' if count != 1 else ''}"]
        parts.append(f"endpoint: {ep.base_url}")
        if ep.model:
            parts.append(ep.model)
        console.print(f"  [dim]{'  ·  '.join(parts)}[/dim]\n")

    # ── specialists ──────────────────────────────────────────────────────

    def _specialists(self) -> None:
        while True:
            specialists = Specialist.discover(self.specialists_dir)
            if specialists:
                console.print()
                for s in specialists:
                    skills_dir = self.specialists_dir / s.dir_name / "skills"
                    skill_count = len(list(skills_dir.glob("*/SKILL.md"))) if skills_dir.exists() else 0
                    console.print(f"  [bold red]{s.name}[/bold red]  [dim]{s.description}[/dim]")
                    console.print(f"    [dim]endpoint: {s.endpoint}  ·  {skill_count} skill{'s' if skill_count != 1 else ''}[/dim]")
                console.print()

            action = _select("specialists", [
                Choice("new", name="create new"),
                Choice("edit", name="edit existing"),
                Choice("delete", name="remove"),
            ])
            if action is None:
                return
            {"new": self._new_specialist, "edit": self._edit_specialist, "delete": self._delete_specialist}[action]()

    def _new_specialist(self) -> None:
        console.print()
        name = _text("name")
        if not name:
            return
        name = name.strip().lower().replace(" ", "-")

        existing = [s.dir_name for s in Specialist.discover(self.specialists_dir)]
        if name in existing:
            console.print(f"  [red]specialist '{name}' already exists[/red]")
            return

        desc = _text("description") or ""
        endpoint = _text("endpoint", default="default") or "default"
        model = _text("model (optional)") or ""

        specialist = Specialist(
            name=name,
            description=desc.strip(),
            model=model.strip(),
            endpoint=endpoint.strip(),
        )
        specialist.save(self.specialists_dir)

        specialist_dir = self.specialists_dir / name
        (specialist_dir / "skills").mkdir(parents=True, exist_ok=True)

        prompt_file = specialist_dir / "system-prompt.md"
        if not prompt_file.exists():
            prompt_file.write_text(
                f"# {name}\n\n"
                f"you are a specialist agent for {desc or name}.\n",
                encoding="utf-8",
            )

        console.print(f"\n  [green]✓[/green] created [bold]{name}[/bold]")
        console.print(f"  [dim]system prompt:[/dim]  specialists/{name}/system-prompt.md")
        console.print(f"  [dim]custom skills:[/dim]  specialists/{name}/skills/\n")

    def _edit_specialist(self) -> None:
        name = self._pick_specialist("edit")
        if not name:
            return
        s = Specialist.load(self.specialists_dir / name)

        console.print()
        s.description = _text("description", default=s.description) or s.description
        s.endpoint = _text("endpoint", default=s.endpoint) or s.endpoint
        s.model = _text("model", default=s.model) or s.model

        s.save(self.specialists_dir)
        console.print(f"\n  [green]✓[/green] updated [bold]{s.name}[/bold]")
        console.print(f"  [dim]system prompt:[/dim]  specialists/{s.dir_name}/system-prompt.md\n")

    def _delete_specialist(self) -> None:
        name = self._pick_specialist("delete")
        if not name:
            return
        if _confirm(f"delete {name} and all its skills?"):
            shutil.rmtree(self.specialists_dir / name)
            console.print(f"  [green]✓[/green] deleted {name}")

    def _pick_specialist(self, action: str) -> str | None:
        specialists = Specialist.discover(self.specialists_dir)
        if not specialists:
            console.print("  [dim]no specialists yet[/dim]")
            return None
        choices = [Choice(s.dir_name, name=f"{s.name}  {s.description}") for s in specialists]
        return _fuzzy(f"{action} which?", choices)

    # ── skills ───────────────────────────────────────────────────────────

    def _skills(self) -> None:
        while True:
            action = _select("skills", [
                Choice("import", name="import a SKILL.md"),
                Choice("view", name="view skills"),
                Choice("chain", name="set up chaining"),
            ])
            if action is None:
                return
            {"import": self._import_skill, "view": self._view_skills, "chain": self._chain_skills}[action]()

    def _import_skill(self) -> None:
        specialist_name = self._pick_specialist("import skill to")
        if not specialist_name:
            return

        path = _text("path to SKILL.md")
        if not path:
            return
        p = Path(path.strip()).expanduser()
        if not p.exists():
            console.print(f"  [red]file not found: {path}[/red]")
            return
        content = p.read_text(encoding="utf-8")
        default_name = p.parent.name if p.name == "SKILL.md" else p.stem
        skill_name = _text("skill name", default=default_name)
        if not skill_name:
            return
        skill_name = skill_name.strip().lower().replace(" ", "-")

        skill_dir = self.specialists_dir / specialist_name / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        console.print(f"  [green]✓[/green] imported {skill_name}")

    def _view_skills(self) -> None:
        specialist_name = self._pick_specialist("view skills for")
        if not specialist_name:
            return
        skill_dirs = self._list_skill_dirs(specialist_name)
        if not skill_dirs:
            console.print(f"  [dim]no skills yet — add SKILL.md files to specialists/{specialist_name}/skills/[/dim]")
            return

        console.print()
        for skill_dir in skill_dirs:
            skill_file = skill_dir / "SKILL.md"
            content = skill_file.read_text(encoding="utf-8")
            desc = ""
            if content.startswith("---"):
                try:
                    end = content.index("\n---\n", 3)
                    fm = yaml.safe_load(content[3:end])
                    desc = fm.get("description", "")
                except (ValueError, yaml.YAMLError):
                    pass
            console.print(f"  [bold red]{skill_dir.name}[/bold red]  [dim]{desc}[/dim]")

        chain_file = self.specialists_dir / specialist_name / "chain.yaml"
        if chain_file.exists():
            chain = yaml.safe_load(chain_file.read_text()) or {}
            if chain.get("chain"):
                console.print(f"\n  [dim]chain:[/dim] {' → '.join(chain['chain'])}")
        console.print()

    def _chain_skills(self) -> None:
        specialist_name = self._pick_specialist("set up chaining for")
        if not specialist_name:
            return
        skill_dirs = self._list_skill_dirs(specialist_name)
        if not skill_dirs:
            console.print(f"  [dim]no skills to chain — add SKILL.md files to specialists/{specialist_name}/skills/ first[/dim]")
            return

        available = [d.name for d in skill_dirs]
        console.print()
        console.print("  [dim]available:[/dim] " + ", ".join(available))
        console.print("  [dim]enter skill names in execution order, comma-separated[/dim]")

        raw = _text("chain")
        if not raw:
            return

        chain = [s.strip() for s in raw.split(",") if s.strip()]
        invalid = [s for s in chain if s not in available]
        if invalid:
            console.print(f"  [red]unknown: {', '.join(invalid)}[/red]")
            return

        chain_file = self.specialists_dir / specialist_name / "chain.yaml"
        chain_file.write_text(yaml.dump({"chain": chain}, default_flow_style=False))
        console.print(f"\n  [green]✓[/green] chain: {' → '.join(chain)}\n")

    def _list_skill_dirs(self, specialist_name: str) -> list[Path]:
        skills_dir = self.specialists_dir / specialist_name / "skills"
        if not skills_dir.exists():
            return []
        return sorted(d for d in skills_dir.iterdir() if (d / "SKILL.md").exists())

    # ── endpoints ────────────────────────────────────────────────────────

    def _endpoints(self) -> None:
        while True:
            ep = self.config.default_endpoint
            console.print()
            console.print(f"  [bold red]{ep.name}[/bold red] [dim](default)[/dim]")
            console.print(f"    [dim]{ep.base_url}  ·  model: {ep.model or '(auto)'}[/dim]")
            for ep in self.config.endpoints:
                console.print(f"  [bold red]{ep.name}[/bold red]")
                console.print(f"    [dim]{ep.base_url}  ·  model: {ep.model or '(auto)'}[/dim]")
            console.print()

            action = _select("endpoints", [
                Choice("add", name="add new"),
                Choice("edit", name="edit default"),
                Choice("remove", name="remove"),
            ])
            if action is None:
                return
            {"add": self._endpoint_add, "edit": self._endpoint_edit, "remove": self._endpoint_rm}[action]()

    def _endpoint_add(self) -> None:
        name = _text("name")
        if not name:
            return
        url = _text("base url", default="http://localhost:8000/v1") or "http://localhost:8000/v1"
        key_env = _text("api key env var (optional)") or ""
        model = _text("model (optional)") or ""

        endpoint = VLLMEndpoint(name=name.strip(), base_url=url.strip(), api_key_env=key_env.strip(), model=model.strip())
        self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name.strip()]
        self.config.endpoints.append(endpoint)
        self.config.save(self.config_path)
        console.print(f"\n  [green]✓[/green] saved: {name.strip()}")

    def _endpoint_edit(self) -> None:
        ep = self.config.default_endpoint
        console.print()
        ep.base_url = (_text("base url", default=ep.base_url) or ep.base_url).strip()
        ep.api_key_env = (_text("api key env var", default=ep.api_key_env) or ep.api_key_env).strip()
        ep.model = (_text("model", default=ep.model) or ep.model).strip()
        self.config.default_endpoint = ep
        self.config.save(self.config_path)
        console.print(f"\n  [green]✓[/green] updated default endpoint")

    def _endpoint_rm(self) -> None:
        if not self.config.endpoints:
            console.print("  [dim]no extra endpoints to remove[/dim]")
            return
        choices = [Choice(ep.name, name=f"{ep.name}  {ep.base_url}") for ep in self.config.endpoints]
        name = _select("remove which?", choices)
        if name:
            self.config.endpoints = [ep for ep in self.config.endpoints if ep.name != name]
            self.config.save(self.config_path)
            console.print(f"  [green]✓[/green] removed: {name}")

    # ── build & deploy ───────────────────────────────────────────────────

    def _build(self) -> None:
        while True:
            action = _select("build & deploy", [
                Choice("one", name="build one specialist"),
                Choice("all", name="build all"),
                Choice("deploy", name="deploy to openshift"),
            ])
            if action is None:
                return
            if action == "one":
                self._build_one()
            elif action == "all":
                self._build_all()
            elif action == "deploy":
                self._deploy_one()

    def _build_one(self) -> None:
        name = self._pick_specialist("build")
        if not name:
            return
        from hermes_specialists.builder.container import build_image
        s = Specialist.load(self.specialists_dir / name)
        console.print(f"\n  building {s.name}...")
        ok = build_image(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
        console.print(f"  [green]✓[/green] built\n" if ok else f"  [red]✗ build failed[/red]\n")

    def _build_all(self) -> None:
        from hermes_specialists.builder.container import build_image
        specialists = Specialist.discover(self.specialists_dir)
        if not specialists:
            console.print("  [dim]no specialists to build[/dim]")
            return
        for s in specialists:
            console.print(f"\n  building {s.name}...")
            ok = build_image(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
            icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
            console.print(f"  {icon} {s.name}")
        console.print()

    def _deploy_one(self) -> None:
        name = self._pick_specialist("deploy")
        if not name:
            return
        from hermes_specialists.builder.deployer import deploy
        s = Specialist.load(self.specialists_dir / name)
        console.print(f"\n  deploying {s.name}...")
        ok = deploy(s, self.config, self.project_root, log_callback=lambda m: console.print(f"  {m}"))
        console.print(f"  [green]✓[/green] deployed\n" if ok else f"  [red]✗ deploy failed[/red]\n")

    # ── config ───────────────────────────────────────────────────────────

    def _show_config(self) -> None:
        count = len(Specialist.discover(self.specialists_dir))
        console.print()
        console.print(f"  [dim]specialists[/dim]  {count}")
        console.print(f"  [dim]config[/dim]       {self.config_path}")
        console.print(f"  [dim]registry[/dim]     {self.config.registry.url}")
        console.print(f"  [dim]base image[/dim]   {self.config.registry.base_image}")
        console.print(f"  [dim]endpoint[/dim]     {self.config.default_endpoint.display}")
        console.print()
