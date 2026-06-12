"""Core tests for DXC Doctor."""

import json
import os
import subprocess
import sys
import textwrap
import time
import types

import yaml

from dxc_doctor.models import CheckDefinition, CheckResult, PluginManifest, SeverityRule
from dxc_doctor.plugin_manager import discover_plugins, load_collector
from dxc_doctor.runner import execute_check, run_selected_plugins_sync
from dxc_doctor.report import write_report


def test_discover_plugins():
    plugins = discover_plugins()
    assert len(plugins) >= 1
    names = [p.name for p in plugins]
    assert "os_info" in names


def test_plugin_manifest_from_dict():
    data = {
        "name": "test",
        "label": "Test Plugin",
        "description": "A test",
        "checks": [
            {"name": "echo_test", "label": "Echo", "type": "command", "command": "echo hello"},
        ],
    }
    manifest = PluginManifest.from_dict(data)
    assert manifest.name == "test"
    assert len(manifest.checks) == 1
    assert manifest.checks[0].type == "command"


def test_plugin_manifest_enabled_default():
    data = {"name": "t", "label": "T", "description": "d", "checks": []}
    manifest = PluginManifest.from_dict(data)
    assert manifest.enabled is True
    assert manifest.detect == ""
    assert manifest.detected is True


def test_plugin_manifest_enabled_false():
    data = {"name": "t", "label": "T", "description": "d", "enabled": False, "checks": []}
    manifest = PluginManifest.from_dict(data)
    assert manifest.enabled is False


def test_execute_command_check():
    check = CheckDefinition(name="test", label="Test", type="command", command="echo hello")
    result = execute_check(check, None)
    assert result.status == "ok"
    assert result.output == "hello"


def test_execute_file_check():
    check = CheckDefinition(name="test", label="Test", type="file", path="/etc/os-release")
    result = execute_check(check, None)
    assert result.status == "ok"
    assert len(result.output) > 0


def test_execute_file_check_missing():
    check = CheckDefinition(name="test", label="Test", type="file", path="/nonexistent/file")
    result = execute_check(check, None)
    assert result.status == "warning"


def test_execute_python_check():
    collector = load_collector("os_info")
    assert collector is not None
    check = CheckDefinition(name="test", label="Test", type="python", function="collect_cpu")
    result = execute_check(check, collector)
    assert result.status == "ok"
    assert "CPU" in result.output or "Model" in result.output


def test_write_report(tmp_path):
    results = {
        "test_plugin": [
            CheckResult(name="c1", label="Check 1", status="ok", output="data"),
            CheckResult(name="c2", label="Check 2", status="warning", error="minor issue"),
        ]
    }
    plugins = {
        "test_plugin": PluginManifest(name="test_plugin", label="Test", description="test"),
    }
    out = str(tmp_path / "report")
    write_report(results, out, plugins)

    assert os.path.exists(os.path.join(out, "summary.json"))
    assert os.path.exists(os.path.join(out, "summary.txt"))
    assert os.path.exists(os.path.join(out, "test_plugin", "c1.txt"))

    assert os.path.exists(os.path.join(out, "report.html"))
    with open(os.path.join(out, "report.html")) as f:
        html_content = f.read()
    assert "<!DOCTYPE html>" in html_content
    assert "Check 1" in html_content


def _make_module(tmp_path, name, yaml_content):
    """Helper to create a temporary module directory with plugin.yaml."""
    mod_dir = tmp_path / name
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("")
    (mod_dir / "plugin.yaml").write_text(textwrap.dedent(yaml_content))
    return mod_dir


