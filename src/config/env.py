import os

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("API_KEY", ""))
    agent_config_dir: str = Field(
        default_factory=lambda: os.getenv("AGENT_CONFIG_DIR", "agent_configs")
    )
    persistence_mode: str = Field(default_factory=lambda: os.getenv("PERSISTENCE_MODE", "file"))
    data_dir: str = Field(default_factory=lambda: os.getenv("DATA_DIR", ".data"))
    # Optional feature flags
    autogen_enabled: bool = Field(
        default_factory=lambda: os.getenv("AUTOGEN_ENABLED", "0").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    agents_use_autogen: bool = Field(
        default_factory=lambda: os.getenv("AGENTS_USE_AUTOGEN", "1").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    # New configuration keys for AutoGen adapter behavior
    agents_autogen_context_max_messages: int = Field(
        default_factory=lambda: int(os.getenv("AGENTS_AUTOGEN_CONTEXT_MAX_MESSAGES", "8") or "8")
    )
    agents_autogen_context_max_chars: int = Field(
        default_factory=lambda: int(os.getenv("AGENTS_AUTOGEN_CONTEXT_MAX_CHARS", "500") or "500")
    )
    agents_autogen_session_ttl_days: int = Field(
        default_factory=lambda: int(os.getenv("AGENTS_AUTOGEN_SESSION_TTL_DAYS", "30") or "30")
    )

    # Pydantic v2 configuration using ConfigDict
    model_config = ConfigDict(arbitrary_types_allowed=True)


settings = Settings()