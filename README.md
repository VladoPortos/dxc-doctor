# DXC Doctor

A portable, single-binary Linux diagnostic and data collection TUI tool. Runs on servers without Python installed — no dependencies required.

```
██████╗ ██╗  ██╗ ██████╗     ██████╗  ██████╗  ██████╗████████╗ ██████╗ ██████╗
██╔══██╗╚██╗██╔╝██╔════╝     ██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██║  ██║ ╚███╔╝ ██║          ██║  ██║██║   ██║██║        ██║   ██║   ██║██████╔╝
██║  ██║ ██╔██╗ ██║          ██║  ██║██║   ██║██║        ██║   ██║   ██║██╔══██╗
██████╔╝██╔╝ ██╗╚██████╗     ██████╔╝╚██████╔╝╚██████╗   ██║   ╚██████╔╝██║  ██║
╚═════╝ ╚═╝  ╚═╝ ╚═════╝     ╚═════╝  ╚═════╝  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
```

## What It Does

DXC Doctor collects system diagnostic information from Linux servers and saves it to a structured report. It provides:

- **Interactive TUI mode** — a terminal UI with tabbed categories, progress bars, and mouse support
- **Batch mode** — non-interactive JSON output for scripting and automation
- **Single binary** — no Python or dependencies needed on target servers (glibc 2.17+, plus a fully static variant)
- **Plugin system** — add new diagnostic modules without touching TUI code
- **Smart detection** — modules auto-detect whether their tooling is available
- **Parallel execution** — several modules run concurrently; checks inside a module stay sequential
- **Per-check timeouts and severity rules** — declared in `plugin.yaml`, no code needed
- **Host metadata** — hostname, OS, kernel, and tool version embedded in every report
- **HTML report** — a self-contained `report.html` with search, status filters, category navigation, and collapsible per-check panels

## Quick Start

### Using the binary (recommended for servers)

```bash
# Download or copy the binary to the target server
chmod +x dxc-doctor
./dxc-doctor                    # Interactive TUI
./dxc-doctor --batch            # Non-interactive, all modules
./dxc-doctor --batch --modules os_info --output /tmp/report
```

### From source (for development)

```bash
pip install -e ".[dev]"
python -m dxc_doctor            # Interactive TUI
python -m dxc_doctor --batch    # Batch mode
```

## Usage

### Interactive TUI

Run `dxc-doctor` (or `python -m dxc_doctor`) and you get a terminal UI where you can:

1. Browse modules organized in category tabs (System, Containers, Network, etc.)
2. Check/uncheck which diagnostic modules to run
3. Set the output directory
4. Click "Start Diagnosis" and watch live progress
5. Review results summary when done

Modules that aren't available on the system are automatically grayed out with a reason (e.g. "(not detected)", "(requires root)").

### Batch / Non-Interactive Mode

When piped or called with `--batch`, the TUI is skipped entirely:

```bash
# Run all modules
dxc-doctor --batch

# Run specific modules
dxc-doctor --batch --modules os_info

# Run multiple modules
dxc-doctor --batch --modules os_info,docker,network

# Custom output directory
dxc-doctor --batch --modules os_info --output /tmp/my-report

# Pipe-friendly (auto-detects non-TTY)
dxc-doctor --batch | jq '.os_info[] | select(.status != "ok")'
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--batch` | Non-interactive mode, JSON output to stdout |
| `--modules NAME[,NAME]` | Comma-separated modules to run |
| `--output PATH` | Output directory (default: `/tmp/dxc-doctor-YYYY-MM-DD_HHMMSS`) |
| `--no-zip` | Do not create a ZIP file of the output |
| `--list-modules` | Print available modules with detection state as JSON and exit |
| `--version` | Print version, build commit, and glibc target |

Note: the batch-mode JSON on stdout truncates each check's output to 200
characters to stay pipe-friendly. The full output is always available in
`summary.json` and the per-check `.txt` files.

### ZIP Output

