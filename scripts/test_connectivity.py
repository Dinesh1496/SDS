"""
Connectivity verification script.

Run this before implementing any module to confirm all external
dependencies are reachable with the read-only sds-monitor account.

Usage:
    python scripts/test_connectivity.py
    python scripts/test_connectivity.py --skip-smtp
    python scripts/test_connectivity.py --verbose
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging(level="INFO", log_format="text")
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    detail: str = ""
    duration_ms: float = 0.0


results: list[CheckResult] = []


def check(name: str):
    """Decorator to wrap a connectivity test function."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                msg, detail = fn(*args, **kwargs)
                duration = (time.monotonic() - start) * 1000
                results.append(CheckResult(name, True, msg, detail, duration))
                print(f"  \033[32m[OK]\033[0m  {name}: {msg} ({duration:.0f}ms)")
            except Exception as exc:
                duration = (time.monotonic() - start) * 1000
                results.append(CheckResult(name, False, str(exc), "", duration))
                print(f"  \033[31m[FAIL]\033[0m {name}: {exc}")
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Connectivity checks
# ---------------------------------------------------------------------------

@check("PostgreSQL Database")
def check_database():
    from app.db.session import check_db_connectivity
    if not check_db_connectivity():
        raise ConnectionError("Database did not respond to SELECT 1")
    return "Connected", ""


@check("SSH to Ceph Admin Node (sds-monitor)")
def check_ssh():
    from app.utils.ssh_client import SSHClient
    cfg = get_settings().get_ceph_settings()
    with SSHClient(
        host=cfg.admin_node,
        username=cfg.ssh_user,
        key_path=cfg.ssh_key_path,
        port=cfg.ssh_port,
        timeout=cfg.ssh_timeout,
    ) as ssh:
        result = ssh.run("echo connected-ok", timeout=10)
        if not result.succeeded or result.stdout.strip() != "connected-ok":
            raise ConnectionError(f"Unexpected response: {result.stdout!r}")
    return f"SSH to {cfg.admin_node} as {cfg.ssh_user}", ""


@check("Ceph Status (read-only, via sudo)")
def check_ceph_status():
    from app.utils.ssh_client import SSHClient
    from app.utils.ceph_client import CephClient
    cfg = get_settings().get_ceph_settings()
    with SSHClient(
        host=cfg.admin_node,
        username=cfg.ssh_user,
        key_path=cfg.ssh_key_path,
    ) as ssh:
        ceph = CephClient(ssh)
        status = ceph.get_status()
    return f"Health: {status.health_status}", \
           f"OSDs: {status.num_osds} total, {status.osds_up} up"


@check("Ceph DF (capacity, read-only)")
def check_ceph_df():
    from app.utils.ssh_client import SSHClient
    from app.utils.ceph_client import CephClient
    cfg = get_settings().get_ceph_settings()
    with SSHClient(
        host=cfg.admin_node,
        username=cfg.ssh_user,
        key_path=cfg.ssh_key_path,
    ) as ssh:
        ceph = CephClient(ssh)
        df = ceph.get_df()
    total_gb = df.total_bytes / (1024 ** 3)
    used_gb = df.total_used_raw_bytes / (1024 ** 3)
    return f"Capacity accessible", \
           f"Total: {total_gb:.1f} GB, Used: {used_gb:.1f} GB"


@check("RGW Admin API — List Users")
def check_rgw_admin():
    import requests
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials

    cfg = get_settings().get_rgw_settings()
    url = f"{cfg.admin_endpoint}/metadata/user"

    credentials = Credentials(
        access_key=cfg.admin_access_key,
        secret_key=cfg.admin_secret_key,
    )

    req = AWSRequest(method="GET", url=url, params={"max-entries": "3"})
    SigV4Auth(credentials, "s3", "us-east-1").add_auth(req)

    response = requests.get(
        url,
        params={"max-entries": "3"},
        headers=dict(req.headers),
        verify=cfg.verify_ssl,
        timeout=cfg.timeout,
    )

    if response.status_code == 403:
        raise PermissionError(
            "403 Forbidden — check RGW user caps: "
            "radosgw-admin user info --uid sds-nexus-monitor"
        )
    response.raise_for_status()
    users = response.json()
    count = len(users) if isinstance(users, list) else "?"
    return f"RGW Admin API reachable", f"Sample user count: {count}"


@check("RGW S3 API — List Buckets")
def check_rgw_s3():
    import boto3
    from botocore.config import Config

    cfg = get_settings().get_rgw_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
        config=Config(signature_version="s3v4"),
        verify=cfg.verify_ssl,
    )
    response = s3.list_buckets()
    count = len(response.get("Buckets", []))
    return "S3 API reachable", f"Visible buckets: {count}"


@check("SMTP Email Server")
def check_smtp(skip: bool = False):
    if skip:
        return "Skipped (--skip-smtp)", ""
    import smtplib
    cfg = get_settings().get_smtp_settings()
    with smtplib.SMTP(cfg.host, cfg.port, timeout=10) as smtp:
        if cfg.use_tls:
            smtp.starttls()
        smtp.login(cfg.user, cfg.password)
    return f"SMTP connected to {cfg.host}:{cfg.port}", ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test all SDS Nexus Platform connectivity"
    )
    parser.add_argument("--skip-smtp", action="store_true",
                        help="Skip SMTP test (useful if email not yet configured)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output for each check")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  SDS Nexus Platform — Connectivity Test")
    print("=" * 60 + "\n")

    check_database()
    check_ssh()
    check_ceph_status()
    check_ceph_df()
    check_rgw_admin()
    check_rgw_s3()
    check_smtp(skip=args.skip_smtp)

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if args.verbose:
        for r in results:
            if r.detail:
                status = "\033[32mOK\033[0m" if r.passed else "\033[31mFAIL\033[0m"
                print(f"  [{status}] {r.name}: {r.detail}")

    if failed > 0:
        print("\n\033[31mFailed checks — resolve before implementing modules.\033[0m")
        print("See docs/IMPLEMENTATION_GUIDE.md Section 15 (Troubleshooting).\n")
        sys.exit(1)
    else:
        print("\n\033[32mAll checks passed — ready to implement modules.\033[0m\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
