"""Configuration loading and management."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from resumeforge.exceptions import ConfigError


class Config(BaseModel):
    """ResumeForge configuration model."""

    paths: dict[str, str] = Field(default_factory=dict)
    pipeline: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, dict[str, str]] = Field(default_factory=dict)
    agents: dict[str, dict[str, Any]] = Field(default_factory=dict)
    providers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    fallback_chain: dict[str, str] = Field(default_factory=dict)
    fallback_model_alias_overrides: dict[str, str] = Field(default_factory=dict)
    logging: dict[str, Any] = Field(default_factory=dict)


def load_config(config_path: str | Path = "./config.yaml") -> Config:
    """Load configuration from YAML file."""
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        return Config(**data)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration file: {e}") from e
    except Exception as e:
        raise ConfigError(f"Error loading configuration: {e}") from e
