"""End-to-end tests for the interactive app flows."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
import pytest

from hermes_specialists.app import HermesSpecialistsApp
from hermes_specialists.models import GlobalConfig, Specialist, VLLMEndpoint


MODULE = "hermes_specialists.app"


# ── specialist management ───────────────────────────────────────────────


class TestCreateSpecialist:
    @patch(f"{MODULE}._text")
    def test_creates_specialist(self, mock_text, app, project_dir):
        mock_text.side_effect = ["my-bot", "a helpful bot", "default", "llama-70b", ""]
        app._new_specialist()

        spec_dir = project_dir / "specialists" / "my-bot"
        assert (spec_dir / "specialist.yaml").exists()
        assert (spec_dir / "system-prompt.md").exists()
        assert (spec_dir / "skills").is_dir()

        loaded = Specialist.load(spec_dir)
        assert loaded.name == "my-bot"
        assert loaded.description == "a helpful bot"
        assert loaded.model == "llama-70b"

    @patch(f"{MODULE}._text")
    def test_creates_system_prompt_scaffold(self, mock_text, app, project_dir):
        mock_text.side_effect = ["helper", "does stuff", "default", "", ""]
        app._new_specialist()

        content = (project_dir / "specialists" / "helper" / "system-prompt.md").read_text()
        assert "helper" in content.lower()

    @patch(f"{MODULE}._text")
    def test_rejects_duplicate_name(self, mock_text, app, project_dir):
        Specialist(name="existing").save(project_dir / "specialists")
        mock_text.side_effect = ["existing"]
        app._new_specialist()

        loaded = Specialist.load(project_dir / "specialists" / "existing")
        assert loaded.description == ""

    @patch(f"{MODULE}._text")
    def test_normalizes_name(self, mock_text, app, project_dir):
        mock_text.side_effect = ["  My Cool Bot  ", "desc", "default", "", ""]
        app._new_specialist()
        assert (project_dir / "specialists" / "my-cool-bot" / "specialist.yaml").exists()

    @patch(f"{MODULE}._text")
    def test_cancel_on_empty_name(self, mock_text, app, project_dir):
        mock_text.return_value = None
        app._new_specialist()
        assert list((project_dir / "specialists").iterdir()) == []


class TestEditSpecialist:
    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._fuzzy")
    def test_updates_specialist(self, mock_fuzzy, mock_text, app, project_dir):
        Specialist(name="bot", description="old desc").save(project_dir / "specialists")

        mock_fuzzy.return_value = "bot"
        mock_text.side_effect = ["new desc", "staging", "gpt-4"]

        app._edit_specialist()

        loaded = Specialist.load(project_dir / "specialists" / "bot")
        assert loaded.description == "new desc"
        assert loaded.endpoint == "staging"
        assert loaded.model == "gpt-4"

    @patch(f"{MODULE}._fuzzy")
    def test_cancel_on_no_pick(self, mock_fuzzy, app, project_dir):
        mock_fuzzy.return_value = None
        app._edit_specialist()


class TestDeleteSpecialist:
    @patch(f"{MODULE}._confirm")
    @patch(f"{MODULE}._fuzzy")
    def test_deletes_specialist(self, mock_fuzzy, mock_confirm, app, project_dir):
        Specialist(name="doomed").save(project_dir / "specialists")
        assert (project_dir / "specialists" / "doomed").exists()

        mock_fuzzy.return_value = "doomed"
        mock_confirm.return_value = True
        app._delete_specialist()

        assert not (project_dir / "specialists" / "doomed").exists()

    @patch(f"{MODULE}._confirm")
    @patch(f"{MODULE}._fuzzy")
    def test_cancel_keeps_specialist(self, mock_fuzzy, mock_confirm, app, project_dir):
        Specialist(name="keeper").save(project_dir / "specialists")

        mock_fuzzy.return_value = "keeper"
        mock_confirm.return_value = False
        app._delete_specialist()

        assert (project_dir / "specialists" / "keeper").exists()


# ── skills management ───────────────────────────────────────────────────


class TestImportSkill:
    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._fuzzy")
    def test_imports_skill_file(self, mock_fuzzy, mock_text, app, project_dir, tmp_path):
        Specialist(name="bot").save(project_dir / "specialists")
        (project_dir / "specialists" / "bot" / "skills").mkdir(parents=True, exist_ok=True)

        skill_src = tmp_path / "my-skill" / "SKILL.md"
        skill_src.parent.mkdir()
        skill_src.write_text("---\ndescription: does things\n---\ndo the thing\n")

        mock_fuzzy.return_value = "bot"
        mock_text.side_effect = [str(skill_src), "my-skill"]

        app._import_skill()

        imported = project_dir / "specialists" / "bot" / "skills" / "my-skill" / "SKILL.md"
        assert imported.exists()
        assert "does things" in imported.read_text()

    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._fuzzy")
    def test_import_nonexistent_file(self, mock_fuzzy, mock_text, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        mock_fuzzy.return_value = "bot"
        mock_text.side_effect = ["/no/such/file.md"]
        app._import_skill()


class TestViewSkills:
    @patch(f"{MODULE}._fuzzy")
    def test_view_with_skills(self, mock_fuzzy, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        skill_dir = project_dir / "specialists" / "bot" / "skills" / "review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\ndescription: reviews prs\n---\nreview code\n")

        mock_fuzzy.return_value = "bot"
        app._view_skills()

    @patch(f"{MODULE}._fuzzy")
    def test_view_no_skills(self, mock_fuzzy, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        (project_dir / "specialists" / "bot" / "skills").mkdir(parents=True, exist_ok=True)

        mock_fuzzy.return_value = "bot"
        app._view_skills()


class TestChainSkills:
    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._fuzzy")
    def test_creates_chain(self, mock_fuzzy, mock_text, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        skills_base = project_dir / "specialists" / "bot" / "skills"
        for skill in ["fetch", "analyze", "report"]:
            d = skills_base / skill
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"# {skill}\n")

        mock_fuzzy.return_value = "bot"
        mock_text.return_value = "fetch, analyze, report"
        app._chain_skills()

        chain_file = project_dir / "specialists" / "bot" / "chain.yaml"
        assert chain_file.exists()
        chain = yaml.safe_load(chain_file.read_text())
        assert chain["chain"] == ["fetch", "analyze", "report"]

    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._fuzzy")
    def test_rejects_invalid_skill_names(self, mock_fuzzy, mock_text, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        skill_dir = project_dir / "specialists" / "bot" / "skills" / "fetch"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# fetch\n")

        mock_fuzzy.return_value = "bot"
        mock_text.return_value = "fetch, nonexistent"
        app._chain_skills()

        assert not (project_dir / "specialists" / "bot" / "chain.yaml").exists()


# ── endpoint management ─────────────────────────────────────────────────


class TestEndpointAdd:
    @patch(f"{MODULE}._text")
    def test_adds_endpoint(self, mock_text, app, project_dir):
        mock_text.side_effect = ["staging", "http://staging:8000/v1", "STAGING_KEY", "llama-70b"]
        app._endpoint_add()

        config = GlobalConfig.load(project_dir / "config.yaml")
        ep = config.get_endpoint("staging")
        assert ep is not None
        assert ep.base_url == "http://staging:8000/v1"
        assert ep.api_key == "STAGING_KEY"
        assert ep.model == "llama-70b"

    @patch(f"{MODULE}._text")
    def test_replaces_existing_endpoint(self, mock_text, app, project_dir):
        mock_text.side_effect = ["staging", "http://old:8000/v1", "", ""]
        app._endpoint_add()

        mock_text.side_effect = ["staging", "http://new:8000/v1", "", ""]
        app._endpoint_add()

        config = GlobalConfig.load(project_dir / "config.yaml")
        staging_eps = [ep for ep in config.endpoints if ep.name == "staging"]
        assert len(staging_eps) == 1
        assert staging_eps[0].base_url == "http://new:8000/v1"


class TestEndpointEdit:
    @patch(f"{MODULE}._text")
    def test_edits_default(self, mock_text, app, project_dir):
        mock_text.side_effect = ["http://new:9000/v1", "MY_KEY", "gpt-4"]
        app._endpoint_edit()

        config = GlobalConfig.load(project_dir / "config.yaml")
        assert config.default_endpoint.base_url == "http://new:9000/v1"
        assert config.default_endpoint.api_key == "MY_KEY"
        assert config.default_endpoint.model == "gpt-4"


class TestEndpointRemove:
    @patch(f"{MODULE}._select")
    @patch(f"{MODULE}._text")
    def test_removes_endpoint(self, mock_text, mock_select, app, project_dir):
        mock_text.side_effect = ["staging", "http://staging:8000/v1", "", ""]
        app._endpoint_add()

        mock_select.return_value = "staging"
        app._endpoint_rm()

        config = GlobalConfig.load(project_dir / "config.yaml")
        assert config.get_endpoint("staging") is None

    def test_no_extra_endpoints(self, app, project_dir):
        app._endpoint_rm()


# ── build & deploy ──────────────────────────────────────────────────────


class TestBuildOne:
    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._fuzzy")
    def test_builds_specialist(self, mock_fuzzy, mock_stream, app, project_dir):
        Specialist(name="bot", model="llama").save(project_dir / "specialists")
        prompt_file = project_dir / "specialists" / "bot" / "system-prompt.md"
        prompt_file.write_text("you are bot\n")

        mock_fuzzy.return_value = "bot"
        mock_stream.return_value = True

        app._build_one()

        assert mock_stream.called
        cmd = mock_stream.call_args[0][0]
        assert cmd[0] == "podman"

    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._fuzzy")
    def test_build_failure(self, mock_fuzzy, mock_stream, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        mock_fuzzy.return_value = "bot"
        mock_stream.return_value = False
        app._build_one()


class TestBuildAll:
    @patch("hermes_specialists.builder.container._run_streaming")
    def test_builds_multiple(self, mock_stream, app, project_dir):
        for name in ["alpha", "bravo"]:
            Specialist(name=name).save(project_dir / "specialists")
        mock_stream.return_value = True

        app._build_all()

        assert mock_stream.call_count == 2

    def test_no_specialists(self, app, project_dir):
        app._build_all()


class TestDeployOne:
    @patch("hermes_specialists.builder.deployer.subprocess.run")
    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._fuzzy")
    def test_deploys_specialist(self, mock_fuzzy, mock_stream, mock_deploy_run, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")

        mock_fuzzy.return_value = "bot"
        mock_stream.return_value = True
        mock_deploy_run.return_value = MagicMock(returncode=0, stdout="deployed", stderr="")

        app._deploy_one()

        assert mock_deploy_run.called
        cmd = mock_deploy_run.call_args[0][0]
        assert cmd[0] == "oc"
        assert "apply" in cmd

        manifest = project_dir / ".deploy" / "bot.yaml"
        assert manifest.exists()
        assert "bot" in manifest.read_text()

    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._fuzzy")
    def test_deploy_stops_on_build_failure(self, mock_fuzzy, mock_stream, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        mock_fuzzy.return_value = "bot"
        mock_stream.return_value = False
        app._deploy_one()
        assert not (project_dir / ".deploy").exists()

    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._fuzzy")
    def test_deploy_stops_on_push_failure(self, mock_fuzzy, mock_stream, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        mock_fuzzy.return_value = "bot"

        results = iter([True, False])
        mock_stream.side_effect = lambda *args, **kwargs: next(results)
        app._deploy_one()


# ── config view ─────────────────────────────────────────────────────────


class TestShowConfig:
    def test_runs_without_error(self, app, project_dir):
        app._show_config()

    def test_with_specialists(self, app, project_dir):
        Specialist(name="bot").save(project_dir / "specialists")
        app._show_config()


# ── navigation ──────────────────────────────────────────────────────────


class TestNavigation:
    @patch(f"{MODULE}._select")
    def test_main_menu_exit(self, mock_select, app):
        mock_select.return_value = None
        app.run()

    @patch(f"{MODULE}._select")
    def test_specialists_back(self, mock_select, app):
        mock_select.return_value = None
        app._specialists()

    @patch(f"{MODULE}._select")
    def test_skills_back(self, mock_select, app):
        mock_select.return_value = None
        app._skills()

    @patch(f"{MODULE}._select")
    def test_build_back(self, mock_select, app):
        mock_select.return_value = None
        app._build()

    @patch(f"{MODULE}._select")
    def test_config_from_main_menu(self, mock_select, app, project_dir):
        mock_select.side_effect = ["config", None]
        app.run()

    @patch(f"{MODULE}._select")
    def test_specialists_flow_from_main_menu(self, mock_select, app, project_dir):
        mock_select.side_effect = ["specialists", None, None]
        app.run()


# ── full flow integration ───────────────────────────────────────────────


class TestFullFlow:
    @patch("hermes_specialists.builder.container._run_streaming")
    @patch(f"{MODULE}._confirm")
    @patch(f"{MODULE}._fuzzy")
    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._select")
    def test_create_then_build_then_deploy(
        self, mock_select, mock_text, mock_fuzzy, mock_confirm, mock_run, app, project_dir
    ):
        mock_run.return_value = True

        mock_select.side_effect = [
            "specialists",
            "new",
            None,
            "build",
            "one",
            None,
            None,
        ]
        mock_text.side_effect = [
            "deploy-bot",
            "handles deploys",
            "default",
            "llama-70b",
            "",
        ]
        mock_fuzzy.side_effect = ["deploy-bot"]

        app.run()

        spec_dir = project_dir / "specialists" / "deploy-bot"
        assert spec_dir.exists()
        assert (spec_dir / "specialist.yaml").exists()
        assert (spec_dir / "system-prompt.md").exists()

        loaded = Specialist.load(spec_dir)
        assert loaded.name == "deploy-bot"
        assert loaded.description == "handles deploys"

        assert mock_run.called

    @patch(f"{MODULE}._confirm")
    @patch(f"{MODULE}._fuzzy")
    @patch(f"{MODULE}._text")
    @patch(f"{MODULE}._select")
    def test_create_then_delete(
        self, mock_select, mock_text, mock_fuzzy, mock_confirm, app, project_dir
    ):
        mock_select.side_effect = [
            "specialists",
            "new",
            "delete",
            None,
        ]
        mock_text.side_effect = ["temp-bot", "temporary", "default", "", ""]
        mock_fuzzy.side_effect = ["temp-bot"]
        mock_confirm.return_value = True

        app.run()

        assert not (project_dir / "specialists" / "temp-bot").exists()
