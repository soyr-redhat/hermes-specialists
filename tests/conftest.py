from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@pytest.fixture
def sample_specialist() -> Specialist:
    return Specialist(
        name="test-bot",
        description="a test specialist",
        endpoint="default",
        model="kimi-k3",
    )


@pytest.fixture
def sample_config() -> GlobalConfig:
    return GlobalConfig(
        default_endpoint=VLLMEndpoint(
            name="default",
            base_url="http://localhost:8000/v1",
            model="kimi-k3",
        ),
        endpoints=[
            VLLMEndpoint(
                name="staging",
                base_url="http://staging:8000/v1",
                api_key="STAGING_KEY",
                model="llama-70b",
            ),
        ],
    )


@pytest.fixture
def specialists_dir(tmp_path: Path, sample_specialist: Specialist) -> Path:
    base = tmp_path / "specialists"
    base.mkdir()
    sample_specialist.save(base)
    prompt_file = base / sample_specialist.dir_name / "system-prompt.md"
    prompt_file.write_text("you are a test bot.\n")
    (base / sample_specialist.dir_name / "skills").mkdir()
    return base


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    dest = tmp_path / "templates"
    shutil.copytree(TEMPLATES_DIR, dest)
    return dest


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a full project directory and chdir into it."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "specialists").mkdir()
    shutil.copytree(TEMPLATES_DIR, project / "templates")
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def app(project_dir: Path):
    """Return a HermesSpecialistsApp instance rooted in the project_dir."""
    from hermes_specialists.app import HermesSpecialistsApp
    config = GlobalConfig()
    config.save(project_dir / "config.yaml")
    return HermesSpecialistsApp()
