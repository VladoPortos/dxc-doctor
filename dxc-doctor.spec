# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for DXC Doctor.

Build with: pyinstaller dxc-doctor.spec
"""

# Dynamically collect all rich unicode data modules (they're loaded at runtime
# by version string, so PyInstaller can't detect them via static analysis)
rich_unicode_hiddenimports = []
try:
    from rich._unicode_data import VERSIONS
    for v in VERSIONS:
        rich_unicode_hiddenimports.append("rich._unicode_data.unicode" + v.replace(".", "-"))
except Exception:
    pass

a = Analysis(
    ["entry.py"],
    pathex=[],
    binaries=[],
    datas=[("src/dxc_doctor/modules", "dxc_doctor/modules")],
    hiddenimports=[
        "dxc_doctor.modules.os_info",
        "dxc_doctor.modules.os_info.collector",
        "dxc_doctor.modules.docker",
        "dxc_doctor.modules.kubernetes",
        "dxc_doctor.modules.podman",
        "dxc_doctor.modules.systemd",
        "dxc_doctor.modules.lvm",
        "dxc_doctor.modules.network",
        "dxc_doctor.modules.network.collector",
        "dxc_doctor.modules.nfs",
        "dxc_doctor.modules.security",
        "dxc_doctor.modules.certificates",
        "dxc_doctor.modules.certificates.collector",
        "dxc_doctor.modules.packages",
        "dxc_doctor.modules.python_env",
        "dxc_doctor.modules.java",
        "dxc_doctor.modules.gpu",
        "dxc_doctor.modules.sensors",
        "dxc_doctor.modules.ansible",
        "dxc_doctor.modules.filesystem",
        "dxc_doctor.modules.filesystem.collector",
        "dxc_doctor.modules.dns",
        "dxc_doctor.modules.dns.collector",
        "dxc_doctor.modules.proxy",
        "dxc_doctor.modules.proxy.collector",
        "dxc_doctor.modules.memory",
        "dxc_doctor.modules.memory.collector",
        "dxc_doctor.modules.timesync",
        "dxc_doctor.modules.timesync.collector",
        "dxc_doctor.modules.kernel",
        "dxc_doctor.modules.kernel.collector",
        "dxc_doctor.modules.ssh",
        "dxc_doctor.modules.ssh.collector",
        "dxc_doctor.modules.processes",
        "dxc_doctor.modules.processes.collector",
        "dxc_doctor.modules.virtualization",
        "dxc_doctor.modules.journal_logs",
        "dxc_doctor.modules.limits",
        "dxc_doctor.modules.limits.collector",
        "dxc_doctor.modules.performance",
        "dxc_doctor.modules.performance.collector",
        "dxc_doctor.modules.disk_health",
        "dxc_doctor.modules.disk_health.collector",
        "dxc_doctor.modules.users_accounts",
        "dxc_doctor.modules.users_accounts.collector",
        "dxc_doctor.modules.cron",
        "dxc_doctor.modules.cron.collector",
        "dxc_doctor.modules.hardware",
        "dxc_doctor.modules.audit_selinux",
        "dxc_doctor.modules.firewall",
        "dxc_doctor.modules.crypto_policy",
        "textual.widgets._tabbed_content",
        "textual.widgets._tab_pane",
        "textual.widgets._tabs",
    ] + rich_unicode_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dxc-doctor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True,
)
