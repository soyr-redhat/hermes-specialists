from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from hermes_specialists.builder.container import (
    build_image,
    generate_config,
    generate_containerfile,
    prepare_build_context,
    push_image,
)
from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint


class TestGenerateConfig:
    def test_basic_config(self, sample_specialist, sample_config):
        cfg = generate_config(sample_specialist, sample_config)
        assert cfg["model"]["provider"] == "custom"
        assert cfg["model"]["base_url"] == "http://localhost:8000/v1"
        assert cfg["model"]["default"] == "kimi-k3"

    def test_uses_named_endpoint(self, sample_config):
        s = Specialist(name="test-bot", endpoint="staging")
        cfg = generate_config(s, sample_config)
        assert cfg["model"]["base_url"] == "http://staging:8000/v1"

    def test_falls_back_to_default(self, sample_config):
        s = Specialist(name="test-bot", endpoint="nonexistent")
        cfg = generate_config(s, sample_config)
        assert cfg["model"]["base_url"] == "http://localhost:8000/v1"

    def test_api_key_included(self, sample_config):
        s = Specialist(name="test-bot", endpoint="staging")
        cfg = generate_config(s, sample_config)
        assert cfg["model"]["api_key"] == "STAGING_KEY"

    def test_no_api_key_when_empty(self, sample_specialist, sample_config):
        cfg = generate_config(sample_specialist, sample_config)
        assert "api_key" not in cfg["model"]


class TestGenerateContainerfile:
    def test_renders_base_image(self, sample_specialist, sample_config, templates_dir, specialists_dir):
        result = generate_containerfile(sample_specialist, sample_config, templates_dir, specialists_dir)
        assert "FROM quay.io/sawyer/hermes-agent:latest" in result

    def test_skills_section(self, sample_config, templates_dir, specialists_dir):
        s = Specialist(name="test-bot")
        skill_dir = specialists_dir / "test-bot" / "skills" / "pr-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# pr-review\n")
        result = generate_containerfile(s, sample_config, templates_dir, specialists_dir)
        assert "COPY skills/" in result

    def test_no_skills_section(self, sample_specialist, sample_config, templates_dir, specialists_dir):
        result = generate_containerfile(sample_specialist, sample_config, templates_dir, specialists_dir)
        assert "COPY skills/" not in result

    def test_copies_config_and_soul(self, sample_specialist, sample_config, templates_dir, specialists_dir):
        result = generate_containerfile(sample_specialist, sample_config, templates_dir, specialists_dir)
        assert "COPY config.yaml" in result
        assert "COPY SOUL.md" in result


class TestPrepareBuildContext:
    def test_creates_files(self, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")
        prompt_file = project / "specialists" / sample_specialist.dir_name / "system-prompt.md"
        prompt_file.write_text("you are a test bot.\n")

        build_dir = prepare_build_context(sample_specialist, sample_config, project / ".build")
        assert (build_dir / "config.yaml").exists()
        assert (build_dir / "SOUL.md").exists()
        assert (build_dir / "Containerfile").exists()

        cfg = yaml.safe_load((build_dir / "config.yaml").read_text())
        assert cfg["model"]["provider"] == "custom"

        soul = (build_dir / "SOUL.md").read_text()
        assert "test bot" in soul


class TestBuildImage:
    @patch("hermes_specialists.builder.container._run_streaming")
    def test_success(self, mock_stream, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_stream.return_value = True
        assert build_image(sample_specialist, sample_config, project) is True

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_failure(self, mock_stream, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_stream.return_value = False
        assert build_image(sample_specialist, sample_config, project) is False

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_podman_fallback_to_docker(self, mock_stream, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        def side_effect(cmd, log_callback=None, **kwargs):
            if cmd[0] == "podman":
                raise FileNotFoundError
            return True

        mock_stream.side_effect = side_effect
        log = []
        assert build_image(sample_specialist, sample_config, project, log_callback=log.append) is True
        assert any("docker" in str(m).lower() or "podman" in str(m).lower() for m in log)

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_timeout(self, mock_stream, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")
        (project / "specialists").mkdir()
        sample_specialist.save(project / "specialists")

        mock_stream.side_effect = subprocess.TimeoutExpired(cmd="podman", timeout=600)
        assert build_image(sample_specialist, sample_config, project) is False


class TestPushImage:
    @patch("hermes_specialists.builder.container._run_streaming")
    def test_success(self, mock_stream, sample_specialist, sample_config):
        mock_stream.return_value = True
        assert push_image(sample_specialist, sample_config) is True
        cmd = mock_stream.call_args[0][0]
        assert cmd[0] == "podman"
        assert cmd[1] == "push"
        assert "quay.io/sawyer/hermes-specialists:test-bot" in cmd[2]

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_failure(self, mock_stream, sample_specialist, sample_config):
        mock_stream.return_value = False
        assert push_image(sample_specialist, sample_config) is False

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_podman_fallback_to_docker(self, mock_stream, sample_specialist, sample_config):
        def side_effect(cmd, log_callback=None, **kwargs):
            if cmd[0] == "podman":
                raise FileNotFoundError
            return True

        mock_stream.side_effect = side_effect
        assert push_image(sample_specialist, sample_config) is True

    @patch("hermes_specialists.builder.container._run_streaming")
    def test_timeout(self, mock_stream, sample_specialist, sample_config):
        mock_stream.side_effect = subprocess.TimeoutExpired(cmd="podman", timeout=300)
        assert push_image(sample_specialist, sample_config) is False
