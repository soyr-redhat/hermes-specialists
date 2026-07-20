from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class VLLMEndpoint(BaseModel):
    """A vLLM serving endpoint."""

    name: str = "default"
    base_url: str = "http://localhost:8000/v1"
    api_key: str = ""
    model: str = ""

    @property
    def display(self) -> str:
        label = f"{self.name}: {self.base_url}"
        if self.model:
            label += f" ({self.model})"
        return label


class RegistryConfig(BaseModel):
    """Container registry settings."""

    url: str = "quay.io/sawyer"
    repo: str = "hermes-specialists"
    namespace: str = ""
    base_image: str = "quay.io/sawyer/hermes-agent:latest"

    def image_ref(self, specialist_dir_name: str) -> str:
        tag = f"{self.namespace}-{specialist_dir_name}" if self.namespace else specialist_dir_name
        return f"{self.url}/{self.repo}:{tag}"


class GlobalConfig(BaseModel):
    """Global configuration for hermes-specialists."""

    default_endpoint: VLLMEndpoint = Field(default_factory=VLLMEndpoint)
    endpoints: list[VLLMEndpoint] = Field(default_factory=list)
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    def get_endpoint(self, name: str) -> VLLMEndpoint | None:
        for ep in self.endpoints:
            if ep.name == name:
                return ep
        if self.default_endpoint.name == name:
            return self.default_endpoint
        return None

    @classmethod
    def load(cls, path: Path) -> GlobalConfig:
        if path.exists():
            data = yaml.safe_load(path.read_text()) or {}
            return cls.model_validate(data)
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False))
