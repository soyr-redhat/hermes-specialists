from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from hermes_specialists.builder.container import (
    build_image,
    generate_cli_config,
    generate_containerfile,
    prepare_build_context,
)
from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint


class TestGenerateCliConfig:
    def test_basic_config(self, sample_specialist, sample_config, specialists_dir):
        cfg = generate_cli_config(sample_specialist, sample_config, specialists_dir)
        assert cfg["model"]["provider"] == "custom"
        assert cfg["model"]["base_url"] == "http://localhost:8000/v1"
        assert cfg["model"]["default"] == "kimi-k3"

    def test_uses_named_endpoint(self, sample_config, specialists_dir):
        s = Specialist(name="test-bot", endpoint="staging")
        cfg = generate_cli_config(s, sample_config, specialists_dir)
        assert cfg["model"]["base_url"] == "http://staging:8000/v1"

    def test_falls_back_to_default(self, sample_config, specialists_dir):
        s = Specialist(name="test-bot", endpoint="nonexistent")
        cfg = generate_cli_config(s, sample_config, specialists_dir)
        assert cfg["model"]["base_url"] == "http://localhost:8000/v1"

    def test_api_key_included(self, sample_config, specialists_dir):
        s = Specialist(name="test-bot", endpoint="staging")
        cfg = generate_cli_config(s, sample_config, specialists_dir)
        assert cfg["model"]["api_key"] == "${STAGING_KEY}"

    def test_no_api_key_when_empty(self, sample_specialist, sample_config, specialists_dir):
        cfg = generate_cli_config(sample_specialist, sample_config, specialists_dir)
        assert "api_key" not in cfg["model"]

    def test_system_prompt_included(self, sample_specialist, sample_config, specialists_dir):
        cfg = generate_cli_config(sample_specialist, sample_config, specialists_dir)
        assert "personalities" in cfg["model"]
        assert "you are a test bot." in cfg["model"]["personalities"]["specialist"]

    def test_no_system_prompt_when_missing(self, sample_config, tmp_path):
        base = tmp_path / "specialists"
        base.mkdir()
        s = Specialist(name="no-prompt")
        s.save(base)
        cfg = generate_cli_config(s, sample_config, base)
        assert "personalities" not in cfg["model"]

    def test_toolset_fallback(self, sample_config, specialists_dir):
        s = Specialist(name="test-bot", toolsets=[])
        cfg = generate_cli_config(s, sample_config, specialists_dir)
        assert cfg["platform_toolsets"]["cli"] == ["hermes-cli"]


class TestGenerateContainerfile:
    def test_renders_base_image(self, sample_specialist, sample_config, templates_dir):
        result = generate_containerfile(sample_specialist, sample_config, templates_dir)
        assert "FROM quay.io/sawyer/hermes-agent:latest" in result

    def test_skills_section(self, sample_config, templates_dir):
        s = Specialist(name="bot", skills=["pr-review"])
        result = generate_containerfile(s, sample_config, templates_dir)
        assert "COPY skills/" in result

    def test_no_skills_section(self, sample_specialist, sample_config, templates_dir):
        result = generate_containerfile(sample_specialist, sample_config, templates_dir)
        assert "COPY skills/" not in result


class TestPrepareBuildContext:
    def test_creates_files(self, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        build_dir = prepare_build_context(sample_specialist, sample_config, project / ".build")
        assert (build_dir / "cli-config.yaml").exists()
        assert (build_dir / "Containerfile").exists()

        cli_cfg = yaml.safe_load((build_dir / "cli-config.yaml").read_text())
        assert cli_cfg["model"]["provider"] == "custom"


class TestBuildImage:
    @patch("hermes_specialists.builder.container.subprocess.run")
    def test_success(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert build_image(sample_specialist, sample_config, project) is True

    @patch("hermes_specialists.builder.container.subprocess.run")
    def test_failure(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        assert build_image(sample_specialist, sample_config, project) is False

    @patch("hermes_specialists.builder.container.subprocess.run")
    def test_podman_fallback_to_docker(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "podman":
                raise FileNotFoundError
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        log = []
        assert build_image(sample_specialist, sample_config, project, log_callback=log.append) is True
        assert any("docker" in str(m).lower() or "podman" in str(m).lower() for m in log)

    @patch("hermes_specialists.builder.container.subprocess.run")
    def test_timeout(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="podman", timeout=600)
        assert build_image(sample_specialist, sample_config, project) is False
