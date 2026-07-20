"""Containerfile generation and image building."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from hermes_specialists.models import GlobalConfig, Specialist


def _run_streaming(cmd, log_callback=None, cwd=None, timeout=600):
    """Run a command, streaming output line-by-line to log_callback."""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line and log_callback:
                log_callback(f"[dim]{line}[/dim]")
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    return proc.returncode == 0


def generate_config(specialist: Specialist, config: GlobalConfig) -> dict:
    """Generate a Hermes config.yaml for a specialist."""
    endpoint = config.get_endpoint(specialist.endpoint) or config.default_endpoint
    model = specialist.model or endpoint.model or ""

    hermes_config: dict = {
        "model": {
            "default": model,
            "provider": "custom",
            "base_url": endpoint.base_url,
        },
        "_config_version": 33,
        "custom_providers": [
            {
                "name": endpoint.name,
                "base_url": endpoint.base_url,
                "model": model,
            },
        ],
        "onboarding": {
            "seen": {
                "busy_input_prompt": True,
            },
        },
    }

    if endpoint.api_key:
        hermes_config["model"]["api_key"] = endpoint.api_key
        hermes_config["custom_providers"][0]["api_key"] = endpoint.api_key

    return hermes_config


def generate_containerfile(
    specialist: Specialist, config: GlobalConfig, templates_dir: Path, specialists_dir: Path,
) -> str:
    """Render a Containerfile from the template for a specialist."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("Containerfile.template")

    return template.render(
        base_image=config.registry.base_image,
        specialist_name=specialist.dir_name,
        skills=specialist.has_skills(specialists_dir),
        context_files=specialist.has_context(specialists_dir),
    )


def prepare_build_context(specialist: Specialist, config: GlobalConfig, output_dir: Path) -> Path:
    """Prepare a build context directory for a specialist."""
    build_dir = output_dir / specialist.dir_name
    build_dir.mkdir(parents=True, exist_ok=True)

    specialists_dir = output_dir.parent / "specialists"

    hermes_config = generate_config(specialist, config)
    (build_dir / "config.yaml").write_text(
        yaml.dump(hermes_config, default_flow_style=False, sort_keys=False)
    )

    system_prompt = specialist.system_prompt(specialists_dir)
    (build_dir / "SOUL.md").write_text(system_prompt or f"You are {specialist.name}.\n")

    if specialist.has_skills(specialists_dir):
        skills_src = specialists_dir / specialist.dir_name / "skills"
        skills_dst = build_dir / "skills"
        if skills_dst.exists():
            shutil.rmtree(skills_dst)
        shutil.copytree(skills_src, skills_dst)

    if specialist.has_context(specialists_dir):
        context_src = specialists_dir / specialist.dir_name / "context"
        context_dst = build_dir / "context"
        if context_dst.exists():
            shutil.rmtree(context_dst)
        shutil.copytree(context_src, context_dst)

    containerfile_content = generate_containerfile(
        specialist, config, output_dir.parent / "templates", specialists_dir,
    )
    (build_dir / "Containerfile").write_text(containerfile_content)

    return build_dir


def build_image(
    specialist: Specialist,
    config: GlobalConfig,
    project_root: Path,
    log_callback=None,
) -> bool:
    """Build a container image for a specialist."""
    build_dir = prepare_build_context(
        specialist, config, project_root / ".build"
    )

    tag = config.registry.image_ref(specialist.dir_name)
    cmd = ["podman", "build", "--platform", "linux/amd64", "-t", tag, "-f", "Containerfile", "."]

    if log_callback:
        log_callback(f"$ {' '.join(cmd)}")
        log_callback(f"  in {build_dir}")

    try:
        return _run_streaming(cmd, log_callback, cwd=str(build_dir), timeout=600)
    except FileNotFoundError:
        if log_callback:
            log_callback("[red]podman not found, trying docker...[/red]")
        cmd[0] = "docker"
        try:
            return _run_streaming(cmd, log_callback, cwd=str(build_dir), timeout=600)
        except FileNotFoundError:
            if log_callback:
                log_callback("[red]neither podman nor docker found[/red]")
            return False
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback("[red]build timed out after 600s[/red]")
        return False


def push_image(
    specialist: Specialist,
    config: GlobalConfig,
    log_callback=None,
) -> bool:
    """Push a specialist's container image to the registry."""
    tag = config.registry.image_ref(specialist.dir_name)
    cmd = ["podman", "push", tag]

    if log_callback:
        log_callback(f"$ {' '.join(cmd)}")

    try:
        return _run_streaming(cmd, log_callback, timeout=300)
    except FileNotFoundError:
        if log_callback:
            log_callback("[red]podman not found, trying docker...[/red]")
        cmd[0] = "docker"
        try:
            return _run_streaming(cmd, log_callback, timeout=300)
        except FileNotFoundError:
            if log_callback:
                log_callback("[red]neither podman nor docker found[/red]")
            return False
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback("[red]push timed out after 300s[/red]")
        return False


