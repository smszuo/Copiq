"""Server configuration -- architecture.md section 17 (TOML + env overrides)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource


class DeduplicationSettings(BaseSettings):
    window_seconds: int = 5
    scope_to_client: bool = True


# Used when [ai] model is unset, so switching provider alone is enough.
_DEFAULT_MODELS = {"claude_cli": "haiku", "openai": "gpt-6-luna"}


class AiSettings(BaseSettings):
    # Literal, so a typo stops the server at startup (section 17).
    # "openai" reads its key from the OPENAI_API_KEY env var.
    provider: Literal["claude_cli", "openai"] = "claude_cli"
    model: str | None = None  # None = _DEFAULT_MODELS[provider]
    # Per-action override, e.g. {"diagram": "sonnet"} -- inferring the right
    # Mermaid diagram type is a more structured task than translate/explain/
    # simplify, so it may be worth a stronger model than the default. This
    # is checked in the pipeline before falling back to `model` above, and
    # it participates in the cache key (section 22) like any other model
    # choice, so changing it never serves a stale result from the old model.
    model_overrides: dict[str, str] = Field(default_factory=dict)
    default_target_language: str = "zh-CN"
    max_input_length: int = 16384
    timeout_seconds: int = 120
    max_concurrency: int = 2

    @model_validator(mode="after")
    def _default_model_for_provider(self) -> AiSettings:
        if not self.model:  # None or "" (e.g. a blank COPIQ_AI__MODEL=)
            self.model = _DEFAULT_MODELS[self.provider]
        return self


class PromptsSettings(BaseSettings):
    # architecture.md section 18.2 -- every action's prompt is configurable
    # without a code change or touching the installed package:
    #   dir       an override directory checked before the bundled prompts;
    #             <dir>/<action>/<version>.txt shadows the built-in one
    #   versions  per-action active version, e.g. {"translate": "v2-formal"};
    #             unlisted actions keep using their built-in default version
    # `dir` is expanded (~) where it's used (pipeline.py), not here --
    # pydantic doesn't do that for a plain str field on its own.
    dir: str | None = None
    versions: dict[str, str] = Field(default_factory=dict)


class SecretDetectionSettings(BaseSettings):
    enabled: bool = True
    block_ai_actions: bool = True
    allow_override: bool = True


class RetentionSettings(BaseSettings):
    days: int = 30


class ClipboardSettings(BaseSettings):
    max_content_length: int = 1_048_576  # 1 MiB


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COPIQ_",
        env_nested_delimiter="__",
        toml_file="copiq.toml",
    )

    database_url: str = "sqlite:///./copiq.db"
    # Bind address for `copiq-server` (the `uvicorn ...` CLI form takes its
    # own --host/--port instead and ignores these). 127.0.0.1-only by
    # default; set server_host = "0.0.0.0" (or a specific LAN/VPN interface
    # IP) to reach the server from other machines -- see architecture.md
    # section 31.0 for the security tradeoffs of doing that.
    server_host: str = "127.0.0.1"
    server_port: int = 5080
    deduplication: DeduplicationSettings = Field(default_factory=DeduplicationSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    prompts: PromptsSettings = Field(default_factory=PromptsSettings)
    secret_detection: SecretDetectionSettings = Field(default_factory=SecretDetectionSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    clipboard: ClipboardSettings = Field(default_factory=ClipboardSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        # TomlConfigSettingsSource tolerates a missing toml_file (returns no
        # values), so it's registered unconditionally rather than only when
        # the file exists -- conditionally omitting it is what triggers
        # pydantic-settings' "config key set but ignored" warning.
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))


def get_settings() -> Settings:
    return Settings()
