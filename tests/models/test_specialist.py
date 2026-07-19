from __future__ import annotations

from pathlib import Path

from hermes_specialists.models import Specialist
from hermes_specialists.models.specialist import DEFAULT_TOOLSETS


class TestSpecialistDirName:
    def test_lowercase(self):
        s = Specialist(name="MyBot")
        assert s.dir_name == "mybot"

    def test_spaces_to_hyphens(self):
        s = Specialist(name="PR Review Bot")
        assert s.dir_name == "pr-review-bot"

    def test_already_clean(self):
        s = Specialist(name="test-bot")
        assert s.dir_name == "test-bot"


class TestSpecialistSystemPrompt:
    def test_reads_file(self, specialists_dir, sample_specialist):
        prompt = sample_specialist.system_prompt(specialists_dir)
        assert prompt == "you are a test bot."

    def test_missing_file(self, tmp_path):
        s = Specialist(name="no-prompt")
        assert s.system_prompt(tmp_path) == ""


class TestSpecialistSaveLoad:
    def test_roundtrip(self, tmp_path, sample_specialist):
        sample_specialist.save(tmp_path)
        loaded = Specialist.load(tmp_path / sample_specialist.dir_name)
        assert loaded.name == sample_specialist.name
        assert loaded.description == sample_specialist.description
        assert loaded.endpoint == sample_specialist.endpoint
        assert loaded.model == sample_specialist.model

    def test_creates_directory(self, tmp_path, sample_specialist):
        sample_specialist.save(tmp_path)
        assert (tmp_path / sample_specialist.dir_name / "specialist.yaml").exists()

    def test_default_toolsets(self):
        s = Specialist(name="a")
        assert s.toolsets == list(DEFAULT_TOOLSETS)

    def test_toolsets_not_shared(self):
        a = Specialist(name="a")
        b = Specialist(name="b")
        a.toolsets.append("extra")
        assert "extra" not in b.toolsets


class TestSpecialistDiscover:
    def test_missing_dir(self, tmp_path):
        assert Specialist.discover(tmp_path / "nope") == []

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert Specialist.discover(d) == []

    def test_finds_specialists(self, specialists_dir):
        found = Specialist.discover(specialists_dir)
        assert len(found) == 1
        assert found[0].name == "test-bot"

    def test_skips_dirs_without_yaml(self, specialists_dir):
        (specialists_dir / "garbage").mkdir()
        found = Specialist.discover(specialists_dir)
        assert len(found) == 1

    def test_sorted_order(self, specialists_dir):
        Specialist(name="alpha").save(specialists_dir)
        Specialist(name="zeta").save(specialists_dir)
        found = Specialist.discover(specialists_dir)
        names = [s.name for s in found]
        assert names == sorted(names)
