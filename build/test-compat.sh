#!/usr/bin/env bash
# Smoke-test the built binaries against old distros in Docker.
#
# Usage: bash build/test-compat.sh
#
# For each image: run --version, --list-modules, and a small batch
# collection. Any failure (glibc error, missing lib, crash) fails the test.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

# Distro images the glibc-2.17 binary must support
IMAGES=(
    "centos:7"
    "rockylinux:8"
    "ubuntu:20.04"
    "debian:10"
)
# The staticx binary should additionally run on musl
STATIC_IMAGES=(
    "alpine:3.19"
)

if [ ! -x "$DIST_DIR/dxc-doctor" ]; then
    echo "ERROR: $DIST_DIR/dxc-doctor not found — run build/build.sh first" >&2
    exit 1
fi

# Stage binaries on a native Linux filesystem: bind-mounting from an
# NTFS-backed path (WSL /mnt/*) can break the exec bit inside containers.
STAGE_DIR="$(mktemp -d /tmp/dxc-compat.XXXXXX)"
trap 'rm -rf "$STAGE_DIR"' EXIT
cp "$DIST_DIR/dxc-doctor" "$STAGE_DIR/"
[ -f "$DIST_DIR/dxc-doctor-static" ] && cp "$DIST_DIR/dxc-doctor-static" "$STAGE_DIR/"
chmod +x "$STAGE_DIR"/dxc-doctor*

run_test() {
    local image="$1" binary="$2"
    echo -n "  $image / $binary ... "
    if docker run --rm -v "$STAGE_DIR:/t:ro" "$image" sh -c "
        /t/$binary --version >/dev/null &&
        /t/$binary --list-modules >/dev/null &&
        /t/$binary --batch --modules os_info,limits --no-zip --output /tmp/compat-run >/dev/null
    " > /tmp/compat-test.log 2>&1; then
        echo "OK"
        return 0
    else
        echo "FAILED"
        sed 's/^/    /' /tmp/compat-test.log | head -10
        return 1
    fi
}

FAILED=0

echo "=== glibc 2.17 binary (dxc-doctor) ==="
for image in "${IMAGES[@]}"; do
    run_test "$image" "dxc-doctor" || FAILED=1
done

if [ -f "$STAGE_DIR/dxc-doctor-static" ]; then
    echo "=== static binary (dxc-doctor-static) ==="
    for image in "${IMAGES[@]}" "${STATIC_IMAGES[@]}"; do
        run_test "$image" "dxc-doctor-static" || FAILED=1
    done
else
    echo "(static binary not present — skipping musl tests)"
fi

echo ""
if [ "$FAILED" = 0 ]; then
    echo "=== All compatibility tests passed ==="
else
    echo "=== SOME COMPATIBILITY TESTS FAILED ===" >&2
fi
exit $FAILED