By default, DXC Doctor packs the entire output into a single ZIP file for easy handoff. The support team gets one file to upload — no need to tar/zip manually.

- **TUI mode:** A "Pack output into ZIP file" checkbox is ticked by default in the output section. The ZIP path is shown in the results screen after diagnosis.
- **Batch mode:** ZIP is created automatically. Use `--no-zip` to skip it. The ZIP path is printed to stderr.

```bash
# Default: creates /tmp/dxc-doctor-2026-02-26_143022.zip
dxc-doctor --batch --modules os_info

# Skip ZIP creation
dxc-doctor --batch --modules os_info --no-zip
```

### Output Structure

After a run, the output directory contains:

```
/tmp/dxc-doctor-2026-02-25-143022/
├── summary.json          # Machine-readable: all checks, statuses, outputs
├── summary.txt           # Human-readable report
├── report.html           # Self-contained HTML report (search, collapsible panels)
├── os_info/              # One folder per module
│   ├── kernel_version.txt
│   ├── os_release.txt
│   └── ...
├── docker/
│   ├── docker_version.txt
│   ├── running_containers.txt
│   └── ...
└── network/
    ├── interfaces.txt
    ├── connectivity.txt
    └── ...
```

## Available Modules

Modules are organized by category. Each category appears as a tab in the TUI.

### System

| Module | Detect | Checks |
|--------|--------|--------|
| **OS Information** (`os_info`) | Always available | Kernel version, OS release, hostname, uptime, CPU, memory, disk, network interfaces |
| **Systemd** (`systemd`) | `systemctl` available | Failed units, running/enabled services, timers, boot time, default target |
| **Memory** (`memory`) | Always available | Meminfo, swap usage, hugepages, OOM history, NUMA topology |
| **Time Sync** (`timesync`) | `timedatectl`, `chronyc`, or `ntpq` available | timedatectl status, chrony tracking/sources, NTP peers, clock drift |
| **Kernel** (`kernel`) | Always available | Kernel version, loaded modules, key sysctl values, tainted flags, boot cmdline, dmesg errors |
| **Processes** (`processes`) | Always available | Top CPU/memory consumers, process/thread counts, zombie and D-state (hung I/O) detection |
| **Virtualization** (`virtualization`) | Always available | Virt type, DMI platform, VMware tools, vmtoolsd, QEMU guest agent, cloud-init |
| **Journal / Logs** (`journal_logs`) | `journalctl` or `/var/log` | Errors this/previous boot, journal disk usage, largest log files |
| **Limits** (`limits`) | Always available | Ulimits, limits.conf, file descriptor usage, PID 1 limits, systemd defaults |
| **Performance** (`performance`) | Always available | Load, pressure stall info (PSI), vmstat/iostat/top snapshots, context switches |
| **Cron** (`cron`) | Always available | System crontab, cron directories, user crontabs, at jobs, anacrontab |

### Containers

| Module | Detect | Checks |
|--------|--------|--------|
| **Docker** (`docker`) | `docker info` succeeds | Version, info, running containers, images, disk usage, daemon config |
| **Kubernetes** (`kubernetes`) | `kubectl cluster-info` succeeds | Cluster info, nodes, pods, failing pods, resource usage, namespaces, services, version |
| **Podman** (`podman`) | `podman info` succeeds | Version, info, running containers, images, disk usage |

### Network

| Module | Detect | Checks |
|--------|--------|--------|
| **Network** (`network`) | Always available | Interfaces, routes, DNS config, listening ports, firewall rules, connectivity check, interface stats |
| **DNS** (`dns`) | Always available | resolv.conf, nsswitch.conf, DNS resolution test with latency, dig/nslookup test |
| **Proxy** (`proxy`) | Always available | Environment proxy variables, APT/YUM/DNF proxy, git proxy, proxy connectivity test |
| **Firewall** (`firewall`) | `firewall-cmd`, `ufw`, or `nft` available | Firewalld state/zones/rules, ufw status, nftables ruleset |

### Security

