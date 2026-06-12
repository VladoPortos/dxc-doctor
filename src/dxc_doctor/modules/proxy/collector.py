"""Python collectors for proxy module."""

from __future__ import annotations

import os


def collect_env_proxy() -> str:
    """Collect proxy-related environment variables."""
    proxy_vars = [
        "HTTP_PROXY", "http_proxy",
        "HTTPS_PROXY", "https_proxy",
        "NO_PROXY", "no_proxy",
        "FTP_PROXY", "ftp_proxy",
        "ALL_PROXY", "all_proxy",
    ]
    results = []
    found = False
    for var in proxy_vars:
        val = os.environ.get(var)
        if val:
            results.append(f"{var}={val}")
            found = True

    if not found:
        return "No proxy environment variables configured"
    return "\n".join(results)


def check_proxy_connectivity() -> str:
    """Test HTTPS connectivity through proxy if configured."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not proxy:
        return "No proxy configured, skipping connectivity test"

    results = [f"Using proxy: {proxy}"]
    test_url = "https://www.google.com"
    try:
        import urllib.request
        req = urllib.request.Request(test_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            results.append(f"OK: {test_url} -> HTTP {resp.status}")
    except Exception as e:
        results.append(f"FAIL: {test_url} -> {e}")

    return "\n".join(results)
