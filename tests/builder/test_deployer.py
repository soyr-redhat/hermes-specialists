from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from hermes_specialists.builder.deployer import (
    deploy,
    generate_deployment,
    write_deployment,
)
from hermes_specialists.models import Specialist


class TestGenerateDeployment:
    def test_renders_specialist_name(self, sample_specialist, sample_config, templates_dir):
        result = generate_deployment(sample_specialist, sample_config, templates_dir)
        assert "test-bot" in result
        assert "quay.io/sawyer" in result

    def test_contains_deployment_kind(self, sample_specialist, sample_config, templates_dir):
        result = generate_deployment(sample_specialist, sample_config, templates_dir)
        assert "kind: Deployment" in result
        assert "kind: PersistentVolumeClaim" in result


class TestWriteDeployment:
    def test_creates_manifest(self, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")

        path = write_deployment(sample_specialist, sample_config, project)
        assert path.exists()
        assert path.name == "test-bot.yaml"
        assert path.parent.name == ".deploy"

        content = path.read_text()
        assert "test-bot" in content


class TestDeploy:
    @patch("hermes_specialists.builder.deployer.subprocess.run")
    def test_success(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")

        mock_run.return_value = MagicMock(returncode=0, stdout="deployed", stderr="")
        assert deploy(sample_specialist, sample_config, project) is True

    @patch("hermes_specialists.builder.deployer.subprocess.run")
    def test_failure(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
        assert deploy(sample_specialist, sample_config, project) is False

    @patch("hermes_specialists.builder.deployer.subprocess.run")
    def test_oc_not_found(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")

        mock_run.side_effect = FileNotFoundError
        log = []
        assert deploy(sample_specialist, sample_config, project, log_callback=log.append) is False
        assert any("oc" in str(m).lower() for m in log)

    @patch("hermes_specialists.builder.deployer.subprocess.run")
    def test_timeout(self, mock_run, sample_specialist, sample_config, tmp_path, templates_dir):
        project = tmp_path / "project"
        project.mkdir()
        shutil.copytree(templates_dir, project / "templates")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="oc", timeout=60)
        assert deploy(sample_specialist, sample_config, project) is False
