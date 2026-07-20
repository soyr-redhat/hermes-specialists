from __future__ import annotations

from pathlib import Path

import yaml

from hermes_specialists.models import GlobalConfig, RegistryConfig, VLLMEndpoint


class TestRegistryConfig:
    def test_image_ref_no_namespace(self):
        reg = RegistryConfig(url="quay.io/sawyer", repo="hermes-specialists")
        assert reg.image_ref("poet") == "quay.io/sawyer/hermes-specialists:poet"

    def test_image_ref_with_namespace(self):
        reg = RegistryConfig(url="quay.io/sawyer", repo="hermes-specialists", namespace="sawyer")
        assert reg.image_ref("poet") == "quay.io/sawyer/hermes-specialists:sawyer-poet"


class TestVLLMEndpoint:
    def test_display_with_model(self):
        ep = VLLMEndpoint(name="prod", base_url="http://prod:8000/v1", model="kimi-k3")
        assert ep.display == "prod: http://prod:8000/v1 (kimi-k3)"

    def test_display_without_model(self):
        ep = VLLMEndpoint(name="prod", base_url="http://prod:8000/v1")
        assert ep.display == "prod: http://prod:8000/v1"


class TestGlobalConfig:
    def test_get_endpoint_from_list(self, sample_config):
        ep = sample_config.get_endpoint("staging")
        assert ep is not None
        assert ep.name == "staging"
        assert ep.base_url == "http://staging:8000/v1"

    def test_get_endpoint_default(self, sample_config):
        ep = sample_config.get_endpoint("default")
        assert ep is not None
        assert ep.name == "default"

    def test_get_endpoint_missing(self, sample_config):
        assert sample_config.get_endpoint("nonexistent") is None

    def test_load_missing_file(self, tmp_path):
        config = GlobalConfig.load(tmp_path / "nope.yaml")
        assert config.default_endpoint.name == "default"
        assert config.endpoints == []

    def test_load_empty_file(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("")
        config = GlobalConfig.load(f)
        assert config.default_endpoint.name == "default"

    def test_save_and_load_roundtrip(self, tmp_path, sample_config):
        path = tmp_path / "config.yaml"
        sample_config.save(path)
        assert path.exists()

        loaded = GlobalConfig.load(path)
        assert loaded.default_endpoint.base_url == sample_config.default_endpoint.base_url
        assert loaded.default_endpoint.model == sample_config.default_endpoint.model
        assert len(loaded.endpoints) == 1
        assert loaded.endpoints[0].name == "staging"

    def test_save_creates_parent_dirs(self, tmp_path, sample_config):
        path = tmp_path / "nested" / "deep" / "config.yaml"
        sample_config.save(path)
        assert path.exists()