| Module | Detect | Checks |
|--------|--------|--------|
| **Security** (`security`) | Always available | SELinux/AppArmor status, SSH config, sudoers, password policy, SUID binaries, last logins |
| **Certificates** (`certificates`) | `openssl` available | System CA certificates, certificate expiry check |
| **SSH** (`ssh`) | `sshd` or `/etc/ssh/sshd_config` present | sshd config, daemon status, host keys, security audit, authorized_keys per user |
| **Users / Accounts** (`users_accounts`) | Always available | Logged-in users, UID 0 accounts, locked accounts, password aging, sudo groups |
| **Audit / SELinux** (`audit_selinux`) | Root + `auditctl` or `semodule` | Auditd status, audit rules, recent AVC denials, SELinux modules and booleans |
| **Crypto Policy** (`crypto_policy`) | crypto-policies, FIPS sysctl, or `openssl` | System crypto policy, FIPS mode, OpenSSL info, SSH ciphers/MACs/kex |

### Software

| Module | Detect | Checks |
|--------|--------|--------|
| **Packages** (`packages`) | Always available | Package manager type, installed count, installed list, pending updates, repositories |
| **Python** (`python_env`) | `python3` available | Python version, pip version, pip packages, python path, virtualenvs |
| **Java** (`java`) | `java` available | Java version, JAVA_HOME, alternatives, running JVMs |
| **Ansible** (`ansible`) | `ansible` available | Ansible version, installed collections |

### Storage

| Module | Detect | Checks |
|--------|--------|--------|
| **LVM** (`lvm`) | `lvs` available | Physical volumes, volume groups, logical volumes, LVM config |
| **NFS** (`nfs`) | `showmount` or `nfsstat` available | NFS mounts, exports, NFS stats, RPC info |
| **Filesystem** (`filesystem`) | Always available | Mounts, fstab, disk/inode usage, read-only mounts, stale mount detection |
| **Disk Health** (`disk_health`) | Root + `smartctl`/`mdadm`/`multipath` | Block devices, SMART health per disk, NVMe health, mdraid, multipath |

### Hardware

| Module | Detect | Checks |
|--------|--------|--------|
| **GPU (NVIDIA)** (`gpu`) | `nvidia-smi` available | GPU info, driver version, utilization, GPU processes |
| **Sensors** (`sensors`) | `sensors` available | All sensor readings, thermal zones |
| **Hardware (DMI)** (`hardware`) | Root + `dmidecode` | System/BIOS DMI info, memory DIMMs, CPU details, PCI and USB devices |

### Module Visibility

Modules support smart detection and access control. A module can be in one of four states:

| State | Condition | TUI Behavior |
|-------|-----------|--------------|
| **Hidden** | `enabled: false` in YAML | Not shown at all |
| **Detected** | detect succeeds (or no detect command) | Normal selectable checkbox |
| **Not detected** | detect command fails | Grayed out, disabled, "(not detected)" label |
| **Requires root** | `requires_root: true` and not running as root | Grayed out, disabled, "(requires root)" label |

The detect commands verify actual service availability, not just binary existence. For example, the Kubernetes module runs `kubectl cluster-info` — having `kubectl` installed but no cluster connected will correctly show "(not detected)".

See [Writing Modules](docs/WRITING_MODULES.md) for the full guide on creating new modules.

## Architecture

### Project Structure

