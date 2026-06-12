# Writing Modules for DXC Doctor

This guide explains how to add new diagnostic modules to DXC Doctor. You do **not** need to touch the TUI code. You create a folder, write a YAML file, and optionally a Python file. That's it.

---

## Table of Contents

1. [Quick Start (5-minute version)](#quick-start)
2. [How It Works (the big picture)](#how-it-works)
3. [The plugin.yaml File](#the-pluginyaml-file)
4. [Check Types Explained](#check-types-explained)
5. [Status Classification](#status-classification)
6. [Adding Python Checks](#adding-python-checks)
7. [Module Visibility, Detection, and Root Access](#module-visibility-detection-and-root-access)
8. [Complete Example: Docker Module](#complete-example-docker-module)
9. [Complete Example: Python-Heavy Module](#complete-example-python-heavy-module)
10. [Complete Example: Targeted Kubernetes Inspection](#complete-example-targeted-kubernetes-inspection)
11. [Adding Your Module to the Build](#adding-your-module-to-the-build)
12. [Testing Your Module](#testing-your-module)
13. [Architecture Reference](#architecture-reference)
14. [Rules and Gotchas](#rules-and-gotchas)

---

## Quick Start

**Minimum viable module — just 2 files:**

```bash
mkdir -p src/dxc_doctor/modules/my_module
touch src/dxc_doctor/modules/my_module/__init__.py
```

Create `src/dxc_doctor/modules/my_module/plugin.yaml`:

```yaml
name: my_module
label: "My Module"
description: "Collects something useful."
category: system
checks:
  - name: check_something
    label: "Something"
    type: command
    command: "echo hello world"
```

Done. Run `python -m dxc_doctor` and your module appears as a checkbox under the "System" tab.

---

## How It Works

Here's what happens when DXC Doctor runs, step by step:

```
┌──────────────────────────────────────────────────────────────┐
│                        STARTUP                               │
│                                                              │
│  1. App starts                                               │
│  2. plugin_manager.py scans modules/ directory               │
│  3. Finds folders that contain plugin.yaml                   │
│  4. Loads each plugin.yaml → PluginManifest object           │
│  5. Skips modules with enabled: false                        │
│  6. Marks modules with requires_root: true as disabled       │
│     (if not running as root)                                 │
│  7. Runs detect command → sets detected flag                 │
│  8. Shows tabs in TUI (one per category, checkboxes inside)  │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     USER CLICKS START                        │
│                                                              │
│  9. For each selected module:                                │
│     For each check in the module's plugin.yaml:              │
│                                                              │
│     ┌─────────────────────────────────────────────┐          │
│     │ type: "command"                             │          │
│     │ → runs the shell command                    │          │
│     │ → captures stdout as the result             │          │
│     ├─────────────────────────────────────────────┤          │
│     │ type: "file"                                │          │
│     │ → reads the file at the given path          │          │
│     │ → file contents become the result           │          │
│     ├─────────────────────────────────────────────┤          │
│     │ type: "python"                              │          │
│     │ → imports collector.py from your module     │          │
│     │ → calls the named function                  │          │
│     │ → return value (string) becomes the result  │          │
│     └─────────────────────────────────────────────┘          │
│                                                              │
│  10. Each check produces a CheckResult:                      │
│      - status: "ok", "warning", "error", "skipped"           │
│      - output: the collected data (string)                   │
│      - error: error message if something went wrong          │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      REPORT WRITTEN                          │
│                                                              │
│  11. For each check, output is saved to:                     │
│      /tmp/dxc-doctor-TIMESTAMP/module_name/check_name.txt    │
│                                                              │
│  12. summary.json and summary.txt are generated              │
└──────────────────────────────────────────────────────────────┘
```

### File Discovery

```
src/dxc_doctor/modules/
├── os_info/                  ← plugin_manager finds this folder
│   ├── __init__.py
│   ├── plugin.yaml           ← because it has plugin.yaml
│   └── collector.py          ← loaded only if a check uses type: python
├── docker/                   ← auto-detected module
│   ├── __init__.py
│   └── plugin.yaml           ← has detect: "docker info >/dev/null 2>&1"
├── my_new_module/            ← your new module goes here
│   ├── __init__.py
│   ├── plugin.yaml           ← required
│   └── collector.py          ← optional (only for python-type checks)
```

The plugin manager does **not** need registration. It auto-discovers any folder inside `modules/` that contains a `plugin.yaml`.

---

## The plugin.yaml File

This is the manifest that describes your module and its checks.

```yaml
# REQUIRED fields
name: my_module               # Unique identifier (must match folder name)
label: "My Module"            # Display name shown in the TUI
description: "What this module does"

# OPTIONAL fields (with defaults)
version: "1.0"                # Module version
author: "Your Name"           # Author
requires_root: false          # If true, module is disabled when not running as root
category: system              # Category tab in TUI
                              # Current categories: system, network, containers,
                              #                     security, software, storage, hardware
enabled: true                 # Set to false to hide module from TUI entirely
detect: ""                    # Shell command to detect if tooling is available
                              # If set and fails → module shown grayed out
                              # If not set → module always available

# REQUIRED: list of checks
checks:
  - name: check_name          # Unique within this module, used for filenames
    label: "Check Name"       # Human-readable label shown in progress
    type: command              # One of: command, file, python
    command: "some command"    # (for type: command)
    path: "/some/file"        # (for type: file)
    function: "func_name"     # (for type: python)
    timeout: 30               # OPTIONAL: seconds before the check is killed
    severity:                  # OPTIONAL: custom status classification rules
      - pattern: "FAILED"      #   regex, case-insensitive, searched in output
        status: error          #   first matching rule wins
```

### Field Rules

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | Yes | string | Must match the folder name. Letters, numbers, underscores only. |
| `label` | Yes | string | Shown in the TUI. Can have spaces and special characters. |
| `description` | Yes | string | Shown in tooltips/documentation. |
| `version` | No | string | Default: "1.0" |
| `author` | No | string | Default: "" |
| `requires_root` | No | bool | Default: false. If true and not running as root, module is grayed out with "(requires root)". |
| `category` | No | string | Default: "general". Determines which tab the module appears in. |
| `enabled` | No | bool | Default: true. Set to false to hide the module entirely. |
| `detect` | No | string | Shell command to detect tooling. If it exits non-zero, the module is shown grayed out with "(not detected)". |
| `checks` | Yes | list | At least one check. |
| `checks[].name` | Yes | string | Unique within module. Used as filename for output. |
| `checks[].label` | Yes | string | Shown in progress display. |
| `checks[].type` | Yes | string | One of: `command`, `file`, `python` |
| `checks[].command` | If type=command | string | Shell command to run |
| `checks[].path` | If type=file | string | File path to read |
| `checks[].function` | If type=python | string | Function name in collector.py |
| `checks[].timeout` | No | int | Default: 30. Seconds before the check is killed (applies to all check types). |
| `checks[].severity` | No | list | Custom classification rules — see [Status Classification](#status-classification). |

---

## Check Types Explained

### Type: `command`

Runs a shell command and captures stdout.

```yaml
- name: kernel_version
  label: "Kernel Version"
  type: command
  command: "uname -r"
```

**What happens:**
1. Runs `uname -r` in its own process group (so a timeout kills the whole tree)
2. Captures stdout → becomes `output`, stderr → `error`, exit code → `returncode`
3. Status is classified — see [Status Classification](#status-classification):
   - non-zero exit code → `"error"`
   - stderr with empty stdout → `"warning"`
   - timeout (default 30s, configurable per check) → `"error"`
   - otherwise → `"ok"` (with mild text heuristics for permission problems)

**Tips:**
- Use `2>/dev/null` to suppress expected stderr
- Use `||` for fallbacks: `"ip addr 2>/dev/null || ifconfig -a"`
- Use `2>&1` to include stderr in output: `"docker info 2>&1"`
- End fallback chains with `|| echo 'explanation'` so the exit code is 0 when the situation is expected
- Commands run with the user's permissions (not root unless the binary is run as root)

### Type: `file`

Reads a file and returns its contents.

```yaml
- name: os_release
  label: "OS Release"
  type: file
  path: "/etc/os-release"
```

**What happens:**
1. Opens the file and reads it
2. Contents → `output`, status → `"ok"`
3. `FileNotFoundError` → status `"warning"`, error message
4. `PermissionError` → status `"error"`, error message

### Type: `python`

Calls a function from your module's `collector.py`.

```yaml
- name: memory_info
  label: "Memory Information"
  type: python
  function: "collect_memory"
```

**What happens:**
1. Imports `src/dxc_doctor/modules/YOUR_MODULE/collector.py`
2. Calls `collector.collect_memory()` (no arguments)
3. The function must return a **string**
4. Return value → `output`, status → `"ok"`
5. If function raises an exception → status `"error"`

---

## Status Classification

Every check ends up with a status: `ok`, `warning`, `error`, or `skipped`.

### Default classification (no `severity` field)

1. **Exit code** (command checks): non-zero → `error`
2. **stderr with empty stdout** → `warning`
3. **Text heuristics**: output containing "permission denied", "not permitted",
   "access denied", "operation not permitted" → `warning`
4. Otherwise → `ok`

File checks: `FileNotFoundError` → `warning`, `PermissionError` → `error`.
Python checks: any raised exception → `error`.

### Custom rules (`severity` field)

```yaml
- name: raid_status
  type: command
  command: "cat /proc/mdstat"
  severity:
    - pattern: "degraded"      # regex, case-insensitive
      status: error            # first matching rule wins
    - pattern: "resync"
      status: warning
```

Rules are evaluated in order against the combined stdout + stderr. When no
rule matches, classification falls back to the exit code only (non-zero →
`error`, otherwise `ok`) — the text heuristics are **skipped**.

### Disabling heuristics (`severity: []`)

Checks that intentionally *collect* error text — dmesg scans, journal error
dumps, log greps — would be misclassified by the text heuristics. An empty
list means "exit code only":

```yaml
- name: dmesg_errors
  type: command
  command: "dmesg --level=err | tail -30"
  severity: []
```

### Per-check timeout

```yaml
- name: smart_health
  type: python
  function: "collect_smart_health"
  timeout: 120     # seconds, default 30
```

The timeout applies to all check types. Command checks run in their own
process group and the whole tree is killed on timeout — background children
can't hang the run. Python checks run in a watchdog thread; a stuck function
(e.g. statvfs on a dead NFS mount) is reported as a timeout error and the
run moves on.

---

## Adding Python Checks

When `command` and `file` types aren't enough (e.g., you need to parse data, compute values, or do complex logic), use Python checks.

### Step 1: Add the check to plugin.yaml

```yaml
checks:
  - name: memory_summary
    label: "Memory Summary"
    type: python
    function: "collect_memory_summary"
```

### Step 2: Create collector.py

```python
# src/dxc_doctor/modules/your_module/collector.py
"""Python collectors for your_module."""


def collect_memory_summary() -> str:
    """Collect and summarize memory information.

    RULES:
    - Takes no arguments
    - Must return a string
    - The string is saved as-is to the report
    - If you raise an exception, the check is marked as "error"
    """
    lines = []

    with open("/proc/meminfo", "r") as f:
        for line in f:
            key, val = line.split(":", 1)
            if key.strip() in ("MemTotal", "MemFree", "MemAvailable"):
                lines.append(f"{key.strip()}: {val.strip()}")

    return "\n".join(lines)
```

### Function Contract

| Rule | Details |
|------|---------|
| Arguments | None. The function takes no parameters. |
| Return type | `str`. Always return a string. |
| On success | Return the collected data as a string. |
| On failure | Raise an exception. The error message is captured. |
| Side effects | Avoid. Don't write files, don't modify state. |
| Timeout | Each check has a 30-second timeout. |

---

## Module Visibility, Detection, and Root Access

Modules have four possible states in the TUI:

| State | Condition | TUI Behavior |
|-------|-----------|--------------|
| **Hidden** | `enabled: false` in YAML | Not shown at all |
| **Detected** | `enabled: true` + detect succeeds (or no detect) + root OK | Normal selectable checkbox |
| **Not detected** | `enabled: true` + detect command fails | Grayed out, disabled, "(not detected)" label |
| **Requires root** | `requires_root: true` + not running as root | Grayed out, disabled, "(requires root)" label |

### The `enabled` field

Set `enabled: false` to completely hide a module from the TUI. Use this for modules that are work-in-progress or not ready for users.

```yaml
name: experimental_module
label: "Experimental"
enabled: false    # hidden from TUI
```

### The `detect` field

The `detect` field specifies a shell command that checks whether the module's tooling is available **and functional** on the system. If the command exits with code 0, the module is considered detected and shown normally. If it exits non-zero, the module is shown grayed out and disabled.

**Important:** Verify the service is actually working, not just that the binary exists. For example:

```yaml
# BAD: binary exists but cluster may not be connected
detect: "command -v kubectl"

# GOOD: actually verifies cluster connectivity
detect: "kubectl cluster-info --request-timeout=3s >/dev/null 2>&1"

# BAD: docker binary exists but daemon may not be running
detect: "command -v docker"

# GOOD: verifies Docker daemon is responsive
detect: "docker info >/dev/null 2>&1"
```

Common detection patterns:

```yaml
# Check if a service is running and responsive
detect: "docker info >/dev/null 2>&1"
detect: "kubectl cluster-info --request-timeout=3s >/dev/null 2>&1"
detect: "podman info >/dev/null 2>&1"

# Check if a binary exists (OK for tools that work standalone)
detect: "command -v python3"
detect: "command -v openssl"
detect: "command -v sensors"

# Check if a file exists
detect: "test -f /etc/docker/daemon.json"

# Multiple conditions
detect: "command -v lvs && lvs >/dev/null 2>&1"
```

If `detect` is not set, the module is always available (detected = true).

### The `requires_root` field

Set `requires_root: true` if your module's checks need root privileges to work correctly. When the binary is run as a non-root user, the module will be grayed out with "(requires root)" instead of prompting for sudo (which would break the TUI).

```yaml
name: audit_log
label: "Audit Log"
requires_root: true    # grayed out for non-root users
detect: "command -v auditctl"
checks:
  - name: audit_rules
    label: "Audit Rules"
    type: command
    command: "auditctl -l"
```

**Note:** `requires_root` is checked *before* `detect`. If the module requires root and you're not root, the detect command is not run.

---

## Complete Example: Docker Module

This module uses only YAML — no Python needed. It verifies Docker is actually running (not just installed).

### Folder structure

```
src/dxc_doctor/modules/docker/
├── __init__.py       ← empty file
└── plugin.yaml       ← the manifest
```

### plugin.yaml

```yaml
name: docker
label: "Docker"
description: "Collect Docker daemon info, images, and running containers."
version: "1.0"
author: "DXC Team"
requires_root: false
category: containers
detect: "docker info >/dev/null 2>&1"
checks:
  - name: docker_version
    label: "Docker Version"
    type: command
    command: "docker version --format '{{.Server.Version}}' 2>&1"

  - name: docker_info
    label: "Docker Info"
    type: command
    command: "docker info 2>&1"

  - name: running_containers
    label: "Running Containers"
    type: command
    command: "docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}' 2>&1"

  - name: docker_images
    label: "Docker Images"
    type: command
    command: "docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}' 2>&1"

  - name: docker_disk_usage
    label: "Docker Disk Usage"
    type: command
    command: "docker system df 2>&1"

  - name: daemon_config
    label: "Daemon Config"
    type: file
    path: "/etc/docker/daemon.json"
```

---

## Complete Example: Python-Heavy Module

This module collects network information using Python for complex parsing.

### Folder structure

```
src/dxc_doctor/modules/network/
├── __init__.py       ← empty file
├── plugin.yaml       ← the manifest
└── collector.py      ← Python functions for complex checks
```

### plugin.yaml

```yaml
name: network
label: "Network"
description: "Network interfaces, routes, DNS, and connectivity."
version: "1.0"
author: "DXC Team"
requires_root: false
category: network
checks:
  - name: interfaces
    label: "Network Interfaces"
    type: command
    command: "ip -br addr 2>/dev/null || ifconfig -a 2>/dev/null"

  - name: routes
    label: "Routing Table"
    type: command
    command: "ip route 2>/dev/null || netstat -rn 2>/dev/null"

  - name: dns_config
    label: "DNS Configuration"
    type: file
    path: "/etc/resolv.conf"

  - name: listening_ports
    label: "Listening Ports"
    type: command
    command: "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null"

  - name: connectivity
    label: "Connectivity Check"
    type: python
    function: "check_connectivity"

  - name: interface_stats
    label: "Interface Statistics"
    type: python
    function: "collect_interface_stats"
```

### collector.py

```python
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
```

---

## Complete Example: Targeted Kubernetes Inspection

This example shows a more advanced pattern: inspecting specific Kubernetes deployments by **partial name match**. Instead of dumping all cluster data, it finds deployments matching a keyword (e.g. "vault") and collects their full spec, status, attached secrets, configmaps, and pod logs.

This is useful for focused troubleshooting — e.g. "show me everything about the Vault deployment".

### Folder structure

```
src/dxc_doctor/modules/kube_vault/
├── __init__.py       ← empty file
├── plugin.yaml       ← the manifest
└── collector.py      ← Python functions for targeted queries
```

### plugin.yaml

```yaml
name: kube_vault
label: "Kubernetes: Vault"
description: "Inspect Vault-related Kubernetes deployments, secrets, and pod logs."
version: "1.0"
author: "DXC Team"
requires_root: false
category: kubernetes
detect: "kubectl cluster-info --request-timeout=3s >/dev/null 2>&1"
checks:
  - name: vault_deployments
    label: "Vault Deployments"
    type: python
    function: "find_deployments"

  - name: vault_deployment_yaml
    label: "Vault Deployment YAML"
    type: python
    function: "get_deployment_yaml"

  - name: vault_pods
    label: "Vault Pods"
    type: python
    function: "get_pods"

  - name: vault_pod_logs
    label: "Vault Pod Logs (last 50 lines)"
    type: python
    function: "get_pod_logs"

  - name: vault_secrets
    label: "Vault Secrets (metadata only)"
    type: python
    function: "get_secrets"

  - name: vault_configmaps
    label: "Vault ConfigMaps"
    type: python
    function: "get_configmaps"

  - name: vault_services
    label: "Vault Services"
    type: python
    function: "get_services"

  - name: vault_events
    label: "Vault Events"
    type: python
    function: "get_events"
```

### collector.py

```python
"""Targeted Kubernetes inspection for Vault-related resources.

Uses partial name matching — any deployment/pod/secret containing "vault"
in its name will be collected. Change MATCH_PATTERN to inspect other apps.
"""

import subprocess

# Change this to target different applications
MATCH_PATTERN = "vault"


def _kubectl(args: str, timeout: int = 15) -> str:
    """Run a kubectl command and return stdout."""
    result = subprocess.run(
        f"kubectl {args}",
        shell=True, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        return result.stderr.strip() or f"kubectl exited with code {result.returncode}"
    return result.stdout.strip()


def _find_resources(resource_type: str) -> list[tuple[str, str]]:
    """Find resources matching MATCH_PATTERN. Returns [(namespace, name), ...]."""
    output = _kubectl(f"get {resource_type} --all-namespaces -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name --no-headers")
    matches = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and MATCH_PATTERN in parts[1].lower():
            matches.append((parts[0], parts[1]))
    return matches


def find_deployments() -> str:
    """Find all deployments with 'vault' in the name."""
    matches = _find_resources("deployments")
    if not matches:
        return f"No deployments matching '{MATCH_PATTERN}' found"

    lines = [f"Found {len(matches)} deployment(s) matching '{MATCH_PATTERN}':", ""]
    for ns, name in matches:
        detail = _kubectl(f"get deployment {name} -n {ns} -o wide")
        lines.append(f"--- {ns}/{name} ---")
        lines.append(detail)
        lines.append("")
    return "\n".join(lines)


def get_deployment_yaml() -> str:
    """Get the full YAML spec for matching deployments."""
    matches = _find_resources("deployments")
    if not matches:
        return f"No deployments matching '{MATCH_PATTERN}' found"

    lines = []
    for ns, name in matches:
        yaml_out = _kubectl(f"get deployment {name} -n {ns} -o yaml")
        lines.append(f"--- {ns}/{name} ---")
        lines.append(yaml_out)
        lines.append("")
    return "\n".join(lines)


def get_pods() -> str:
    """Find pods matching the pattern and show their status."""
    matches = _find_resources("pods")
    if not matches:
        return f"No pods matching '{MATCH_PATTERN}' found"

    lines = [f"Found {len(matches)} pod(s) matching '{MATCH_PATTERN}':", ""]
    for ns, name in matches:
        detail = _kubectl(f"get pod {name} -n {ns} -o wide")
        lines.append(f"--- {ns}/{name} ---")
        lines.append(detail)
        # Also show container statuses
        status = _kubectl(f"get pod {name} -n {ns} -o jsonpath='{{.status.containerStatuses[*].state}}'")
        if status:
            lines.append(f"Container states: {status}")
        lines.append("")
    return "\n".join(lines)


def get_pod_logs() -> str:
    """Get last 50 lines of logs from matching pods."""
    matches = _find_resources("pods")
    if not matches:
        return f"No pods matching '{MATCH_PATTERN}' found"

    lines = []
    for ns, name in matches:
        logs = _kubectl(f"logs {name} -n {ns} --tail=50 --all-containers=true", timeout=20)
        lines.append(f"--- {ns}/{name} ---")
        lines.append(logs)
        lines.append("")
    return "\n".join(lines)


def get_secrets() -> str:
    """Find secrets matching the pattern (metadata only, no values)."""
    matches = _find_resources("secrets")
    if not matches:
        return f"No secrets matching '{MATCH_PATTERN}' found"

    lines = [f"Found {len(matches)} secret(s) matching '{MATCH_PATTERN}':", ""]
    for ns, name in matches:
        # Only show metadata and keys, NOT the actual secret values
        detail = _kubectl(
            f"get secret {name} -n {ns} -o jsonpath="
            "'{.metadata.name}: type={.type}, keys=[{.data}]'"
        )
        # Show just the key names, not values
        keys = _kubectl(
            f"get secret {name} -n {ns} -o jsonpath='{{range .data}}{{@}}{{\"\\n\"}}{{end}}'"
            " | wc -l"
        )
        keys_list = _kubectl(
            f"get secret {name} -n {ns} -o go-template="
            "'{{range $k, $v := .data}}{{$k}} {{end}}'"
        )
        lines.append(f"--- {ns}/{name} ---")
        lines.append(f"Keys: {keys_list}")
        lines.append("")
    return "\n".join(lines)


def get_configmaps() -> str:
    """Find configmaps matching the pattern."""
    matches = _find_resources("configmaps")
    if not matches:
        return f"No configmaps matching '{MATCH_PATTERN}' found"

    lines = [f"Found {len(matches)} configmap(s) matching '{MATCH_PATTERN}':", ""]
    for ns, name in matches:
        detail = _kubectl(f"get configmap {name} -n {ns} -o yaml")
        lines.append(f"--- {ns}/{name} ---")
        lines.append(detail)
        lines.append("")
    return "\n".join(lines)


def get_services() -> str:
    """Find services matching the pattern."""
    matches = _find_resources("services")
    if not matches:
        return f"No services matching '{MATCH_PATTERN}' found"

    lines = [f"Found {len(matches)} service(s) matching '{MATCH_PATTERN}':", ""]
    for ns, name in matches:
        detail = _kubectl(f"get svc {name} -n {ns} -o wide")
        endpoints = _kubectl(f"get endpoints {name} -n {ns}")
        lines.append(f"--- {ns}/{name} ---")
        lines.append(detail)
        lines.append(f"Endpoints: {endpoints}")
        lines.append("")
    return "\n".join(lines)


def get_events() -> str:
    """Get recent events related to matching resources."""
    matches = _find_resources("pods")
    if not matches:
        return f"No pods matching '{MATCH_PATTERN}' found"

    lines = []
    namespaces = set(ns for ns, _ in matches)
    for ns in namespaces:
        events = _kubectl(
            f"get events -n {ns} --sort-by='.lastTimestamp' "
            f"--field-selector involvedObject.name!=''"
            f" | grep -i {MATCH_PATTERN} | tail -20"
        )
        if events:
            lines.append(f"--- Events in {ns} ---")
            lines.append(events)
            lines.append("")
    return "\n".join(lines) or f"No recent events for '{MATCH_PATTERN}'"
```

### Key Patterns Demonstrated

**Partial name matching:** The `_find_resources()` helper queries all resources of a type across all namespaces and filters by substring match. This catches `vault-agent-injector`, `vault-server-0`, `my-vault-sidecar`, etc.

**Safe secret handling:** The `get_secrets()` function only collects key names, never the actual secret values. Diagnostic reports should never contain credentials.

**Reusable for other apps:** Change `MATCH_PATTERN = "vault"` to `"redis"`, `"postgres"`, `"nginx"`, etc. to inspect a different application stack. You could even create multiple modules from this pattern:

```
modules/kube_vault/plugin.yaml      → MATCH_PATTERN = "vault"
modules/kube_redis/plugin.yaml      → MATCH_PATTERN = "redis"
modules/kube_postgres/plugin.yaml   → MATCH_PATTERN = "postgres"
```

All would share the same `category: kubernetes` and appear under the same tab, each with their own detect + checks.

**Timeout handling:** The `_kubectl()` helper has a 15-second default timeout per command. Individual checks have the runner's 30-second timeout on top of that.

---

## Adding Your Module to the Build

When building the standalone binary with PyInstaller, you need to register your module in `dxc-doctor.spec` so it gets bundled.

Edit the `hiddenimports` list in `dxc-doctor.spec`:

```python
hiddenimports=[
    # ... existing modules ...
    "dxc_doctor.modules.your_module",
    "dxc_doctor.modules.your_module.collector",  # only if you have collector.py
]
```

Then rebuild:

```bash
make build
```

**Note:** YAML-only modules (no `collector.py`) still need the module import but not the collector import. The `plugin.yaml` files are bundled automatically via the `datas` setting.

---

## Testing Your Module

### Quick test with batch mode

```bash
# Run just your module
python -m dxc_doctor --batch --modules your_module_name

# Run multiple modules
python -m dxc_doctor --batch --modules os_info,your_module_name

# With custom output
python -m dxc_doctor --batch --modules your_module_name --output /tmp/test-run
```

### Check the output

```bash
# See the JSON output (stdout)
python -m dxc_doctor --batch --modules your_module_name | python -m json.tool

# See the saved files
ls /tmp/dxc-doctor-*/your_module_name/

# Read a specific check result
cat /tmp/dxc-doctor-*/your_module_name/check_name.txt
```

### Test with the TUI

```bash
python -m dxc_doctor
# Your module should appear as a checkbox under its category tab
```

### Validate the YAML

```bash
python -c "
import yaml
from dxc_doctor.models import PluginManifest

with open('src/dxc_doctor/modules/YOUR_MODULE/plugin.yaml') as f:
    data = yaml.safe_load(f)

manifest = PluginManifest.from_dict(data)
print(f'Module: {manifest.label}')
print(f'Category: {manifest.category}')
print(f'Detect: {manifest.detect or \"(always available)\"}')
print(f'Requires root: {manifest.requires_root}')
print(f'Checks: {len(manifest.checks)}')
for c in manifest.checks:
    print(f'  [{c.type}] {c.name}: {c.label}')
"
```

---

## Architecture Reference

### How files connect

```
__main__.py                         Entry point
    │
    ├── config.py                   CLI argument parsing
    │
    ├── app.py (TUI mode)          The terminal UI
    │   │
    │   ├── plugin_manager.py       Discovers your modules
    │   │   ├── reads plugin.yaml from each module folder
    │   │   ├── skips enabled: false modules
    │   │   ├── checks requires_root vs current user
    │   │   └── runs detect commands
    │   │
    │   ├── runner.py               Executes checks
    │   │   ├── command → subprocess.run()
    │   │   ├── file → open() and read
    │   │   └── python → imports collector.py, calls function
    │   │
    │   └── report.py              Writes output files
    │
    └── runner.py (batch mode)     Same runner, no TUI
```

### Key data types

```python
# models.py

@dataclass
class CheckDefinition:
    """One check from plugin.yaml"""
    name: str          # "kernel_version"
    label: str         # "Kernel Version"
    type: str          # "command", "file", or "python"
    command: str       # shell command (if type=command)
    path: str          # file path (if type=file)
    function: str      # function name (if type=python)
    timeout: int       # seconds, default 30
    severity: list[SeverityRule] | None  # custom classification rules

@dataclass
class PluginManifest:
    """Loaded plugin.yaml"""
    name: str          # "os_info"
    label: str         # "OS Information"
    description: str
    category: str      # "system" — determines TUI tab
    enabled: bool      # false = hidden entirely
    detect: str        # shell command to check availability
    detected: bool     # runtime: did detect pass?
    requires_root: bool # true = disabled for non-root
    disabled_reason: str # runtime: "not detected", "requires root", or ""
    checks: list[CheckDefinition]

@dataclass
class CheckResult:
    """Result of running one check"""
    name: str          # "kernel_version"
    label: str         # "Kernel Version"
    status: str        # "ok", "warning", "error", "skipped"
    output: str        # the collected data
    error: str         # error message (if failed)
    duration: float    # seconds taken
    returncode: int | None  # exit code (command checks only)
```

### How runner.py executes a check

```python
# Simplified version of what runner.py does:

def execute_check(check, collector_module):
    if check.type == "command":
        # own process group; killed wholesale on timeout
        stdout, stderr, rc = run_in_process_group(check.command, check.timeout)
        return CheckResult(output=stdout, returncode=rc,
                           status=classify(check, stdout, stderr, rc))

    elif check.type == "file":
        content = open(check.path).read()
        return CheckResult(output=content, status=classify(check, content, "", None))

    elif check.type == "python":
        func = getattr(collector_module, check.function)
        result = call_with_timeout(func, check.timeout)  # watchdog thread
        return CheckResult(output=result, status=classify(check, result, "", None))
```

---

## Rules and Gotchas

### Do

- **DO** use descriptive `name` values — they become filenames (`memory_info.txt`)
- **DO** use `2>&1` or `2>/dev/null` in commands to handle stderr
- **DO** use `||` for fallback commands: `"ip addr || ifconfig -a"`
- **DO** return strings from Python functions
- **DO** create an `__init__.py` in your module folder (can be empty)
- **DO** test with `--batch` mode first — it's faster and shows errors clearly
- **DO** verify service availability in `detect`, not just binary existence
- **DO** add your module to `dxc-doctor.spec` `hiddenimports` before building

### Don't

- **DON'T** modify the TUI code — your module is pure data collection
- **DON'T** use `name` values with spaces or special characters (they become CSS IDs)
- **DON'T** forget the `__init__.py` — Python won't find your collector without it
- **DON'T** print to stdout in your collector functions — return strings instead
- **DON'T** run destructive commands — this is a diagnostic tool, not a fix tool
- **DON'T** assume root — use `requires_root: true` if you need it
- **DON'T** take longer than the check timeout (default 30s) — set `timeout:` in the YAML if a check legitimately needs more
- **DON'T** let log-collecting checks (dmesg, journal greps) use default classification — add `severity: []` so collected error text isn't misread as a failed check
- **DON'T** use commands that prompt for passwords (e.g. `sudo`) — they break the TUI
- **DON'T** use `command -v` alone as `detect` for client-server tools — verify the server is reachable

### Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Missing `__init__.py` | Module not found | Create empty `__init__.py` |
| `name` has spaces | TUI crash (BadIdentifier) | Use underscores: `my_check` |
| Python function has arguments | TypeError | Functions must take zero arguments |
| Python function returns int/dict | TypeError or garbled output | Always return a `str` |
| Forgot `type` field in check | KeyError at startup | Add `type: command/file/python` |
| `name` doesn't match folder | Plugin not found | Make sure `name: xyz` matches folder `xyz/` |
| `detect` only checks binary | Module detected but all checks fail | Verify service: `docker info >/dev/null 2>&1` |
| Commands prompt for sudo | TUI breaks or hangs | Set `requires_root: true` or use non-sudo commands |
| Module not in spec file | Missing from binary build | Add to `hiddenimports` in `dxc-doctor.spec` |
