"""
Multi-environment configuration management.

Supports loading different configuration profiles for development, staging,
and production environments with environment-specific overrides.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import get_logger

logger = get_logger(__name__)


class Environment(str, Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentConfig(BaseSettings):
    """
    Environment-specific configuration loader.
    
    Loads configuration from multiple sources in order of precedence:
    1. Environment variables (highest priority)
    2. Environment-specific .env file (e.g., .env.production)
    3. Base .env file
    4. Default values (lowest priority)
    """
    
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )
    
    # Environment detection
    app_env: str = "development"
    
    # Configuration file paths
    config_dir: str = "/etc/sds-nexus"
    
    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate and normalize environment name."""
        normalized = v.lower()
        try:
            Environment(normalized)
            return normalized
        except ValueError:
            valid_envs = [e.value for e in Environment]
            raise ValueError(
                f"Invalid APP_ENV '{v}'. Must be one of: {', '.join(valid_envs)}"
            )
    
    @property
    def environment(self) -> Environment:
        """Get the current environment as an enum."""
        return Environment(self.app_env)
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_staging(self) -> bool:
        return self.environment == Environment.STAGING
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


def get_env_file_path() -> str | None:
    """
    Determine which .env file to load based on APP_ENV.
    
    Priority:
    1. /etc/sds-nexus/{environment}.env (production)
    2. .env.{environment} (development/staging)
    3. /etc/sds-nexus/.env (production fallback)
    4. .env (development fallback)
    
    Returns:
        Path to the .env file, or None if not found
    """
    # Get environment from ENV var (default to development)
    env = os.getenv("APP_ENV", "development").lower()
    
    # Check if we're in a production-like deployment
    config_dir = Path("/etc/sds-nexus")
    is_deployed = config_dir.exists()
    
    env_files_to_check = []
    
    if is_deployed:
        # Production deployment - check /etc/sds-nexus first
        env_files_to_check.extend([
            config_dir / f"{env}.env",
            config_dir / ".env",
        ])
    
    # Also check local directory (for development)
    env_files_to_check.extend([
        Path(f".env.{env}"),
        Path(".env"),
    ])
    
    for env_file in env_files_to_check:
        if env_file.exists():
            logger.info(f"Loading environment configuration from: {env_file}")
            return str(env_file)
    
    logger.warning("No .env file found - using environment variables and defaults only")
    return None


def load_environment_config() -> dict[str, Any]:
    """
    Load environment-specific configuration.
    
    Returns:
        Dictionary of configuration values
    """
    env_file = get_env_file_path()
    
    if env_file:
        # Load .env file
        from dotenv import dotenv_values
        config = dotenv_values(env_file)
        
        # Override with actual environment variables
        for key in config.keys():
            if key in os.environ:
                config[key] = os.environ[key]
        
        return config
    
    # No .env file - use environment variables only
    return dict(os.environ)


def get_config_value(
    key: str,
    default: Any = None,
    required: bool = False,
) -> Any:
    """
    Get a configuration value from environment.
    
    Args:
        key: Configuration key (environment variable name)
        default: Default value if not found
        required: If True, raise ValueError if not found
    
    Returns:
        Configuration value
    
    Raises:
        ValueError: If required=True and value not found
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"Required configuration '{key}' not found")
    
    return value


def validate_environment_config() -> bool:
    """
    Validate that all required environment-specific configuration is present.
    
    Returns:
        True if valid, False otherwise
    """
    env_config = EnvironmentConfig()
    
    # Required variables for all environments
    required_vars = [
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "APP_SECRET_KEY",
        "JWT_SECRET_KEY",
    ]
    
    # Additional required variables for production
    if env_config.is_production:
        required_vars.extend([
            "CEPH_MONITOR_HOST",
            "CEPH_ADMIN_NODE",
            "CEPH_SSH_KEY_PATH",
            "RGW_ENDPOINT",
            "RGW_ACCESS_KEY",
            "RGW_SECRET_KEY",
            "SMTP_HOST",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "SMTP_FROM_ADDRESS",
        ])
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(
            f"Missing required configuration variables for {env_config.app_env} environment",
            missing_vars=missing_vars,
        )
        return False
    
    logger.info(f"Environment configuration validated for {env_config.app_env}")
    return True


def get_environment_info() -> dict[str, Any]:
    """
    Get information about the current environment configuration.
    
    Returns:
        Dictionary with environment details
    """
    env_config = EnvironmentConfig()
    env_file = get_env_file_path()
    
    return {
        "environment": env_config.app_env,
        "is_production": env_config.is_production,
        "is_staging": env_config.is_staging,
        "is_development": env_config.is_development,
        "config_file": env_file,
        "config_dir": env_config.config_dir,
    }
