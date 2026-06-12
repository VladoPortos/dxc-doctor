"""Auto-discover and load plugin modules."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml

from .models import PluginManifest

DETECT_TIMEOUT = 10
DETECT_WORKERS = 8


def _get_modules_dir() -> Path:
    """Return the path to the modules directory."""
    return Path(__file__).parent / "modules"


def _validate_unique_check_names(plugins: list[PluginManifest]) -> None:
    """Warn about duplicate check names across modules.

    Check names are used as widget IDs in the TUI, so duplicates cause
    crashes.  This prints clear warnings pointing at the offending modules
    so developers can fix them quickly.
    """
    seen: dict[str, str] = {}  # check_name -> module_name
    for plugin in plugins:
        for check in plugin.checks:
            if check.name in seen:
                print(
                    f"WARNING: Duplicate check name '{check.name}' "
                    f"found in module '{plugin.name}' — already defined "
                    f"in module '{seen[check.name]}'. "
                    f"Rename it in {plugin.name}/plugin.yaml to avoid "
                    f"TUI crashes.",
                    file=sys.stderr,
                )
            else:
                seen[check.name] = plugin.name


def _run_detect(plugin: PluginManifest) -> None:
    """Run a plugin's detect command and set detected/disabled_reason."""
    try:
        result = subprocess.run(
            plugin.detect, shell=True,
            capture_output=True, timeout=DETECT_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        plugin.detected = result.returncode == 0
        if not plugin.detected:
            plugin.disabled_reason = "not detected"
    except Exception:
        plugin.detected = False
        plugin.disabled_reason = "not detected"


def discover_plugins() -> list[PluginManifest]:
    """Scan modules/ for directories containing plugin.yaml and load them.

    Detect commands run concurrently so startup stays fast even when
    several detect commands are slow or time out.
    """
    modules_dir = _get_modules_dir()
    plugins = []
    is_root = os.geteuid() == 0

    if not modules_dir.is_dir():
        return plugins

    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "plugin.yaml"
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, "r") as f:
                data = yaml.safe_load(f)
            plugin = PluginManifest.from_dict(data)
            if not plugin.enabled:
                continue
            if plugin.requires_root and not is_root:
                plugin.detected = False
                plugin.disabled_reason = "requires root"
            plugins.append(plugin)
        except Exception as e:
            print(
                f"Warning: Failed to load plugin from {entry.name}: {e}",
                file=sys.stderr,
            )

    to_detect = [p for p in plugins if p.detect and not p.disabled_reason]
    if to_detect:
        workers = max(1, min(DETECT_WORKERS, len(to_detect)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_run_detect, to_detect))

    _validate_unique_check_names(plugins)
    return plugins


def load_collector(plugin_name: str) -> Any | None:
    """Dynamically import a plugin's collector module."""
    try:
        module = importlib.import_module(f".modules.{plugin_name}.collector", package="dxc_doctor")
        return module
    except ImportError:
        return None
