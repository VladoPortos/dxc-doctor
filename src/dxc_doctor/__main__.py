"""Entry point for DXC Doctor."""

import json
import os
import sys

from .config import parse_args


def _configure_ca_bundle() -> None:
    """Point the bundled OpenSSL at the host's CA certificates.

    The PyInstaller binary ships its own OpenSSL whose compiled-in default
    cert paths may not exist on the target distro. Without this, any HTTPS
    check (e.g. proxy connectivity) fails certificate verification.
    """
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return
    try:
        import ssl
        paths = ssl.get_default_verify_paths()
        if paths.cafile and os.path.exists(paths.cafile):
            return
        if paths.capath and os.path.isdir(paths.capath):
            return
    except Exception:
        pass
    for candidate in (
        "/etc/pki/tls/certs/ca-bundle.crt",       # RHEL family
        "/etc/ssl/certs/ca-certificates.crt",     # Debian/Ubuntu
        "/etc/ssl/ca-bundle.pem",                 # SUSE
        "/etc/pki/tls/cacert.pem",
        "/etc/ssl/cert.pem",
    ):
        if os.path.exists(candidate):
            os.environ["SSL_CERT_FILE"] = candidate
            break


def _print_version() -> None:
    from . import __version__
    line = f"dxc-doctor {__version__}"
    try:
        from ._build_info import BUILD_INFO
        extras = ", ".join(f"{k}: {v}" for k, v in BUILD_INFO.items())
        if extras:
            line += f" ({extras})"
    except ImportError:
        pass
    print(line)


def _list_modules() -> None:
    from .plugin_manager import discover_plugins
    plugins = discover_plugins()
    listing = [
        {
            "name": p.name,
            "label": p.label,
            "category": p.category,
            "description": p.description,
            "detected": p.detected,
            "disabled_reason": p.disabled_reason,
            "checks": len(p.checks),
        }
        for p in plugins
    ]
    print(json.dumps(listing, indent=2))


def main():
    _configure_ca_bundle()
    args = parse_args()

    if args.version:
        _print_version()
        sys.exit(0)

    if args.list_modules:
        _list_modules()
        sys.exit(0)

    if args.batch or not sys.stdout.isatty():
        from .runner import run_batch
        run_batch(args)
    else:
        # Discover before the TUI starts: detect commands and any plugin
        # warnings print to a normal terminal instead of garbling the UI.
        from .plugin_manager import discover_plugins
        from .app import DXCDoctorApp
        plugins = discover_plugins()
        app = DXCDoctorApp(args, plugins=plugins)
        app.run()


if __name__ == "__main__":
    main()
