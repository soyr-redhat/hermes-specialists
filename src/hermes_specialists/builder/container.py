"""Containerfile generation and image building."""

from __future__ import annotations

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

    if endpoint.api_key_env:
        hermes_config["model"]["api_key"] = f"${{{endpoint.api_key_env}}}"
        hermes_config["custom_providers"][0]["api_key"] = f"${{{endpoint.api_key_env}}}"

    return hermes_config


def generate_containerfile(specialist: Specialist, config: GlobalConfig, templates_dir: Path) -> str:
    """Render a Containerfile from the template for a specialist."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("Containerfile.template")

    return template.render(
        base_image=config.registry.base_image,
        specialist_name=specialist.dir_name,
        skills=bool(specialist.skills),
        context_files=bool(specialist.context_files),
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

    containerfile_content = generate_containerfile(
        specialist, config, output_dir.parent / "templates"
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

    tag = f"{config.registry.url}/{specialist.dir_name}:latest"
    cmd = ["podman", "build", "-t", tag, "-f", "Containerfile", "."]

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
    tag = f"{config.registry.url}/{specialist.dir_name}:latest"
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


