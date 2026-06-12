"""Python collectors for processes module."""

from __future__ import annotations

import os


def _iter_proc_stats():
    """Yield (pid, comm, state) for every process in /proc."""
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "r") as f:
                raw = f.read()
        except OSError:
            continue  # process exited or not readable
        # comm is parenthesised and may contain spaces/parens itself
        close = raw.rfind(")")
        if close == -1:
            continue
        comm = raw[raw.find("(") + 1:close]
        rest = raw[close + 2:].split()
        if not rest:
            continue
        yield entry, comm, rest[0]


def collect_process_states() -> str:
    """Count process states and list zombies and D-state processes.

    D-state (uninterruptible sleep) processes are the classic symptom of
    hung storage (NFS, dead disks). Zombies indicate a parent not reaping
    children.
    """
    counts: dict[str, int] = {}
    zombies: list[str] = []
    blocked: list[str] = []

    for pid, comm, state in _iter_proc_stats():
        counts[state] = counts.get(state, 0) + 1
        if state == "Z":
            zombies.append(f"  ZOMBIE: pid={pid} ({comm})")
        elif state == "D":
            blocked.append(f"  BLOCKED: pid={pid} ({comm}) - uninterruptible sleep")

    if not counts:
        return "/proc not available"

    lines = ["State counts: " + ", ".join(
        f"{state}={count}" for state, count in sorted(counts.items())
    )]
    if blocked:
        lines.append("")
        lines.append(f"{len(blocked)} process(es) in D-state (possible hung I/O):")
        lines.extend(blocked[:20])
    if zombies:
        lines.append("")
        lines.append(f"{len(zombies)} zombie process(es):")
        lines.extend(zombies[:20])
    if not blocked and not zombies:
        lines.append("No zombie or D-state processes.")

    return "\n".join(lines)
