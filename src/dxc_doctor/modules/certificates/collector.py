"""Python collectors for certificates module."""

import glob
import subprocess


def check_cert_expiry() -> str:
    """Check expiry of certificate files found on the system."""
    cert_dirs = [
        "/etc/pki/tls/certs",
        "/etc/ssl/certs",
        "/etc/pki/ca-trust/source/anchors",
    ]
    cert_files = []
    for d in cert_dirs:
        cert_files.extend(glob.glob(f"{d}/*.pem"))
        cert_files.extend(glob.glob(f"{d}/*.crt"))

    if not cert_files:
        return "No certificate files found in standard locations"

    results = []
    for cert_path in sorted(cert_files)[:20]:
        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", cert_path, "-noout",
                 "-subject", "-enddate"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().replace("\n", " | ")
                results.append(f"{cert_path}: {lines}")
            else:
                results.append(f"{cert_path}: (not a valid certificate)")
        except Exception:
            results.append(f"{cert_path}: (could not read)")

    return "\n".join(results)
