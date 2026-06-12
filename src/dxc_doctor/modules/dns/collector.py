"""Python collectors for DNS module."""

from __future__ import annotations

import socket
import time


def resolve_test() -> str:
    """Resolve common hostnames and measure latency."""
    targets = [
        "google.com",
        "github.com",
        "dns.google",
        "cloudflare.com",
    ]
    results = []
    for host in targets:
        start = time.monotonic()
        try:
            addrs = socket.getaddrinfo(host, None, socket.AF_UNSPEC)
            elapsed = (time.monotonic() - start) * 1000
            ip = addrs[0][4][0]
            results.append(f"OK:   {host} -> {ip} ({elapsed:.1f} ms)")
        except socket.gaierror as e:
            elapsed = (time.monotonic() - start) * 1000
            results.append(f"FAIL: {host} -> {e} ({elapsed:.1f} ms)")

    return "\n".join(results)
