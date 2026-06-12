"""Python collectors for limits module."""

from __future__ import annotations


def collect_fd_usage() -> str:
    """Report system-wide file descriptor usage from /proc/sys/fs."""
    lines = []
    try:
        with open("/proc/sys/fs/file-nr", "r") as f:
            parts = f.read().split()
        allocated = int(parts[0])
        maximum = int(parts[2])
        pct = (allocated / maximum * 100) if maximum else 0.0
        lines.append(f"Allocated file handles: {allocated}")
        lines.append(f"Maximum file handles:   {maximum}")
        flag = "HIGH: " if pct >= 80 else ""
        lines.append(f"{flag}Usage: {pct:.1f}%")
    except (OSError, ValueError, IndexError):
        lines.append("/proc/sys/fs/file-nr not available")

    try:
        with open("/proc/sys/fs/nr_open", "r") as f:
            lines.append(f"Per-process fd limit (nr_open): {f.read().strip()}")
    except OSError:
        pass

    return "\n".join(lines)
