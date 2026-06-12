"""Python collectors for cron module."""

from __future__ import annotations

import os
import subprocess

# RHEL-style and Debian-style crontab spools
_SPOOL_DIRS = ("/var/spool/cron", "/var/spool/cron/crontabs")


def collect_user_crontabs() -> str:
    """List per-user crontabs from the spool (root) or the current user's."""
    lines = []
    spool_readable = False

    for spool in _SPOOL_DIRS:
        if not os.path.isdir(spool):
            continue
        try:
            users = sorted(os.listdir(spool))
            spool_readable = True
        except PermissionError:
            continue
        for user in users:
            path = os.path.join(spool, user)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r") as f:
                    content = [
                        line for line in f.read().splitlines()
                        if line.strip() and not line.strip().startswith("#")
                    ]
                lines.append(f"== {user} ({len(content)} entries) ==")
                lines.extend(content[:20])
            except PermissionError:
                lines.append(f"== {user} == (not readable)")

    if lines:
        return "\n".join(lines)

    # Fall back to the current user's own crontab
    suffix = "" if spool_readable else " (spool not readable, showing current user only)"
    try:
        proc = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return f"Current user crontab{suffix}:\n{proc.stdout.strip()}"
        return f"No user crontabs found{suffix}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return f"No user crontabs found, crontab command unavailable{suffix}"
