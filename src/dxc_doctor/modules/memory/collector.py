"""Python collectors for memory module."""

from __future__ import annotations

import glob
import os


def collect_hugepages() -> str:
    """Parse hugepage settings from /proc/meminfo and /sys/kernel/mm/hugepages/."""
    results = []

    # From /proc/meminfo
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "huge" in line.lower():
                    results.append(line.strip())
    except FileNotFoundError:
        results.append("/proc/meminfo not available")

    # From sysfs
    hp_base = "/sys/kernel/mm/hugepages"
    if os.path.isdir(hp_base):
        for hp_dir in sorted(glob.glob(f"{hp_base}/hugepages-*")):
            size = os.path.basename(hp_dir)
            entries = {}
            for fname in ["nr_hugepages", "free_hugepages", "surplus_hugepages"]:
                fpath = os.path.join(hp_dir, fname)
                try:
                    with open(fpath, "r") as f:
                        entries[fname] = f.read().strip()
                except (FileNotFoundError, PermissionError):
                    pass
            if entries:
                parts = [f"{k}={v}" for k, v in entries.items()]
                results.append(f"{size}: {', '.join(parts)}")
    else:
        results.append("Hugepages sysfs not available")

    if not results:
        return "No hugepage information found"
    return "\n".join(results)
