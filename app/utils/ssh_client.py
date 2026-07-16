"""
SSH client wrapper using Paramiko.

Provides a context-manager-based SSH client with:
- Key-based authentication only (no password auth for security)
- Configurable connection timeout and retry logic
- Structured logging of all commands executed
- Command output parsing helpers

Usage::

    with SSHClient(host="ceph-admin.internal", username="cephadmin",
                   key_path="/etc/keys/ceph_key") as ssh:
        result = ssh.run("ceph status --format json")
        data = result.stdout_json()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

import paramiko

from app.core.logging import get_logger
from app.utils.retry import retry_on_network_error

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class CommandResult(NamedTuple):
    """
    Encapsulates the result of an SSH command execution.

    Attributes:
        command: The command that was run.
        stdout: Raw stdout string.
        stderr: Raw stderr string.
        exit_code: Process exit code (0 = success).
    """

    command: str
    stdout: str
    stderr: str
    exit_code: int

    @property
    def succeeded(self) -> bool:
        """Return True if the command exited with code 0."""
        return self.exit_code == 0

    def stdout_json(self) -> Any:
        """
        Parse stdout as JSON and return the result.

        Raises:
            ValueError: If stdout is not valid JSON.
        """
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Command stdout is not valid JSON.\n"
                f"Command: {self.command}\n"
                f"Stdout: {self.stdout[:500]!r}"
            ) from exc

    def stdout_lines(self) -> list[str]:
        """Return stdout split into non-empty lines."""
        return [line for line in self.stdout.splitlines() if line.strip()]

    def raise_on_error(self) -> "CommandResult":
        """
        Raise a RuntimeError if the command failed.

        Returns:
            self — for chaining.

        Raises:
            RuntimeError: If exit_code != 0.
        """
        if not self.succeeded:
            raise RuntimeError(
                f"SSH command failed (exit={self.exit_code}).\n"
                f"Command: {self.command}\n"
                f"Stderr: {self.stderr}"
            )
        return self


# ---------------------------------------------------------------------------
# SSH Client
# ---------------------------------------------------------------------------


class SSHClient:
    """
    Context-manager SSH client for executing commands on Ceph nodes.

    Always uses key-based authentication. The private key must be readable
    by the application process (do not use passphrase-protected keys in
    automated contexts without an agent).

    Args:
        host: Hostname or IP address of the remote node.
        username: SSH username (e.g. "cephadmin").
        key_path: Absolute path to the SSH private key file.
        port: SSH port (default 22).
        timeout: TCP connect timeout in seconds (default 30).
        banner_timeout: SSH banner negotiation timeout (default 15).
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str,
        port: int = 22,
        timeout: int = 30,
        banner_timeout: int = 15,
    ) -> None:
        self._host = host
        self._username = username
        self._key_path = key_path
        self._port = port
        self._timeout = timeout
        self._banner_timeout = banner_timeout
        self._client: paramiko.SSHClient | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @retry_on_network_error(
        max_attempts=3,
        wait_min=2.0,
        wait_max=10.0,
        exceptions=(paramiko.SSHException, OSError, TimeoutError),
    )
    def connect(self) -> None:
        """
        Establish the SSH connection.

        Retried up to 3 times on transient network errors. Raises
        ``paramiko.SSHException`` or ``OSError`` after all attempts fail.
        """
        key_path = Path(self._key_path)
        if not key_path.exists():
            raise FileNotFoundError(
                f"SSH private key not found: {self._key_path}"
            )

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            pkey = paramiko.RSAKey.from_private_key_file(str(key_path))
        except paramiko.PasswordRequiredException:
            raise paramiko.SSHException(
                "SSH private key requires a passphrase — use an unencrypted key "
                "or configure ssh-agent for automated use."
            )

        logger.debug("Connecting via SSH", host=self._host, port=self._port, user=self._username)

        client.connect(
            hostname=self._host,
            port=self._port,
            username=self._username,
            pkey=pkey,
            timeout=self._timeout,
            banner_timeout=self._banner_timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        self._client = client
        logger.info("SSH connection established", host=self._host, user=self._username)

    def close(self) -> None:
        """Close the SSH connection if open."""
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("SSH connection closed", host=self._host)

    @property
    def is_connected(self) -> bool:
        """Return True if the SSH transport is active."""
        if not self._client:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run(
        self,
        command: str,
        timeout: int | None = None,
        raise_on_error: bool = False,
    ) -> CommandResult:
        """
        Execute a shell command on the remote host.

        Args:
            command: Shell command string to execute.
            timeout: Per-command timeout override (seconds). Uses connection
                     timeout if not specified.
            raise_on_error: If True, raise RuntimeError on non-zero exit.

        Returns:
            CommandResult with stdout, stderr, and exit code.

        Raises:
            RuntimeError: If not connected.
            RuntimeError: If raise_on_error=True and command fails.
        """
        if not self._client:
            raise RuntimeError("SSH client is not connected. Call connect() first.")

        effective_timeout = timeout or self._timeout
        logger.debug("Executing SSH command", host=self._host, command=command[:200])

        try:
            stdin, stdout, stderr = self._client.exec_command(
                command, timeout=effective_timeout
            )
            stdout_str = stdout.read().decode("utf-8", errors="replace").strip()
            stderr_str = stderr.read().decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
        except paramiko.SSHException as exc:
            raise RuntimeError(
                f"SSH command execution failed on {self._host}: {exc}"
            ) from exc

        result = CommandResult(
            command=command,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
        )

        if result.succeeded:
            logger.debug(
                "SSH command succeeded", host=self._host, exit_code=exit_code
            )
        else:
            logger.warning(
                "SSH command returned non-zero exit code",
                host=self._host,
                command=command[:200],
                exit_code=exit_code,
                stderr=stderr_str[:500],
            )

        if raise_on_error:
            result.raise_on_error()

        return result

    def run_json(self, command: str, timeout: int | None = None) -> Any:
        """
        Execute a command and parse the stdout as JSON.

        Convenience method that combines run() + stdout_json().

        Args:
            command: Shell command expected to produce JSON output.
            timeout: Optional per-command timeout override.

        Returns:
            Parsed JSON object (dict, list, etc.).

        Raises:
            RuntimeError: On non-zero exit code.
            ValueError: If output is not valid JSON.
        """
        result = self.run(command, timeout=timeout, raise_on_error=True)
        return result.stdout_json()

    def test_connectivity(self) -> bool:
        """
        Verify the connection by running a trivial command.

        Returns:
            True if the connection is healthy, False otherwise.
        """
        try:
            result = self.run("echo ok", timeout=10)
            return result.succeeded and result.stdout.strip() == "ok"
        except Exception as exc:
            logger.warning("SSH connectivity test failed", host=self._host, error=str(exc))
            return False
