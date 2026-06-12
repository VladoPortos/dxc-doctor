"""Python-based collectors for OS info module."""

from __future__ import annotations

import os


def collect_cpu() -> str:
    """Collect CPU information from /proc/cpuinfo."""
    lines = []
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()

        model = ""
        cores = 0
        for line in cpuinfo.splitlines():
            if line.startswith("model name") and not model:
                model = line.split(":", 1)[1].strip()
            if line.startswith("processor"):
                cores += 1

        lines.append(f"Model: {model}")
        lines.append(f"Logical CPUs: {cores}")
    except FileNotFoundError:
        lines.append("CPU info not available (/proc/cpuinfo not found)")

    try:
        load = os.getloadavg()
        lines.append(f"Load average: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
    except OSError:
        pass

    return "\n".join(lines)


def collect_memory() -> str:
    """Collect memory information from /proc/meminfo."""
    lines = []
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        fields = {}
        for line in meminfo.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                fields[key] = val

        for key in ["MemTotal", "MemFree", "MemAvailable", "SwapTotal", "SwapFree", "Buffers", "Cached"]:
            if key in fields:
                lines.append(f"{key}: {fields[key]}")

    except FileNotFoundError:
        lines.append("Memory info not available (/proc/meminfo not found)")

    return "\n".join(lines)