def test_disabled_plugin_skipped(tmp_path, monkeypatch):
    """Plugin with enabled: false should not appear in discover results."""
    _make_module(tmp_path, "hidden_mod", """\
        name: hidden_mod
        label: "Hidden"
        description: "Should not appear"
        enabled: false
        checks:
          - name: c1
            label: "C1"
            type: command
            command: "echo hi"
    """)
    _make_module(tmp_path, "visible_mod", """\
        name: visible_mod
        label: "Visible"
        description: "Should appear"
        checks:
          - name: c1
            label: "C1"
            type: command
            command: "echo hi"
    """)
    monkeypatch.setattr("dxc_doctor.plugin_manager._get_modules_dir", lambda: tmp_path)
    plugins = discover_plugins()
    names = [p.name for p in plugins]
    assert "hidden_mod" not in names
    assert "visible_mod" in names


def test_detect_failing_command(tmp_path, monkeypatch):
    """Plugin with a failing detect command should have detected=False."""
    _make_module(tmp_path, "fail_detect", """\
        name: fail_detect
        label: "Fail Detect"
        description: "Detect fails"
        detect: "false"
        checks:
          - name: c1
            label: "C1"
            type: command
            command: "echo hi"
    """)
    monkeypatch.setattr("dxc_doctor.plugin_manager._get_modules_dir", lambda: tmp_path)
    plugins = discover_plugins()
    assert len(plugins) == 1
    assert plugins[0].detected is False


def test_detect_passing_command(tmp_path, monkeypatch):
    """Plugin with a passing detect command should have detected=True."""
    _make_module(tmp_path, "pass_detect", """\
        name: pass_detect
        label: "Pass Detect"
        description: "Detect passes"
        detect: "true"
        checks:
          - name: c1
            label: "C1"
            type: command
            command: "echo hi"
    """)
    monkeypatch.setattr("dxc_doctor.plugin_manager._get_modules_dir", lambda: tmp_path)
    plugins = discover_plugins()
    assert len(plugins) == 1
    assert plugins[0].detected is True


def test_no_detect_always_detected(tmp_path, monkeypatch):
    """Plugin with no detect field should have detected=True."""
    _make_module(tmp_path, "no_detect", """\
        name: no_detect
        label: "No Detect"
        description: "No detect command"
        checks:
          - name: c1
            label: "C1"
            type: command
            command: "echo hi"
    """)
    monkeypatch.setattr("dxc_doctor.plugin_manager._get_modules_dir", lambda: tmp_path)
    plugins = discover_plugins()
    assert len(plugins) == 1
    assert plugins[0].detected is True


def test_generate_html_report():
    """HTML report should be a valid self-contained HTML string."""
    from dxc_doctor.html_report import generate_html_report

    results = {
        "os_info": [
            CheckResult(name="kernel", label="Kernel Version", status="ok", output="6.1.0", duration=0.02),
            CheckResult(name="memory", label="Memory Info", status="warning", output="MemTotal: 8GB", error="Low memory", duration=0.1),
        ],
        "docker": [
            CheckResult(name="version", label="Docker Version", status="error", output="", error="not found", duration=0.5),
        ],
    }
    plugins = {
        "os_info": PluginManifest(name="os_info", label="OS Information", description="OS info", category="system"),
        "docker": PluginManifest(name="docker", label="Docker", description="Docker info", category="containers"),
    }

    html = generate_html_report(results, plugins)

    # Basic structure
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html

    # Content present
    assert "Kernel Version" in html
    assert "Memory Info" in html
    assert "Docker Version" in html
    assert "6.1.0" in html

    # Status indicators present
    assert "ok" in html.lower() or "✓" in html or "#00ff41" in html
    assert "error" in html.lower() or "✗" in html or "#ff4444" in html

    # Category sections
    assert "system" in html.lower()
    assert "containers" in html.lower()

    # Search input exists
    assert 'type="search"' in html or 'type="text"' in html

    # Self-contained (no external links)
    assert "http://" not in html
    assert "https://" not in html


def test_html_report_empty_results():
    """HTML report should handle empty results."""
    from dxc_doctor.html_report import generate_html_report

    html = generate_html_report({}, {})
    assert "<!DOCTYPE html>" in html
    assert "Total: 0" in html


