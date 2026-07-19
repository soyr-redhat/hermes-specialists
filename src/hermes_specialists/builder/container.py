"""Containerfile generation and image building."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib import request, error
import json

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


def make_repo_public(
    specialist: Specialist,
    config: GlobalConfig,
    log_callback=None,
) -> bool:
    """Set the quay.io repository to public via the API."""
    token = os.environ.get("QUAY_API_TOKEN", "")
    if not token:
        env_path = Path.cwd() / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("QUAY_API_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break

    if not token:
        if log_callback:
            log_callback("[dim]no QUAY_API_TOKEN set, skipping visibility change[/dim]")
        return True

    namespace = config.registry.url.split("/", 1)[-1] if "/" in config.registry.url else config.registry.url
    repo = specialist.dir_name
    url = f"https://quay.io/api/v1/repository/{namespace}/{repo}/changevisibility"

    data = json.dumps({"visibility": "public"}).encode()
    req = request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                if log_callback:
                    log_callback(f"[dim]repository {namespace}/{repo} set to public[/dim]")
                return True
            if log_callback:
                log_callback(f"[yellow]visibility API returned {resp.status}[/yellow]")
            return False
    except error.HTTPError as e:
        if log_callback:
            log_callback(f"[yellow]could not set repo public: {e.code} {e.reason}[/yellow]")
        return False
    except Exception as e:
        if log_callback:
            log_callback(f"[yellow]could not set repo public: {e}[/yellow]")
        return False
