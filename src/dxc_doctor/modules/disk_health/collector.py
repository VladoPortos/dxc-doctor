"""Python collectors for disk_health module."""

from __future__ import annotations

import os
import subprocess

# Disk name prefixes worth a SMART query (skips loop, ram, dm-, zram, sr)
_DISK_PREFIXES = ("sd", "hd", "vd", "xvd", "nvme")


def _physical_disks() -> list[str]:
    """Return /dev paths of physical-looking block devices."""
    disks = []
    try:
        for name in sorted(os.listdir("/sys/block")):
            if name.startswith(_DISK_PREFIXES):
                disks.append(f"/dev/{name}")
    except OSError:
        pass
    return disks


def collect_smart_health() -> str:
    """Run smartctl -H against every physical disk."""
    disks = _physical_disks()
    if not disks:
        return "No physical disks found under /sys/block"

    results = []
    for disk in disks:
        try:
            proc = subprocess.run(
                ["smartctl", "-H", disk],
                capture_output=True, text=True, timeout=20,
            )
        except FileNotFoundError:
            return "smartctl not installed (install smartmontools)"
        except subprocess.TimeoutExpired:
            results.append(f"ATTENTION: {disk}: smartctl timed out")
            continue

        out = (proc.stdout + proc.stderr).lower()
        if "passed" in out or "smart health status: ok" in out:
            results.append(f"OK: {disk}: SMART health PASSED")
        elif "failed" in out:
            results.append(f"ATTENTION: {disk}: SMART health FAILED")
        elif "unable to detect device type" in out or "open device" in out:
            results.append(f"{disk}: not SMART-capable or not accessible")
        else:
            summary = proc.stdout.strip().splitlines()
            tail = summary[-1] if summary else "no output"
            results.append(f"{disk}: {tail}")

    return "\n".join(results)