```
src/dxc_doctor/
├── __main__.py           # Entry point: TUI vs batch routing
├── app.py                # Textual TUI application
├── config.py             # CLI argument parsing
├── mascot.py             # ASCII art banner and messages
├── models.py             # CheckResult, PluginManifest dataclasses
├── plugin_manager.py     # Auto-discovers modules/, runs detection
├── runner.py             # Executes checks, handles timeouts
├── report.py             # Writes output files and summaries
├── html_report.py        # Self-contained HTML report generator
└── modules/              # Diagnostic plugins (one folder each)
    ├── os_info/          # System info (always available)
    ├── memory/           # Memory, swap, hugepages, OOM (always available)
    ├── timesync/         # NTP/chrony time sync (auto-detected)
    ├── kernel/           # Kernel modules, sysctl, taint flags (always available)
    ├── docker/           # Docker runtime (auto-detected)
    ├── kubernetes/       # Kubernetes cluster (auto-detected)
    ├── podman/           # Podman runtime (auto-detected)
    ├── systemd/          # Systemd services (auto-detected)
    ├── network/          # Network diagnostics (always available)
    ├── dns/              # DNS config and resolution tests (always available)
    ├── proxy/            # Proxy configuration (always available)
    ├── security/         # Security audit (always available)
    ├── certificates/     # TLS cert checks (auto-detected)
    ├── ssh/              # SSH daemon audit (auto-detected)
    ├── packages/         # Package management (always available)
    ├── python_env/       # Python environment (auto-detected)
    ├── java/             # Java environment (auto-detected)
    ├── ansible/          # Ansible info (auto-detected)
    ├── lvm/              # LVM storage (auto-detected)
    ├── nfs/              # NFS storage (auto-detected)
    ├── filesystem/       # Mounts, inode usage, stale mounts (always available)
    ├── disk_health/      # SMART, NVMe, mdraid, multipath (requires root)
    ├── processes/        # Top consumers, zombies, D-state (always available)
    ├── virtualization/   # Virt type, VMware tools, cloud-init (always available)
    ├── journal_logs/     # Journal errors, log disk usage (auto-detected)
    ├── limits/           # Ulimits, fd usage (always available)
    ├── performance/      # Load, PSI, vmstat/iostat (always available)
    ├── cron/             # Crontabs and at jobs (always available)
    ├── users_accounts/   # Accounts, password aging (always available)
    ├── audit_selinux/    # Auditd, AVC denials (requires root)
    ├── firewall/         # Firewalld, ufw, nftables (auto-detected)
    ├── crypto_policy/    # Crypto policy, FIPS (auto-detected)
    ├── hardware/         # DMI, DIMMs, PCI/USB (requires root)
    ├── gpu/              # NVIDIA GPU (auto-detected)
    └── sensors/          # Hardware sensors (auto-detected)
```

### How the Plugin System Works

Each module is a folder inside `modules/` containing a `plugin.yaml` manifest. The plugin manager auto-discovers any folder with a `plugin.yaml` — no registration, no config changes, no TUI modifications needed.

```yaml
name: docker
label: "Docker"
description: "Collect Docker daemon info, images, and running containers."
category: containers
detect: "docker info >/dev/null 2>&1"    # verify Docker daemon is running
checks:
  - name: docker_version
    label: "Docker Version"
    type: command
    command: "docker version --format '{{.Server.Version}}' 2>&1"
```

**Three check types** exist so different skill levels can contribute:

| Type | What it does | Who can write it |
|------|-------------|-----------------|
| `command` | Runs a shell command, captures stdout | Anyone who knows Linux commands |
| `file` | Reads a file's contents | Anyone — just specify the path |
| `python` | Calls a function in `collector.py` | Python developers (for complex logic) |

**Per-check `timeout` and `severity`** can be declared right in the YAML:

```yaml
- name: smart_health
  label: "SMART Health"
  type: python
  function: "collect_smart_health"
  timeout: 120                 # seconds (default 30), applies to all check types
  severity:                    # ordered regex rules; first match wins
    - pattern: "ATTENTION:"
      status: error
    - pattern: "not accessible"
      status: warning
```

When no `severity` is given, classification is exit-code based (non-zero →
error, stderr-only → warning) with mild text heuristics. `severity: []`
disables the heuristics entirely (exit code only) — useful for checks that
intentionally *collect* error text, like dmesg or journal scans.

**Adding a new module is 2 steps:**

1. Create `src/dxc_doctor/modules/your_module/plugin.yaml`
2. (Optional) Create `collector.py` if you need `python`-type checks

### Data Flow