def test_html_report_special_characters():
    """HTML report should escape special characters in output."""
    from dxc_doctor.html_report import generate_html_report

    results = {
        "test": [
            CheckResult(
                name="xss",
                label="XSS <script>alert('xss')</script>",
                status="ok",
                output="<b>bold</b> & 'quotes' \"double\"",
                duration=0.01,
            ),
        ],
    }
    plugins = {
        "test": PluginManifest(name="test", label="Test", description="t", category="system"),
    }

    html = generate_html_report(results, plugins)
    # Script tags must be escaped, not rendered
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;" in html
    assert "&amp;" in html


def test_html_report_large_output():
    """HTML report should handle large check outputs without truncation."""
    from dxc_doctor.html_report import generate_html_report

    big_output = "line {}\n" * 10000
    results = {
        "test": [
            CheckResult(name="big", label="Big Output", status="ok", output=big_output, duration=1.0),
        ],
    }
    plugins = {
        "test": PluginManifest(name="test", label="Test", description="t", category="system"),
    }

    html = generate_html_report(results, plugins)
    assert "Big Output" in html
    # Output should not be truncated
    assert "line {}" in html


# ---------------------------------------------------------------------------
# Classification: exit codes and severity rules
# ---------------------------------------------------------------------------

def test_nonzero_exit_code_is_error():
    check = CheckDefinition(name="t", label="T", type="command", command="exit 3")
    result = execute_check(check, None)
    assert result.status == "error"
    assert result.returncode == 3


def test_zero_exit_code_is_ok():
    check = CheckDefinition(name="t", label="T", type="command", command="echo fine")
    result = execute_check(check, None)
    assert result.status == "ok"
    assert result.returncode == 0


def test_stderr_only_is_warning():
    check = CheckDefinition(name="t", label="T", type="command", command="echo oops >&2")
    result = execute_check(check, None)
    assert result.status == "warning"


def test_heuristic_warning_on_permission_denied_text():
    check = CheckDefinition(name="t", label="T", type="command",
                            command="echo 'bash: permission denied'")
    result = execute_check(check, None)
    assert result.status == "warning"


def test_empty_severity_disables_heuristics():
    """severity: [] means exit-code-only classification."""
    check = CheckDefinition(name="t", label="T", type="command",
                            command="echo 'bash: permission denied'", severity=[])
    result = execute_check(check, None)
    assert result.status == "ok"


def test_severity_rules_first_match_wins():
    rules = [
        SeverityRule(pattern="CRITICAL", status="error"),
        SeverityRule(pattern="degraded", status="warning"),
    ]
    check = CheckDefinition(name="t", label="T", type="command",
                            command="echo 'array is degraded'", severity=rules)
    result = execute_check(check, None)
    assert result.status == "warning"


def test_severity_rules_fall_back_to_exit_code():
    rules = [SeverityRule(pattern="nomatch_xyz", status="warning")]
    check = CheckDefinition(name="t", label="T", type="command",
                            command="echo hello; exit 2", severity=rules)
    result = execute_check(check, None)
    assert result.status == "error"


def test_manifest_parses_timeout_and_severity():
    data = {
        "name": "t", "label": "T", "description": "d",
        "checks": [
            {"name": "c1", "label": "C1", "type": "command", "command": "true",
             "timeout": 60,
             "severity": [{"pattern": "FAIL", "status": "warning"}]},
            {"name": "c2", "label": "C2", "type": "command", "command": "true",
             "severity": []},
            {"name": "c3", "label": "C3", "type": "command", "command": "true"},
        ],
    }
    manifest = PluginManifest.from_dict(data)
    assert manifest.checks[0].timeout == 60
    assert manifest.checks[0].severity[0].pattern == "FAIL"
    assert manifest.checks[1].severity == []
    assert manifest.checks[2].severity is None
    assert manifest.checks[2].timeout == 30


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

