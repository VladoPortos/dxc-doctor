"""Python collectors for filesystem module."""

from __future__ import annotations

import os


def check_readonly_mounts() -> str:
    """Parse /proc/mounts to find read-only mounted filesystems."""
    lines = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                device, mountpoint, fstype, options = parts[0], parts[1], parts[2], parts[3]
                opts = options.split(",")
                if "ro" in opts:
                    lines.append(f"RO: {mountpoint} ({fstype}) on {device}")
    except FileNotFoundError:
        return "/proc/mounts not available"

    if not lines:
        return "No read-only mounts detected"
    return "\n".join(lines)


def check_stale_mounts() -> str:
    """Try os.statvfs() on each mount point to detect stale/hung mounts."""
    results = []
    try:
        with open("/proc/mounts", "r") as f:
            mounts = f.readlines()
    except FileNotFoundError:
        return "/proc/mounts not available"

    for line in mounts:
        parts = line.split()
        if len(parts) < 2:
            continue
        mountpoint = parts[1]
        # Skip pseudo-filesystems
        if mountpoint.startswith(("/proc", "/sys", "/dev", "/run")):
            continue
        try:
            os.statvfs(mountpoint)
            results.append(f"OK:   {mountpoint}")
        except OSError as e:
            results.append(f"STALE: {mountpoint} ({e})")

    if not results:
        return "No mountpoints to check"
    return "\n".join(results)
