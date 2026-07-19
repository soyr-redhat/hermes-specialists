"""Containerfile generation and image building."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from hermes_specialists.models import GlobalConfig, Specialist


def generate_cli_config(specialist: Specialist, config: GlobalConfig, specialists_dir: Path) -> dict:
    """Generate a Hermes cli-config.yaml for a specialist."""
    endpoint = config.get_endpoint(specialist.endpoint) or config.default_endpoint

    cli_config: dict = {
        "model": {
            "default": specialist.model or endpoint.model or "",
            "provider": "custom",
            "base_url": endpoint.base_url,
        },
        "terminal": {
            "backend": "local",
            "cwd": ".",
            "timeout": 180,
        },
        "platform_toolsets": {
            "cli": specialist.toolsets if specialist.toolsets else ["hermes-cli"],
        },
    }

    if endpoint.api_key_env:
        cli_config["model"]["api_key"] = f"${{{endpoint.api_key_env}}}"

    system_prompt = specialist.system_prompt(specialists_dir)
    if system_prompt:
        cli_config["model"]["personalities"] = {
            "specialist": system_prompt,
        }

    return cli_config


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

    cli_config = generate_cli_config(specialist, config, output_dir.parent / "specialists")
    (build_dir / "cli-config.yaml").write_text(
        yaml.dump(cli_config, default_flow_style=False, sort_keys=False)
    )

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
        result = subprocess.run(
            cmd, cwd=str(build_dir), capture_output=True, text=True, timeout=600
        )
        if log_callback:
            if result.stdout:
                log_callback(result.stdout)
            if result.stderr:
                log_callback(result.stderr)
        return result.returncode == 0
    except FileNotFoundError:
        if log_callback:
            log_callback("[red]podman not found, trying docker...[/red]")
        cmd[0] = "docker"
        try:
            result = subprocess.run(
                cmd, cwd=str(build_dir), capture_output=True, text=True, timeout=600
            )
            if log_callback:
                if result.stdout:
                    log_callback(result.stdout)
                if result.stderr:
                    log_callback(result.stderr)
            return result.returncode == 0
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if log_callback:
            if result.stdout:
                log_callback(result.stdout)
            if result.stderr:
                log_callback(result.stderr)
        return result.returncode == 0
    except FileNotFoundError:
        if log_callback:
            log_callback("[red]podman not found, trying docker...[/red]")
        cmd[0] = "docker"
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if log_callback:
                if result.stdout:
                    log_callback(result.stdout)
                if result.stderr:
                    log_callback(result.stderr)
            return result.returncode == 0
        except FileNotFoundError:
            if log_callback:
                log_callback("[red]neither podman nor docker found[/red]")
            return False
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback("[red]push timed out after 300s[/red]")
        return False
