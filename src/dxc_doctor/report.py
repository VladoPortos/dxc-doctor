"""Write collected diagnostic data to output folder."""

from __future__ import annotations

import json
import os
import platform
import socket
import zipfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .models import CheckResult, PluginManifest
from .html_report import generate_html_report


def collect_host_metadata() -> dict:
    """Collect basic facts about the host the report was generated on.

    Deliberately avoids anything that can block (DNS lookups, subprocesses):
    this must work even on a badly broken server.
    """
    meta = {
        "hostname": "",
        "os": "",
        "kernel": "",
        "arch": "",
        "user": "",
        "tool_version": __version__,
    }
    try:
        meta["hostname"] = socket.gethostname()
    except OSError:
        pass
    try:
        meta["kernel"] = platform.release()
        meta["arch"] = platform.machine()
    except OSError:
        pass
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    meta["os"] = line.split("=", 1)[1].strip().strip('"')
                    break
    except OSError:
        pass
    try:
        import getpass
        meta["user"] = getpass.getuser()
    except Exception:
        pass
    return meta


def write_report(
    all_results: dict[str, list[CheckResult]],
    output_dir: str,
    plugins: dict[str, PluginManifest],
) -> str:
    """Write all results to the output directory. Returns the output path."""
    os.makedirs(output_dir, exist_ok=True)

    # Write per-plugin results
    for plugin_name, results in all_results.items():
        plugin_dir = os.path.join(output_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)

        for result in results:
            content = result.output if result.output else result.error
            filepath = os.path.join(plugin_dir, f"{result.name}.txt")
            with open(filepath, "w") as f:
                f.write(content + "\n")

    # Build summary
    total = 0
    ok_count = 0
    warn_count = 0
    error_count = 0
    skipped_count = 0
    checks_summary = []

    for plugin_name, results in all_results.items():
        plugin_label = plugins[plugin_name].label if plugin_name in plugins else plugin_name
        for r in results:
            total += 1
            if r.status == "ok":
                ok_count += 1
            elif r.status == "warning":
                warn_count += 1
            elif r.status == "error":
                error_count += 1
            else:
                skipped_count += 1
            checks_summary.append({
                "plugin": plugin_name,
                "name": r.name,
                "label": r.label,
                "status": r.status,
                "output": r.output,
                "error": r.error,
                "returncode": r.returncode,
                "duration": round(r.duration, 3),
            })

    host_meta = collect_host_metadata()

    summary_data = {
        "timestamp": datetime.now().isoformat(),
        "host": host_meta,
        "total_checks": total,
        "ok": ok_count,
        "warnings": warn_count,
        "errors": error_count,
        "skipped": skipped_count,
        "checks": checks_summary,
    }

    # Write JSON summary
    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary_data, f, indent=2)

    # Write human-readable summary
    lines = [
        "DXC Doctor Report",
        f"Generated: {summary_data['timestamp']}",
        f"Host: {host_meta['hostname']}  ({host_meta['os']}, kernel {host_meta['kernel']}, {host_meta['arch']})",
        f"Run by: {host_meta['user']}  |  dxc-doctor {host_meta['tool_version']}",
        "=" * 60,
        f"Total checks: {total}",
        f"  OK:       {ok_count}",
        f"  Warnings: {warn_count}",
        f"  Errors:   {error_count}",
        f"  Skipped:  {skipped_count}",
        "",
        "Details:",
        "-" * 60,
    ]

    for c in checks_summary:
        status_icon = {"ok": "+", "warning": "!", "error": "x", "skipped": "-"}.get(c["status"], "?")
        lines.append(f"  [{status_icon}] {c['label']} ({c['plugin']})")
        if c["error"]:
            lines.append(f"      Error: {c['error']}")

    lines.append("")
    lines.append(f"Output saved to: {output_dir}")

    with open(os.path.join(output_dir, "summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # Write HTML report
    html_content = generate_html_report(all_results, plugins, host_meta=host_meta)
    with open(os.path.join(output_dir, "report.html"), "w") as f:
        f.write(html_content)

    return output_dir


def create_zip(output_dir: str) -> str:
    """Zip the entire output directory into a single file. Returns the zip path."""
    output_path = Path(output_dir)
    zip_path = str(output_path) + ".zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_path.parent)
                zf.write(file_path, arcname)

    return zip_path
