"""
Application configuration management.

Uses pydantic-settings for typed, validated configuration with environment
variable and .env file support. All sensitive values should be provided
via environment variables, never hardcoded.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, EmailStr, Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="sds_nexus", description="Database name")
    user: str = Field(default="sds_nexus_user", description="Database user")
    password: str = Field(description="Database password")
    pool_size: int = Field(default=10, ge=1, le=50, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Max overflow connections")
    pool_timeout: int = Field(default=30, ge=1, description="Pool connection timeout (seconds)")
    pool_recycle: int = Field(default=3600, ge=60, description="Connection recycle interval (seconds)")
    echo_sql: bool = Field(default=False, description="Echo SQL statements to log")

    @property
    def url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class CephSSHSettings(BaseSettings):
    """Ceph cluster SSH access configuration."""

    model_config = SettingsConfigDict(env_prefix="CEPH_", extra="ignore")

    cluster_name: str = Field(default="prod-cluster-01", description="Cluster identifier")
    cluster_display_name: str = Field(default="Production Ceph Cluster")
    monitor_host: str = Field(description="Primary Ceph monitor hostname/IP")
    monitor_port: int = Field(default=6789)
    admin_node: str = Field(description="Ceph admin node hostname")
    ssh_user: str = Field(default="cephadmin", description="SSH username for Ceph nodes")
    ssh_key_path: str = Field(description="Path to SSH private key file")
    ssh_port: int = Field(default=22)
    ssh_timeout: int = Field(default=30, ge=5, description="SSH connection timeout (seconds)")
    ssh_retry_attempts: int = Field(default=3, ge=1, le=10)
    ssh_retry_delay: int = Field(default=5, ge=1)


class RGWSettings(BaseSettings):
    """RADOS Gateway (S3 API) configuration."""

    model_config = SettingsConfigDict(env_prefix="RGW_", extra="ignore")

    endpoint: str = Field(description="RGW S3 endpoint URL")
    access_key: str = Field(description="RGW S3 access key")
    secret_key: str = Field(description="RGW S3 secret key")
    admin_endpoint: str = Field(description="RGW admin API endpoint")
    admin_access_key: str = Field(description="RGW admin access key")
    admin_secret_key: str = Field(description="RGW admin secret key")
    verify_ssl: bool = Field(default=False)
    timeout: int = Field(default=30, ge=5)


class SMTPSettings(BaseSettings):
    """Email / SMTP configuration."""

    model_config = SettingsConfigDict(env_prefix="SMTP_", extra="ignore")

    host: str = Field(description="SMTP server hostname")
    port: int = Field(default=587)
    user: str = Field(description="SMTP authentication username")
    password: str = Field(description="SMTP authentication password")
    use_tls: bool = Field(default=True)
    use_ssl: bool = Field(default=False)
    timeout: int = Field(default=30, ge=5)
    from_address: str = Field(description="From email address")
    from_name: str = Field(default="SDS Nexus Platform")


class AlertThresholds(BaseSettings):
    """Alert threshold configuration."""

    model_config = SettingsConfigDict(env_prefix="ALERT_", extra="ignore")

    osd_down_threshold: int = Field(default=1, ge=1, description="Alert if >= N OSDs are down")
    pg_degraded_threshold: int = Field(default=100, ge=1)
    capacity_warning_percent: float = Field(default=75.0, ge=1.0, le=100.0)
    capacity_critical_percent: float = Field(default=85.0, ge=1.0, le=100.0)
    cluster_unhealthy: bool = Field(default=True)


class ChargebackSettings(BaseSettings):
    """Chargeback and billing configuration."""

    model_config = SettingsConfigDict(env_prefix="CHARGEBACK_", extra="ignore")

    currency_primary: str = Field(default="GBP")
    currency_secondary: str = Field(default="USD")
    gbp_per_gb_month: float = Field(default=0.05, ge=0.0, description="Cost per GB per month in GBP")
    usd_per_gb_month: float = Field(default=0.06, ge=0.0, description="Cost per GB per month in USD")
    gbp_usd_rate: float = Field(default=1.27, ge=0.0, description="GBP to USD exchange rate")
    billing_day: int = Field(default=1, ge=1, le=28, description="Day of month for billing cycle")
    include_vat: bool = Field(default=True)
    vat_rate: float = Field(default=0.20, ge=0.0, le=1.0)


class MonitoringSettings(BaseSettings):
    """Monitoring interval configuration (seconds)."""

    model_config = SettingsConfigDict(env_prefix="MONITOR_", extra="ignore")

    cluster_health_interval: int = Field(default=300, ge=60)
    node_interval: int = Field(default=300, ge=60)
    object_storage_interval: int = Field(default=3600, ge=300)
    capacity_interval: int = Field(default=3600, ge=300)


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: str = Field(default="INFO")
    format: str = Field(default="json")
    output_path: str = Field(default="/var/log/sds-nexus")
    rotation: str = Field(default="100 MB")
    retention: str = Field(default="30 days")
    backtrace: bool = Field(default=True)
    diagnose: bool = Field(default=False)

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return upper


class SecuritySettings(BaseSettings):
    """Security and JWT configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    secret_key: str = Field(description="JWT signing secret key (min 32 chars)")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=5)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v


