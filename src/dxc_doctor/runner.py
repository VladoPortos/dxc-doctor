"""Execute diagnostic checks and report progress."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .models import CheckDefinition, CheckResult, PluginManifest
from .plugin_manager import discover_plugins, load_collector
from .report import create_zip, write_report

DEFAULT_CHECK_TIMEOUT = 30

# Number of modules executed concurrently. Checks inside a module always run
# sequentially (in manifest order) so checks that share state — e.g. package
# manager metadata locks — never race against each other.
MODULE_WORKERS = 4

# Text heuristics applied only when a command exits 0 and the check does not
# define its own severity rules. Exit codes are the primary signal.
_WARNING_PATTERNS = (
    "permission denied",
    "running as a non-root",
    "not permitted",
    "access denied",
    "operation not permitted",
)


class CheckTimeout(Exception):
    """A check exceeded its timeout."""


def _classify(check: CheckDefinition, stdout: str, stderr: str,
              returncode: int | None) -> str:
    """Classify a check result.

    Order of precedence:
    1. Per-check severity rules from plugin.yaml (first regex match wins).
    2. Exit code: non-zero -> error.
    3. stderr with empty stdout -> warning.
    4. Built-in warning text heuristics (skipped when the check defines
       severity rules, even an empty list).
    """
    combined = stdout + "\n" + stderr
    if check.severity is not None:
        for rule in check.severity:
            if re.search(rule.pattern, combined, re.IGNORECASE):
                return rule.status
        if returncode is not None and returncode != 0:
            return "error"
        return "ok"

    if returncode is not None and returncode != 0:
        return "error"
    if stderr and not stdout:
        return "warning"
    lowered = combined.lower()
    for pat in _WARNING_PATTERNS:
        if pat in lowered:
            return "warning"
    return "ok"


def _run_command(command: str, timeout: int) -> tuple[str, str, int]:
    """Run a shell command and return (stdout, stderr, returncode).

    stdin is connected to /dev/null so no command can ever prompt for a
    password or interactive input (which would break the TUI).

    The command runs in its own session (process group). On timeout the
    whole group is killed — plain Popen.kill() only kills the shell and
    leaves grandchildren holding the output pipes, which would hang the
    subsequent read forever.
    """
    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        raise CheckTimeout(f"Timed out after {timeout}s")
    return stdout.strip(), stderr.strip(), proc.returncode


def _read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, "r") as f:
        return f.read().strip()


def _call_with_timeout(func: Callable[[], str], timeout: int) -> str:
    """Call a python collector function with a timeout.

    Runs the function in a daemon thread; if it does not finish in time a
    CheckTimeout is raised. The thread itself cannot be killed (it may be
    stuck in an uninterruptible syscall like statvfs on a dead NFS mount),
    but being a daemon it never blocks the rest of the run or process exit.
    """
    outcome: dict = {}

    def target() -> None:
        try:
            outcome["output"] = func()
        except BaseException as e:  # noqa: BLE001 - re-raised in caller
            outcome["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise CheckTimeout(f"Timed out after {timeout}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("output", "")


def execute_check(check: CheckDefinition, collector_module) -> CheckResult:
    """Execute a single check and return the result."""
    start = time.time()
    result = CheckResult(name=check.name, label=check.label)
    timeout = check.timeout or DEFAULT_CHECK_TIMEOUT

    try:
        if check.type == "command":
            stdout, stderr, returncode = _run_command(check.command, timeout)
            result.output = stdout
            result.returncode = returncode
            if stderr:
                result.error = stderr
            result.status = _classify(check, stdout, stderr, returncode)

        elif check.type == "file":
            try:
                result.output = _read_file(check.path)
                result.status = _classify(check, result.output, "", None)
            except PermissionError:
                result.status = "error"
                result.error = f"Permission denied: {check.path}"
            except FileNotFoundError:
                result.status = "warning"
                result.error = f"File not found: {check.path}"

        elif check.type == "python":
            if collector_module is None:
                result.status = "error"
                result.error = "Collector module not found"
            else:
                func = getattr(collector_module, check.function, None)
                if func is None:
                    result.status = "error"
                    result.error = f"Function '{check.function}' not found in collector"
                else:
                    result.output = _call_with_timeout(func, timeout)
                    result.status = _classify(check, result.output, "", None)

        else:
            result.status = "skipped"
            result.error = f"Unknown check type: {check.type}"

    except CheckTimeout as e:
        result.status = "error"
        result.error = str(e)
    except Exception as e:
        result.status = "error"
        result.error = str(e)

    result.duration = time.time() - start
    return result


def run_selected_plugins_sync(
    plugins: list[PluginManifest],
    on_check_start: Callable | None = None,
    on_check_done: Callable | None = None,
    max_workers: int = MODULE_WORKERS,
) -> dict[str, list[CheckResult]]:
    """Run the selected plugins, several modules in parallel.

    Checks within a module run sequentially in manifest order. Results are
    returned keyed by plugin name in the original selection order regardless
    of completion order. Callbacks are invoked from worker threads — TUI
    callers must marshal back with call_from_thread.
    """
    all_results: dict[str, list[CheckResult]] = {p.name: [] for p in plugins}

    def run_one_plugin(plugin: PluginManifest) -> None:
        collector = load_collector(plugin.name)
        for check in plugin.checks:
            if on_check_start:
                on_check_start(plugin.name, check)
            result = execute_check(check, collector)
            all_results[plugin.name].append(result)
            if on_check_done:
                on_check_done(plugin.name, result)

    workers = max(1, min(max_workers, len(plugins)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_one_plugin, p) for p in plugins]
        for future in futures:
            future.result()

    return all_results


def run_batch(args) -> None:
    """Run in batch mode (no TUI)."""
    plugins = discover_plugins()

    if args.modules:
        # Explicitly named modules run even when not detected — the user
        # asked for them. Warn so a typo or missing tool is visible.
        selected_names = [m.strip() for m in args.modules.split(",")]
        unknown = [n for n in selected_names if n not in {p.name for p in plugins}]
        for name in unknown:
            print(f"Warning: unknown module '{name}' ignored", file=sys.stderr)
        plugins = [p for p in plugins if p.name in selected_names]
        for p in plugins:
            if not p.detected:
                print(
                    f"Warning: module '{p.name}' is {p.disabled_reason or 'not detected'}"
                    " — running anyway as explicitly requested",
                    file=sys.stderr,
                )
    else:
        # Default run: skip modules whose tooling is absent or that need
        # root we don't have, matching what the TUI offers.
        skipped = [p for p in plugins if not p.detected]
        plugins = [p for p in plugins if p.detected]
        for p in skipped:
            print(
                f"Skipping module '{p.name}' ({p.disabled_reason or 'not detected'})",
                file=sys.stderr,
            )

    if not plugins:
        print(json.dumps({"error": "No matching modules found"}))
        sys.exit(1)

    all_results = run_selected_plugins_sync(plugins)

    write_report(all_results, args.output, {p.name: p for p in plugins})

    if not args.no_zip:
        zip_path = create_zip(args.output)
        print(f"ZIP file: {zip_path}", file=sys.stderr)

    # Print JSON summary to stdout. Output is truncated to 200 chars per
    # check here — full output lives in summary.json and the per-check files.
    summary = {}
    for plugin_name, results in all_results.items():
        summary[plugin_name] = [
            {
                "name": r.name,
                "label": r.label,
                "status": r.status,
                "output": r.output[:200],
                "error": r.error,
                "returncode": r.returncode,
                "duration": round(r.duration, 3),
            }
            for r in results
        ]
    print(json.dumps(summary, indent=2))
