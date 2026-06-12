"""Python collectors for SSH module."""

from __future__ import annotations

import os
import pwd


def audit_sshd_config() -> str:
    """Parse sshd_config for key security settings."""
    config_path = "/etc/ssh/sshd_config"
    security_keys = [
        "PermitRootLogin",
        "PasswordAuthentication",
        "PubkeyAuthentication",
        "MaxAuthTries",
        "AllowUsers",
        "AllowGroups",
        "DenyUsers",
        "DenyGroups",
        "PermitEmptyPasswords",
        "X11Forwarding",
        "UsePAM",
        "Protocol",
    ]

    try:
        with open(config_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"{config_path} not found"
    except PermissionError:
        return f"Permission denied reading {config_path}"

    settings = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) == 2:
            settings[parts[0]] = parts[1]

    results = []
    for key in security_keys:
        if key in settings:
            results.append(f"{key}: {settings[key]}")
        else:
            results.append(f"{key}: (default)")

    return "\n".join(results)


def list_authorized_keys() -> str:
    """List users with authorized_keys files and key counts."""
    results = []
    try:
        users = pwd.getpwall()
    except (AttributeError, KeyError, Exception):
        return "Cannot enumerate users (getpwall not available)"

    for user in users:
        # Skip system users with nologin/false shells
        if user.pw_shell in ("/sbin/nologin", "/usr/sbin/nologin", "/bin/false"):
            continue
        # Skip users without a usable home directory
        if user.pw_dir in ("", "/dev/null"):
            continue

        ak_path = os.path.join(user.pw_dir, ".ssh", "authorized_keys")
        if os.path.isfile(ak_path):
            try:
                with open(ak_path, "r") as f:
                    keys = [l for l in f.readlines() if l.strip() and not l.strip().startswith("#")]
                results.append(f"{user.pw_name} (uid={user.pw_uid}): {len(keys)} key(s) in {ak_path}")
            except PermissionError:
                results.append(f"{user.pw_name} (uid={user.pw_uid}): {ak_path} (permission denied)")

    if not results:
        return "No authorized_keys files found for login users"
    return "\n".join(results)