class Settings(BaseSettings):
    """
    Master application settings.

    All sub-settings are composed here for a single configuration object
    accessible throughout the application via the get_settings() dependency.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="SDS Nexus Platform")
    app_version: str = Field(default="1.0.0")
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_debug: bool = Field(default=False)
    app_secret_key: str = Field(description="Application secret key")

    # Distribution lists
    email_ops_team: str = Field(default="", description="Comma-separated ops team emails")
    email_management: str = Field(default="", description="Comma-separated management emails")
    email_alerts: str = Field(default="", description="Comma-separated alert emails")

    # Reporting
    report_output_path: str = Field(default="/var/sds-nexus/reports")
    report_retention_days: int = Field(default=365, ge=1)
    report_daily_email_time: str = Field(default="07:00")
    report_6h_schedule: str = Field(default="0 */6 * * *")
    report_monthly_day: int = Field(default=1, ge=1, le=28)

    # Paths
    temp_dir: str = Field(default="/tmp/sds-nexus")
    data_dir: str = Field(default="/var/sds-nexus/data")

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = {"development", "staging", "production"}
        if v.lower() not in valid_envs:
            raise ValueError(f"APP_ENV must be one of: {valid_envs}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def ops_team_emails(self) -> list[str]:
        """Parse comma-separated ops team email list."""
        return [e.strip() for e in self.email_ops_team.split(",") if e.strip()]

    @property
    def management_emails(self) -> list[str]:
        """Parse comma-separated management email list."""
        return [e.strip() for e in self.email_management.split(",") if e.strip()]

    @property
    def alert_emails(self) -> list[str]:
        """Parse comma-separated alert email list."""
        return [e.strip() for e in self.email_alerts.split(",") if e.strip()]

    def get_db_settings(self) -> DatabaseSettings:
        return DatabaseSettings()

    def get_ceph_settings(self) -> CephSSHSettings:
        return CephSSHSettings()

    def get_rgw_settings(self) -> RGWSettings:
        return RGWSettings()

    def get_smtp_settings(self) -> SMTPSettings:
        return SMTPSettings()

    def get_alert_thresholds(self) -> AlertThresholds:
        return AlertThresholds()

    def get_chargeback_settings(self) -> ChargebackSettings:
        return ChargebackSettings()

    def get_monitoring_settings(self) -> MonitoringSettings:
        return MonitoringSettings()

    def get_logging_settings(self) -> LoggingSettings:
        return LoggingSettings()

    def get_security_settings(self) -> SecuritySettings:
        return SecuritySettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached application settings instance.

    Uses lru_cache so settings are only loaded once per process.
    Call get_settings.cache_clear() in tests to reset.
    """
    return Settings()
