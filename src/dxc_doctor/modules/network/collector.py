"""Python collectors for network module."""

import socket
import subprocess


def check_connectivity() -> str:
    """Check connectivity to common endpoints."""
    results = []
    targets = [
        ("google.com", 443),
        ("github.com", 443),
    ]

    for host, port in targets:
        try:
            addr = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
            results.append(f"OK:   {host} -> {addr}")
        except socket.gaierror:
            results.append(f"FAIL: {host} -> DNS resolution failed")

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            results.append("OK:   ping 8.8.8.8")
        else:
            results.append("FAIL: ping 8.8.8.8")
    except Exception:
        results.append("FAIL: ping 8.8.8.8 (timeout or not available)")

    return "\n".join(results)


def collect_interface_stats() -> str:
    """Parse /proc/net/dev for interface RX/TX stats."""
    lines = []
    try:
        with open("/proc/net/dev", "r") as f:
            raw = f.readlines()

        for line in raw[2:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            iface = parts[0].rstrip(":")
            rx_bytes = int(parts[1])
            tx_bytes = int(parts[9])
            rx_mb = rx_bytes / (1024 * 1024)
            tx_mb = tx_bytes / (1024 * 1024)
            lines.append(f"{iface}: RX {rx_mb:.1f} MB, TX {tx_mb:.1f} MB")
    except FileNotFoundError:
        lines.append("Interface stats not available")

    return "\n".join(lines)
