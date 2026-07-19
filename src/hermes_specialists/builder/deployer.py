"""OpenShift deployment generation and application."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from hermes_specialists.models import GlobalConfig, Specialist


def generate_deployment(specialist: Specialist, config: GlobalConfig, templates_dir: Path) -> str:
    """Render a deployment manifest from the template for a specialist."""
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("deployment.template.yaml")

    return template.render(
        specialist_name=specialist.dir_name,
        registry=config.registry.url,
        tag="latest",
    )


def write_deployment(specialist: Specialist, config: GlobalConfig, project_root: Path) -> Path:
    """Write a deployment manifest for a specialist."""
    templates_dir = project_root / "templates"
    manifest = generate_deployment(specialist, config, templates_dir)

    output_dir = project_root / ".deploy"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / f"{specialist.dir_name}.yaml"
    manifest_path.write_text(manifest)
    return manifest_path


def deploy(specialist: Specialist, config: GlobalConfig, project_root: Path, log_callback=None) -> bool:
    """Deploy a specialist to OpenShift via oc apply."""
    manifest_path = write_deployment(specialist, config, project_root)

    cmd = ["oc", "apply", "-f", str(manifest_path)]
    if log_callback:
        log_callback(f"$ {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if log_callback:
            if result.stdout:
                log_callback(result.stdout)
            if result.stderr:
                log_callback(result.stderr)
        return result.returncode == 0
    except FileNotFoundError:
        if log_callback:
            log_callback("[red]oc cli not found — install openshift cli[/red]")
        return False
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback("[red]deploy timed out[/red]")
        return False
