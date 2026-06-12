"""Python collectors for kernel module."""

from __future__ import annotations


def collect_sysctl_values() -> str:
    """Read key sysctl values from /proc/sys/."""
    keys = {
        "vm.swappiness": "/proc/sys/vm/swappiness",
        "vm.overcommit_memory": "/proc/sys/vm/overcommit_memory",
        "vm.dirty_ratio": "/proc/sys/vm/dirty_ratio",
        "fs.file-max": "/proc/sys/fs/file-max",
        "fs.nr_open": "/proc/sys/fs/nr_open",
        "net.ipv4.ip_forward": "/proc/sys/net/ipv4/ip_forward",
        "net.ipv4.tcp_syncookies": "/proc/sys/net/ipv4/tcp_syncookies",
        "net.core.somaxconn": "/proc/sys/net/core/somaxconn",
        "kernel.pid_max": "/proc/sys/kernel/pid_max",
        "kernel.threads-max": "/proc/sys/kernel/threads-max",
    }
    results = []
    for name, path in sorted(keys.items()):
        try:
            with open(path, "r") as f:
                val = f.read().strip()
            results.append(f"{name} = {val}")
        except (FileNotFoundError, PermissionError):
            results.append(f"{name} = (not available)")

    return "\n".join(results)


# Tainted flag definitions from kernel documentation
_TAINT_FLAGS = {
    0: "G/P - Proprietary module loaded",
    1: "F - Module force loaded",
    2: "S - Kernel running on out-of-spec system",
    3: "R - Module force unloaded",
    4: "M - Machine check exception occurred",
    5: "B - Bad page referenced",
    6: "U - User request taint",
    7: "D - Kernel died recently (OOPS/BUG)",
    8: "A - ACPI table overridden",
    9: "W - Warning issued",
    10: "C - Staging driver loaded",
    11: "I - Workaround for platform firmware bug applied",
    12: "O - Out-of-tree module loaded",
    13: "E - Unsigned module loaded",
    14: "L - Soft lockup occurred",
    15: "K - Kernel live patched",
    16: "X - Auxiliary taint",
    17: "T - Built with struct randomization",
}


def decode_tainted_flags() -> str:
    """Parse /proc/sys/kernel/tainted and decode the bitmask."""
    try:
        with open("/proc/sys/kernel/tainted", "r") as f:
            value = int(f.read().strip())
    except (FileNotFoundError, PermissionError):
        return "Tainted flags not available"

    if value == 0:
        return "Kernel is not tainted (value: 0)"

    results = [f"Tainted value: {value}"]
    for bit, desc in sorted(_TAINT_FLAGS.items()):
        if value & (1 << bit):
            results.append(f"  Bit {bit}: {desc}")

    return "\n".join(results)
