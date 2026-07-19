from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

HERMES_TOOLSETS = [
    "web",
    "search",
    "terminal",
    "file",
    "browser",
    "vision",
    "image_gen",
    "skills",
    "skills_hub",
    "todo",
    "tts",
    "cronjob",
]

DEFAULT_TOOLSETS = ["terminal", "file", "web", "skills", "todo"]

BUILTIN_PERSONALITIES = {
    "helpful": "You are a helpful, friendly AI assistant.",
    "concise": "You are a concise assistant. Keep responses brief and to the point.",
    "technical": "You are a technical expert. Provide detailed, accurate technical information.",
}


class Specialist(BaseModel):
    """A single specialist agent configuration."""

    name: str
    description: str = ""
    model: str = ""
    endpoint: str = "default"
    personality: str = ""
    toolsets: list[str] = Field(default_factory=lambda: list(DEFAULT_TOOLSETS))
    skills: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)

    @property
    def dir_name(self) -> str:
        return self.name.lower().replace(" ", "-")

    def system_prompt(self, base_dir: Path) -> str:
        prompt_file = base_dir / self.dir_name / "system-prompt.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
        return ""

    def save(self, base_dir: Path) -> None:
        specialist_dir = base_dir / self.dir_name
        specialist_dir.mkdir(parents=True, exist_ok=True)
        config_path = specialist_dir / "specialist.yaml"
        config_path.write_text(
            yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)
        )

    @classmethod
    def load(cls, specialist_dir: Path) -> Specialist:
        config_path = specialist_dir / "specialist.yaml"
        data = yaml.safe_load(config_path.read_text())
        return cls.model_validate(data)

    @classmethod
    def discover(cls, base_dir: Path) -> list[Specialist]:
        specialists = []
        if not base_dir.exists():
            return specialists
        for child in sorted(base_dir.iterdir()):
            config = child / "specialist.yaml"
            if child.is_dir() and config.exists():
                specialists.append(cls.load(child))
        return specialists
