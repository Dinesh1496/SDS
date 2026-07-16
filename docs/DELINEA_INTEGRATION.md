# Delinea Secret Server Integration Guide

**Version:** 1.0.0  
**Purpose:** Secure credential management for SDS Nexus platform using Delinea Secret Server  
**Target OS:** RHEL 10  
**Auth Model:** Service Account with API access to Delinea Secret Server

---

## Table of Contents

1. [Architecture & Overview](#1-architecture--overview)
2. [Delinea Secret Server Setup](#2-delinea-secret-server-setup)
3. [SDS Nexus Integration](#3-sds-nexus-integration)
4. [Python Secret Retrieval Client](#4-python-secret-retrieval-client)
5. [Configuration & Deployment](#5-configuration--deployment)
6. [Security Best Practices](#6-security-best-practices)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Architecture & Overview

### Why Delinea Secret Server?

Instead of storing secrets in `.env` files (which can be accidentally committed or leaked),
Delinea Secret Server provides:

- **Centralized credential management** — all passwords in one place
- **Audit trail** — every secret access is logged
- **Rotation automation** — change passwords without redeploying
- **Access control** — fine-grained permissions per secret
- **Encryption at rest** — secrets encrypted in database
- **API-based retrieval** — applications pull secrets at runtime

### Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│   SDS Nexus Platform (RHEL 10)                          │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │ Application Code (Python)                        │  │
│   │                                                   │  │
│   │  Modules 1-6, Worker Services, FastAPI routes   │  │
│   └──────────┬───────────────────────────────────────┘  │
│              │ needs credentials at runtime              │
│   ┌──────────▼───────────────────────────────────────┐  │
│   │ Secret Retrieval Client (new module)             │  │
│   │                                                   │  │
│   │  - Load service account key from disk            │  │
│   │  - Request secret from Delinea API               │  │
│   │  - Cache in memory (optional, TTL)               │  │
│   │  - Return to application                         │  │
│   └──────────┬───────────────────────────────────────┘  │
│              │ HTTPS API call (encrypted)                │
├──────────────┼──────────────────────────────────────────┤
│              │                                            │
│ Platform Network                                         │
└──────────────┼──────────────────────────────────────────┘
               │
    ┌──────────▼──────────┐
    │ HTTPS Network       │
    │ (TLS 1.2+)         │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────────────────────────────┐
    │  Delinea Secret Server (Corporate Network)  │
    │                                              │
    │  - Ceph SSH credentials                     │
    │  - PostgreSQL password                      │
    │  - SMTP credentials                         │
    │  - RGW S3 access keys                       │
    │  - QuantaStor API keys (if used)            │
    │  - Any other sensitive data                 │
    └──────────────────────────────────────────────┘
```

### Secrets Managed by Delinea

| Secret | Usage | Current Source | Delinea Path |
|---|---|---|---|
| Ceph SSH private key | SSH to nodes | `/etc/sds-nexus/keys/sds_monitor_ed25519` | `/infrastructure/ceph/sds-monitor-key` |
| Ceph SSH password | (unused — key-based) | N/A | `/infrastructure/ceph/sds-monitor-password` |
| PostgreSQL password | DB connection | `DB_PASSWORD` in .env | `/databases/postgresql/sds_nexus_user` |
| SMTP credentials | Email reports | `SMTP_USER`, `SMTP_PASSWORD` in .env | `/email/smtp/sds-nexus` |
| RGW access keys | S3 API | `RGW_ACCESS_KEY`, `RGW_SECRET_KEY` in .env | `/object-storage/rgw/sds-nexus-monitor` |
| JWT secret | API authentication | `JWT_SECRET_KEY` in .env | `/application/jwt/sds-nexus-api` |
| App secret key | Session management | `APP_SECRET_KEY` in .env | `/application/secrets/sds-nexus-app` |

---

## 2. Delinea Secret Server Setup

### 2.1 Administrator Tasks (Delinea Team)

#### Step 1 — Create Secrets in Delinea Web Interface

In the Delinea Secret Server web portal (`https://delinea.yourcompany.com`):

1. **Create Folder Structure**
   - Right-click → New Folder → `/infrastructure`
   - Right-click → New Folder → `/infrastructure/ceph`
   - Right-click → New Folder → `/databases`
   - Right-click → New Folder → `/databases/postgresql`
   - Right-click → New Folder → `/email`
   - Right-click → New Folder → `/email/smtp`
   - Right-click → New Folder → `/object-storage`
   - Right-click → New Folder → `/object-storage/rgw`
   - Right-click → New Folder → `/application`
   - Right-click → New Folder → `/application/jwt`
   - Right-click → New Folder → `/application/secrets`

2. **Create Individual Secrets**

   **SSH Key Secret:**
   - Name: `/infrastructure/ceph/sds-monitor-key`
   - Type: "Text (Multiline)" or "SSH Key"
   - Content: Paste the entire private key (from `/etc/sds-nexus/keys/sds_monitor_ed25519`)
   - Description: "SDS Nexus Ceph SSH private key for sds-monitor user"

   **PostgreSQL Password Secret:**
   - Name: `/databases/postgresql/sds_nexus_user`
   - Type: "Password"
   - Username: `sds_nexus_user`
   - Password: (generate strong password or use existing)
   - Description: "SDS Nexus database user password"

   **SMTP Credentials Secret:**
   - Name: `/email/smtp/sds-nexus`
   - Type: "Username/Password"
   - Username: `sds-nexus@company.com`
   - Password: (SMTP server password)
   - Description: "SDS Nexus SMTP relay credentials"

   **RGW S3 Keys Secret:**
   - Name: `/object-storage/rgw/sds-nexus-monitor`
   - Type: "API Key"
   - Fields:
     - `access_key`: (from `radosgw-admin user info`)
     - `secret_key`: (from `radosgw-admin user info`)
   - Description: "SDS Nexus RGW S3 API credentials (read-only)"

   **JWT Secret:**
   - Name: `/application/jwt/sds-nexus-api`
   - Type: "Text"
   - Content: (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - Description: "SDS Nexus JWT signing secret"

   **App Secret:**
   - Name: `/application/secrets/sds-nexus-app`
   - Type: "Text"
   - Content: (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - Description: "SDS Nexus application secret key"

#### Step 2 — Create Service Account in Delinea

1. In Delinea Web UI: Administration → Users → New User
   - **Username:** `sds-nexus-api-user`
   - **Display Name:** "SDS Nexus Platform API Access"
   - **Email:** `sds-nexus@company.com`
   - **Authentication:** API Key (generate one)
   - **Note the API Key** — this goes to the platform server

2. Grant Permissions:
   - Administration → Roles → New Role → "SDS Nexus API Reader"
   - Permissions:
     - View secrets in `/infrastructure/ceph/` (read-only)
     - View secrets in `/databases/` (read-only)
     - View secrets in `/email/` (read-only)
     - View secrets in `/object-storage/` (read-only)
     - View secrets in `/application/` (read-only)
   - Assign this role to user `sds-nexus-api-user`

#### Step 3 — Generate API Key for Platform Server

```bash
# Delinea Admin generates an API key for the service account
# In Delinea Web UI:
# - Administration > Users > sds-nexus-api-user > API Key
# - Click "Generate API Key"
# - Copy the key (you'll only see it once)
# - Save to: /etc/sds-nexus/delinea/api-key.txt (on platform server)
#   with permissions: 600, owner: sds-nexus:sds-nexus
```

---

## 3. SDS Nexus Integration

### 3.1 Delinea API Client Library

Create a new Python module to handle Delinea Secret Server interactions.

**File:** `app/utils/secret_manager.py`

```python
"""
Delinea Secret Server integration for secure credential management.

This module provides a unified interface to retrieve secrets from Delinea,
with optional in-memory caching and automatic retry on failure.

Usage:
    manager = DelineaSecretManager(
        server_url="https://delinea.yourcompany.com",
        api_key_path="/etc/sds-nexus/delinea/api-key.txt"
    )
    
    # Retrieve a secret
    ssh_key = manager.get_secret("/infrastructure/ceph/sds-monitor-key")
    
    # Retrieve a username/password secret
    db_creds = manager.get_secret("/databases/postgresql/sds_nexus_user")
    # Returns: {"username": "sds_nexus_user", "password": "xxx"}
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from app.core.logging import get_logger
from app.utils.retry import retry_on_network_error

logger = get_logger(__name__)


class DelineaSecretManager:
    """Client for retrieving secrets from Delinea Secret Server via REST API."""

    def __init__(
        self,
        server_url: str,
        api_key_path: str,
        verify_ssl: bool = True,
        timeout: int = 30,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        """
        Initialize Delinea Secret Manager.

        Args:
            server_url: Base URL of Delinea Secret Server (e.g. https://delinea.company.com)
            api_key_path: Path to file containing the API key (mode 600)
            verify_ssl: Verify SSL certificate (False for self-signed in dev)
            timeout: HTTP request timeout (seconds)
            cache_ttl_seconds: Cache secrets for this many seconds (0 = no cache)
        """
        self.server_url = server_url.rstrip("/")
        self.api_key_path = Path(api_key_path)
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.cache_ttl_seconds = cache_ttl_seconds

        # Load API key once at init
        self._api_key = self._load_api_key()
        self._cache: dict[str, tuple[Any, float]] = {}  # path -> (value, timestamp)

    def _load_api_key(self) -> str:
        """
        Load API key from file.

        The file must:
        - Exist at the configured path
        - Be owned by sds-nexus:sds-nexus
        - Have permissions 600
        - Contain exactly one line (the API key)

        Returns:
            API key string

        Raises:
            FileNotFoundError: API key file not found
            ValueError: File permissions are too permissive (> 600)
            RuntimeError: Unable to read API key
        """
        if not self.api_key_path.exists():
            raise FileNotFoundError(
                f"Delinea API key file not found: {self.api_key_path}. "
                f"Run: sudo tee {self.api_key_path} < <(echo '<api-key>') && "
                f"sudo chmod 600 {self.api_key_path} && "
                f"sudo chown sds-nexus:sds-nexus {self.api_key_path}"
            )

        # Check permissions (must be 0o600 = -rw-------)
        mode = self.api_key_path.stat().st_mode
        if mode & 0o077:  # Check for any group/other permissions
            raise ValueError(
                f"API key file {self.api_key_path} has insecure permissions "
                f"({oct(mode)}). Must be 0o600. Run: sudo chmod 600 {self.api_key_path}"
            )

        try:
            with open(self.api_key_path, "r") as f:
                api_key = f.read().strip()
            if not api_key:
                raise ValueError("API key file is empty")
            return api_key
        except Exception as exc:
            raise RuntimeError(f"Failed to read API key from {self.api_key_path}: {exc}") from exc

    @retry_on_network_error(max_attempts=3, wait_min=2.0, wait_max=10.0)
    def get_secret(
        self, secret_path: str, force_refresh: bool = False
    ) -> dict[str, Any] | str:
        """
        Retrieve a secret from Delinea Secret Server.

        Args:
            secret_path: Path to the secret (e.g. '/infrastructure/ceph/sds-monitor-key')
            force_refresh: Skip cache and fetch fresh from server

        Returns:
            Secret value. For simple text secrets, returns str. For structured
            secrets (username/password, API keys), returns dict with keys.

        Raises:
            RuntimeError: Delinea API error, auth failure, or network error
        """
        # Check cache first
        if not force_refresh and secret_path in self._cache:
            value, cached_at = self._cache[secret_path]
            age_seconds = time.time() - cached_at
            if age_seconds < self.cache_ttl_seconds:
                logger.debug(
                    "Secret retrieved from cache",
                    secret_path=secret_path,
                    cache_age_seconds=int(age_seconds),
                )
                return value

        logger.debug("Fetching secret from Delinea", secret_path=secret_path)

        # Build API request
        api_url = f"{self.server_url}/api/v1/secrets"
        params = {"filter": f"path eq '{secret_path}'", "take": 1}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Delinea API request failed",
                secret_path=secret_path,
                error=str(exc),
                status_code=getattr(exc.response, "status_code", None),
            )
            raise RuntimeError(f"Failed to retrieve secret from Delinea: {exc}") from exc

        # Parse response
        data = response.json()
        records = data.get("records", [])

        if not records:
            raise RuntimeError(f"Secret not found in Delinea: {secret_path}")

        secret_record = records[0]
        secret_id = secret_record.get("id")

        # Fetch full secret details (includes field values)
        logger.debug("Fetching secret details", secret_id=secret_id, secret_path=secret_path)
        details_url = f"{self.server_url}/api/v1/secrets/{secret_id}"

        try:
            response = requests.get(
                details_url,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to fetch secret details", secret_id=secret_id, error=str(exc))
            raise RuntimeError(f"Failed to fetch secret details: {exc}") from exc

        secret_details = response.json()
        fields = secret_details.get("items", [])

        # Extract secret value
        # For simple text secrets, return the "secret data" field
        # For structured secrets, return a dict of all fields
        if len(fields) == 1:
            # Single field — return as string
            value = fields[0].get("itemValue", "")
        else:
            # Multiple fields — return as dict
            value = {field.get("fieldName", "value"): field.get("itemValue", "") for field in fields}

        # Cache the result
        if self.cache_ttl_seconds > 0:
            self._cache[secret_path] = (value, time.time())
            logger.debug("Secret cached", secret_path=secret_path, ttl_seconds=self.cache_ttl_seconds)

        logger.info("Secret retrieved successfully", secret_path=secret_path)
        return value

    def get_secret_string(self, secret_path: str) -> str:
        """
        Retrieve a secret as a string (convenience method for text secrets).

        Args:
            secret_path: Path to the secret

        Returns:
            Secret value as string

        Raises:
            RuntimeError: If secret is not a simple text value
        """
        value = self.get_secret(secret_path)
        if isinstance(value, dict):
            raise ValueError(
                f"Secret at {secret_path} is structured (dict), "
                f"not a simple string. Use get_secret() instead."
            )
        return value

    def clear_cache(self) -> None:
        """Clear all cached secrets."""
        self._cache.clear()
        logger.info("Secret cache cleared")

    def __repr__(self) -> str:
        return f"DelineaSecretManager(server_url={self.server_url})"
```

### 3.2 Integration into Application

**File:** `app/core/config.py` — Update the Settings class

Add a method to the existing `Settings` class to initialize the secret manager:

```python
def get_secret_manager(self) -> "DelineaSecretManager | None":
    """
    Return a Delinea Secret Manager if configured.
    
    Returns None if Delinea is not enabled.
    Raises if Delinea is enabled but configuration is invalid.
    """
    from app.utils.secret_manager import DelineaSecretManager
    
    if not getattr(self, 'use_delinea', False):
        return None
    
    delinea_server = os.getenv("DELINEA_SERVER_URL")
    delinea_api_key_path = os.getenv("DELINEA_API_KEY_PATH")
    
    if not delinea_server or not delinea_api_key_path:
        raise ValueError(
            "DELINEA_SERVER_URL and DELINEA_API_KEY_PATH must be set "
            "if USE_DELINEA=true"
        )
    
    return DelineaSecretManager(
        server_url=delinea_server,
        api_key_path=delinea_api_key_path,
        verify_ssl=os.getenv("DELINEA_VERIFY_SSL", "true").lower() == "true",
        cache_ttl_seconds=int(os.getenv("DELINEA_CACHE_TTL_SECONDS", "3600")),
    )
```

### 3.3 Update Application Startup

**File:** `app/main.py` — Lifespan context manager

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    logger.info("Starting SDS Nexus Platform")
    
    # Initialize Delinea Secret Manager if enabled
    settings = get_settings()
    if os.getenv("USE_DELINEA", "false").lower() == "true":
        try:
            secret_manager = settings.get_secret_manager()
            # Store in app state for use by modules
            app.state.secret_manager = secret_manager
            logger.info("Delinea Secret Manager initialized")
        except Exception as exc:
            logger.error("Failed to initialize Delinea Secret Manager", error=str(exc))
            if os.getenv("REQUIRE_DELINEA", "false").lower() == "true":
                raise  # Fail startup if Delinea is required
            # Otherwise continue with fallback to .env (logging the warning)
            logger.warning("Continuing without Delinea — secrets from .env only")
    
    yield
    logger.info("Platform shutting down")
```

### 3.4 Use Secrets in Module 3 (Object Storage)

**File:** `app/services/object_storage/rgw_admin_client.py`

```python
async def get_rgw_credentials() -> tuple[str, str]:
    """
    Retrieve RGW credentials from Delinea Secret Server or .env fallback.
    
    Returns: (access_key, secret_key) tuple
    """
    # Try Delinea first
    if hasattr(app.state, 'secret_manager') and app.state.secret_manager:
        try:
            creds = app.state.secret_manager.get_secret("/object-storage/rgw/sds-nexus-monitor")
            if isinstance(creds, dict):
                return (creds['access_key'], creds['secret_key'])
        except Exception as exc:
            logger.warning("Failed to retrieve RGW credentials from Delinea", error=str(exc))
    
    # Fallback to .env
    return (settings.RGW_ACCESS_KEY, settings.RGW_SECRET_KEY)
```

---

## 4. Configuration & Deployment

### 4.1 Environment Variables

Add to `/etc/sds-nexus/production.env`:

```bash
# ============================================================
# DELINEA SECRET SERVER INTEGRATION
# ============================================================

# Enable/disable Delinea (false = use .env secrets only)
USE_DELINEA=true

# Fail startup if Delinea is unavailable (true = required, false = optional fallback)
REQUIRE_DELINEA=false

# Delinea server URL
DELINEA_SERVER_URL="https://delinea.yourcompany.com"

# Path to API key file (mode 600, owner sds-nexus:sds-nexus)
DELINEA_API_KEY_PATH="/etc/sds-nexus/delinea/api-key.txt"

# Verify Delinea SSL certificate (false for self-signed in dev/staging)
DELINEA_VERIFY_SSL=true

# Cache secrets in memory (seconds) — 0 = no cache
DELINEA_CACHE_TTL_SECONDS=3600
```

### 4.2 Platform Server Setup

```bash
# Create Delinea directory
sudo mkdir -p /etc/sds-nexus/delinea
sudo chmod 700 /etc/sds-nexus/delinea
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/delinea

# Place API key file (provided by Delinea admin)
# The Delinea admin will provide this securely (e.g., via 1Password, encrypted email)
sudo tee /etc/sds-nexus/delinea/api-key.txt << 'EOF'
<paste-api-key-here>
EOF

# Secure the API key
sudo chmod 600 /etc/sds-nexus/delinea/api-key.txt
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/delinea/api-key.txt

# Verify permissions
ls -la /etc/sds-nexus/delinea/
# Expected: -rw------- 1 sds-nexus sds-nexus ... api-key.txt
```

---

## 5. Security Best Practices

### 5.1 Principle of Least Privilege

- **Delinea Role:** Grant only read access to required secrets
- **API Key:** Rotate annually or on suspicion of compromise
- **Platform Account:** Run app as `sds-nexus` user (non-root)
- **File Permissions:** API key file mode 600, not world-readable

### 5.2 Network Security

- **HTTPS Only:** All Delinea API calls over TLS 1.2+
- **Firewall Rules:** Allow platform server → Delinea server only from platform IP
- **Network Segmentation:** Delinea on isolated management network if possible
- **VPN:** Use VPN if Delinea is off-site

### 5.3 Audit & Monitoring

- **Enable Audit Logging:** In Delinea, enable audit trail for secret access
- **Monitor Access:** Alert on unusual access patterns (e.g. bulk secret retrieval)
- **Log Integration:** Forward Delinea audit logs to SIEM
- **Secrets in Logs:** Never log secret values — use placeholder names

### 5.4 Secret Rotation

In Delinea Web UI, set up automatic rotation for:

- PostgreSQL passwords (every 90 days)
- SMTP credentials (every 180 days)
- RGW S3 keys (every 180 days)
- JWT secrets (manually, as needed)

---

## 6. Troubleshooting

### Issue: "API key file not found"

```bash
# Check file exists and has correct permissions
ls -la /etc/sds-nexus/delinea/api-key.txt

# Fix ownership/permissions
sudo chown sds-nexus:sds-nexus /etc/sds-nexus/delinea/api-key.txt
sudo chmod 600 /etc/sds-nexus/delinea/api-key.txt
```

### Issue: "Delinea API request failed" (auth error)

```bash
# Verify API key is correct (first 20 chars should match Delinea UI)
head -c 20 /etc/sds-nexus/delinea/api-key.txt

# Test API connectivity
curl -v -H "Authorization: Bearer <api-key>" \
    https://delinea.yourcompany.com/api/v1/secrets \
    -k  # Ignore self-signed cert warnings in dev

# Check Delinea service status and logs
# (Contact Delinea admin if API is down)
```

### Issue: "Secret not found in Delinea"

```bash
# Verify secret path exists in Delinea Web UI
# Navigate to: Administration > Secrets > (search for secret name)

# Verify platform user has read access
# In Delinea: Administration > Users > sds-nexus-api-user > Roles
# Ensure role has permission to read the secret path
```

### Issue: "Continuing without Delinea" (fallback to .env)

This occurs when:
- `USE_DELINEA=true` but Delinea is unreachable
- `REQUIRE_DELINEA=false` (optional mode)

Platform will use `.env` secrets as fallback. To make Delinea required:

```bash
# Set REQUIRE_DELINEA=true in .env
# Platform will fail to start if Delinea is unavailable
# (recommended for production)
```

---

## 7. Migration Strategy

### Phase 1: Optional (Dev/Staging)

```bash
USE_DELINEA=true
REQUIRE_DELINEA=false  # Optional fallback
```

- Start using Delinea
- Keep .env as fallback if Delinea is down
- Monitor logs for any issues
- Duration: 2-4 weeks

### Phase 2: Enforce (Staging)

```bash
USE_DELINEA=true
REQUIRE_DELINEA=true   # Delinea required
```

- Platform fails to start without Delinea
- All modules use only Delinea secrets
- Remove sensitive data from .env files
- Duration: 1-2 weeks

### Phase 3: Production

```bash
USE_DELINEA=true
REQUIRE_DELINEA=true
DELINEA_VERIFY_SSL=true       # Enforce cert verification
DELINEA_CACHE_TTL_SECONDS=3600 # Cache for performance
```

- Full production deployment
- Enable audit logging in Delinea
- Set up monitoring and alerts
- Document for operations team

---

## Checklist

Before deploying Delinea integration:

- [ ] Delinea server is installed and accessible
- [ ] All secrets are created in Delinea Web UI
- [ ] Service account `sds-nexus-api-user` is created with read-only role
- [ ] API key is generated and saved to `/etc/sds-nexus/delinea/api-key.txt`
- [ ] API key file has correct permissions (mode 600)
- [ ] Firewall allows platform server → Delinea server on HTTPS
- [ ] `SECRET_MANAGER` module (this document) is installed
- [ ] `.env` is updated with Delinea configuration
- [ ] Platform starts without errors (`systemctl start sds-nexus-api`)
- [ ] Audit logging is enabled in Delinea
- [ ] Secret rotation policies are configured
- [ ] Operations team is trained on Delinea management

---

**Last Updated:** 2025-01-15  
**Maintained By:** Storage Operations Team