def test_command_timeout():
    check = CheckDefinition(name="t", label="T", type="command",
                            command="sleep 10", timeout=1)
    start = time.time()
    result = execute_check(check, None)
    assert result.status == "error"
    assert "Timed out" in result.error
    assert time.time() - start < 5


def test_command_timeout_kills_grandchildren():
    """A background grandchild holding the output pipe must not hang the read."""
    check = CheckDefinition(name="t", label="T", type="command",
                            command="sleep 30 & sleep 30", timeout=1)
    start = time.time()
    result = execute_check(check, None)
    assert result.status == "error"
    assert time.time() - start < 10


def test_python_check_timeout():
    collector = types.SimpleNamespace(slow=lambda: time.sleep(10) or "done")
    check = CheckDefinition(name="t", label="T", type="python",
                            function="slow", timeout=1)
    start = time.time()
    result = execute_check(check, collector)
    assert result.status == "error"
    assert "Timed out" in result.error
    assert time.time() - start < 5


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

def test_parallel_runner_preserves_order():
    def make_plugin(name, n_checks):
        return PluginManifest(
            name=name, label=name, description="t",
            checks=[
                CheckDefinition(name=f"{name}_c{i}", label=f"C{i}",
                                type="command", command=f"echo {name}-{i}")
                for i in range(n_checks)
            ],
        )

    plugins = [make_plugin("alpha", 3), make_plugin("beta", 2), make_plugin("gamma", 1)]
    results = run_selected_plugins_sync(plugins)

    assert list(results.keys()) == ["alpha", "beta", "gamma"]
    assert [r.name for r in results["alpha"]] == ["alpha_c0", "alpha_c1", "alpha_c2"]
    assert results["beta"][1].output == "beta-1"
    assert all(r.status == "ok" for rs in results.values() for r in rs)


def test_parallel_runner_callbacks():
    plugins = [
        PluginManifest(name="p1", label="P1", description="t", checks=[
            CheckDefinition(name="p1_c", label="C", type="command", command="echo hi"),
        ]),
    ]
    started, done = [], []
    run_selected_plugins_sync(
        plugins,
        on_check_start=lambda p, c: started.append(c.name),
        on_check_done=lambda p, r: done.append(r.name),
    )
    assert started == ["p1_c"]
    assert done == ["p1_c"]


# ---------------------------------------------------------------------------
# Host metadata
# ---------------------------------------------------------------------------

def test_write_report_includes_host_metadata(tmp_path):
    results = {
        "test_plugin": [CheckResult(name="c1", label="C1", status="ok", output="x")],
    }
    plugins = {
        "test_plugin": PluginManifest(name="test_plugin", label="Test", description="t"),
    }
    out = str(tmp_path / "report")
    write_report(results, out, plugins)

    with open(os.path.join(out, "summary.json")) as f:
        summary = json.load(f)
    assert "host" in summary
    assert summary["host"]["hostname"]
    assert summary["host"]["tool_version"]
    assert summary["host"]["kernel"]


def test_html_report_host_metadata_and_filters():
    from dxc_doctor.html_report import generate_html_report

    results = {
        "test": [CheckResult(name="c", label="C", status="ok", output="x", duration=0.1)],
    }
    plugins = {
        "test": PluginManifest(name="test", label="Test", description="t", category="system"),
    }
    host = {"hostname": "srv-test-01", "os": "TestOS 9", "kernel": "6.1.0",
            "arch": "x86_64", "user": "tester", "tool_version": "0.1.0"}

    html = generate_html_report(results, plugins, host_meta=host)
    assert "srv-test-01" in html
    assert "TestOS 9" in html
    assert "filter-chip" in html
    assert 'data-status="error"' in html or 'data-status="ok"' in html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_list_modules_cli():
    proc = subprocess.run(
        [sys.executable, "-m", "dxc_doctor", "--list-modules"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0
    listing = json.loads(proc.stdout)
    names = [m["name"] for m in listing]
    assert "os_info" in names
    assert all("detected" in m and "category" in m for m in listing)