```
1. Startup
   __main__.py → parse CLI args → TUI or batch?

2. Plugin Discovery & Detection
   plugin_manager.py → scan modules/ → load plugin.yaml
   → skip if enabled: false
   → skip if requires_root: true and not root
   → run detect command → set detected flag
   → list of PluginManifest

3. TUI Mode
   app.py → show tabs (one per category) → checkboxes per module
   → disabled modules grayed out with reason → user selects → Start

4. Execution
   runner.py → up to 4 modules in parallel; checks inside a module sequential:
     command → subprocess (own process group, killed wholesale on timeout)
     file    → open() and read
     python  → import collector.py, call function (with timeout)
   → CheckResult per check (status from exit code + severity rules)

5. Report
   report.py → write per-check .txt files + summary.json + summary.txt
   html_report.py → generate self-contained report.html

6. Results
   TUI shows summary or batch prints JSON to stdout
```

### Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **TUI** | [Textual](https://textual.textualize.io/) | Modern async widgets, CSS styling, mouse support, tabbed content |
| **Binary** | [PyInstaller](https://pyinstaller.org/) `--onefile` | Most mature, bundles Python + deps into single binary |
| **Build env** | manylinux2014 Docker | Produces binary compatible with glibc 2.17+ (RHEL/CentOS 7+, Ubuntu 14.04+, Debian 8+) |
| **Static variant** | [staticx](https://github.com/JonathonReinhart/staticx) | Bundles glibc itself — runs on any Linux including musl/Alpine |
| **Plugin config** | YAML manifests | Non-Python devs can add modules with just YAML |
| **Python** | 3.9+ source / 3.12 in builds | Modern features while supporting older build envs |

## Building

### Prerequisites

- Docker (for the portable build)
- Python 3.9+ with pip (for development)

### Docker Build (recommended)

The Docker build produces two binaries:

| Binary | Requirement | Use when |
|--------|-------------|----------|
| `dist/dxc-doctor` | Linux x86_64, glibc 2.17+ | Default — covers RHEL/CentOS 7 and everything newer |
| `dist/dxc-doctor-static` | Any Linux x86_64 kernel | glibc is broken/ancient, or musl-based distros (Alpine) |

```bash
make build
# or: cd build && bash build.sh

# Verify against old distros (centos:7, rockylinux:8, ubuntu:20.04, debian:10, alpine):
bash build/test-compat.sh
```

**Why Docker for building?** PyInstaller links against your system's glibc. If you build on Ubuntu 24.04 (glibc 2.39), the binary won't run on older distros. Building inside manylinux2014 (CentOS 7 era, glibc 2.17) produces a maximally compatible binary; the staticx pass additionally bundles glibc itself for a truly run-anywhere variant. You only need Docker for building — the resulting binary has zero dependencies.

The build stamps the git commit, build date, and glibc target into the binary — visible via `dxc-doctor --version` — so support can always identify a field binary.

### Local Build (for your own machine only)

```bash
pip install pyinstaller
pyinstaller dxc-doctor.spec
# Binary at: dist/dxc-doctor
```

Note: A local build will only run on systems with the same or newer glibc as your build machine.

### Adding Modules to the Build

When you add a new module with a `collector.py`, you must register it in `dxc-doctor.spec` under `hiddenimports` so PyInstaller bundles it:

```python
hiddenimports=[
    "dxc_doctor.modules.your_module",
    "dxc_doctor.modules.your_module.collector",  # only if it has collector.py
    ...
]
```

Modules that are YAML-only (no `collector.py`) still need the module import but not the collector import.

### Compatibility

The built binary is a fully self-contained ELF executable. It requires:

- **Linux x86_64** (amd64)
- **glibc 2.17+** (RHEL 7 / CentOS 7 era) — or *nothing* for the static variant
- No Python, no shared libraries, no runtime dependencies

| Distro | `dxc-doctor` | `dxc-doctor-static` |
|--------|--------------|---------------------|
| RHEL / CentOS | 7+ | any |
| Alma / Rocky | 8+ | any |
| Ubuntu | 14.04+ | any |
| Debian | 8+ | any |
| SUSE / SLES | 12+ | any |
| Amazon Linux | 2+ | any |
| Fedora | 19+ | any |
| Alpine (musl) | — | any |
| Arch Linux | any | any |

Run `bash build/test-compat.sh` after a build to prove compatibility against real containers of the oldest supported distros.

## Troubleshooting

### TUI looks broken (dashed borders, garbled characters)

If the TUI renders with dashed lines or block characters instead of clean borders, your terminal's `TERM` variable may not be set correctly. This is common with PuTTY-based SSH clients (mRemoteNG, PuTTY, KiTTY).

Fix by running with:

```bash
TERM=xterm-256color ./dxc-doctor
```

Or set it permanently in your shell profile (`~/.bashrc`):

```bash
export TERM=xterm-256color
```

### GLIBC version error

If you see an error like `GLIBC_2.38 not found`, the binary was built on a newer system than your server. Use the Docker build (`make build`) which produces a binary compatible with glibc 2.17+ — or use `dxc-doctor-static`, which carries its own glibc and runs on any Linux.

### Binary won't start: noexec /tmp

The single-file binary self-extracts to `$TMPDIR` (default `/tmp`) at launch. On hardened servers `/tmp` is often mounted `noexec` (CIS benchmarks), and the binary silently fails or reports a bootloader error. Point it at an exec-allowed location:

```bash
TMPDIR=/var/tmp ./dxc-doctor
# or any writable, exec-allowed directory:
TMPDIR=/root ./dxc-doctor
```

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run from source
python -m dxc_doctor

# Run tests
python -m pytest tests/ -v

# Run batch mode for quick testing
python -m dxc_doctor --batch --modules os_info

# Test a specific module
python -m dxc_doctor --batch --modules docker,network
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make dev` | Install in development mode |
| `make test` | Run test suite |
| `make run` | Run the TUI |
| `make build` | Build binary via Docker |
| `make clean` | Remove build artifacts |

## Future Improvements

### Conditional Checks

Allow checks to declare platform or distro conditions directly in `plugin.yaml`, so they only run where they're relevant:

```yaml
- name: apt_proxy
  label: "APT Proxy Config"
  type: command
  command: "grep -r proxy /etc/apt/"
  when: "distro in ['ubuntu', 'debian']"
```

This prevents irrelevant checks (e.g., apt commands on RHEL) from cluttering results with false errors.

### Output Redaction

A `--redact` flag that automatically strips sensitive data from reports before sharing. IP addresses, hostnames, usernames, passwords in config files, and API keys would be replaced with placeholders. Modules could also declare per-check redaction patterns in `plugin.yaml` for domain-specific secrets.

### Exit Codes

Return meaningful exit codes in batch mode for use in CI/CD pipelines and automation scripts:

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more warnings |
| `2` | One or more errors |
| `3` | No modules matched / nothing to run |

### Module Scaffolding

A built-in command to generate new module boilerplate:

```bash
dxc-doctor create-module mymodule --category system --checks 3
```

This would create the directory structure (`__init__.py`, `plugin.yaml`, `collector.py`) with placeholder content, add the hidden import to `dxc-doctor.spec`, and print a checklist of next steps. Lowers the barrier for new contributors.

### Module Testing

A dedicated command to test individual modules in isolation with verbose output:

```bash
dxc-doctor test-module kernel --verbose
```

This would run only that module's checks, show full stdout/stderr for each, report timing, and flag any issues (missing detect commands, broken Python collectors, duplicate check names). Useful during development without spinning up the full TUI.

### Schema Validation

Validate every `plugin.yaml` against a strict JSON schema at load time. Instead of silent failures or cryptic runtime errors, module authors would get clear, actionable messages:

```
ERROR in mymodule/plugin.yaml: check "disk_check" is missing required field "command" (type is "command")
ERROR in mymodule/plugin.yaml: unknown check type "cmd" — valid types are: command, file, python
WARNING in mymodule/plugin.yaml: field "detect" is empty — module will always be enabled
```
