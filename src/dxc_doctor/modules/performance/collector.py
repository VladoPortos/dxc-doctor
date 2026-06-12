"""Python collectors for performance module."""

from __future__ import annotations

import os

# avg60 "some" percentage above which a resource is flagged as under pressure
_PRESSURE_THRESHOLD = 10.0


def collect_pressure() -> str:
    """Read pressure stall information from /proc/pressure/ (kernel 4.20+).

    PSI shows the share of wall-clock time tasks were stalled waiting for a
    resource. avg60 'some' above ~10% indicates sustained contention.
    """
    base = "/proc/pressure"
    if not os.path.isdir(base):
        return "PSI not available (kernel < 4.20 or psi=0 boot option)"

    lines = []
    for resource in ("cpu", "memory", "io"):
        path = os.path.join(base, resource)
        try:
            with open(path, "r") as f:
                content = f.read().strip()
        except OSError:
            continue

        flag = ""
        for line in content.splitlines():
            if line.startswith("some"):
                for token in line.split():
                    if token.startswith("avg60="):
                        try:
                            if float(token.split("=", 1)[1]) >= _PRESSURE_THRESHOLD:
                                flag = "ELEVATED: "
                        except ValueError:
                            pass
        lines.append(f"{flag}{resource}:")
        for line in content.splitlines():
            lines.append(f"  {line}")

    if not lines:
        return "PSI files not readable"
    return "\n".join(lines)
