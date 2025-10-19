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

    # Pydantic v2 configuration using ConfigDict
    model_config = ConfigDict(arbitrary_types_allowed=True)


settings = Settings()
