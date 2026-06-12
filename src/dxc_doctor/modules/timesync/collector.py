"""Python collectors for timesync module."""

from __future__ import annotations

import subprocess
import time


def check_clock_drift() -> str:
    """Compare system clock to RTC if available."""
    results = []

    # Try reading RTC time
    try:
        result = subprocess.run(
            ["hwclock", "--show"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            results.append(f"RTC time: {result.stdout.strip()}")
        else:
            results.append("hwclock not available or no RTC")
    except Exception:
        results.append("hwclock not available")

    # Show current system time with nanoseconds
    now = time.time()
    local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now))
    results.append(f"System time (local): {local}")
    results.append(f"System time (UTC):   {utc}")

    # Try reading adjtime for drift info
    try:
        with open("/etc/adjtime", "r") as f:
            results.append(f"Adjtime: {f.read().strip()}")
    except (FileNotFoundError, PermissionError):
        pass

    return "\n".join(results)
