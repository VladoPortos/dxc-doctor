#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/dist"

echo "=== DXC Doctor Build ==="
echo "Project: $PROJECT_DIR"

mkdir -p "$OUTPUT_DIR"

GIT_SHA="$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Build in Docker using manylinux2014 for glibc 2.17 compat
docker build \
    -f "$SCRIPT_DIR/Dockerfile" \
    --build-arg GIT_SHA="$GIT_SHA" \
    --build-arg BUILD_DATE="$BUILD_DATE" \
    -t dxc-doctor-builder \
    "$PROJECT_DIR"

# Extract binaries via docker cp to avoid WSL/NTFS mount issues
CONTAINER_ID=$(docker create dxc-doctor-builder)
docker cp "$CONTAINER_ID:/build/dist/dxc-doctor" "$OUTPUT_DIR/dxc-doctor"
docker cp "$CONTAINER_ID:/build/dist/dxc-doctor-static" "$OUTPUT_DIR/dxc-doctor-static" 2>/dev/null \
    || echo "(no static binary produced — staticx step failed, glibc-2.17 binary is still fine)"
docker rm "$CONTAINER_ID" > /dev/null

echo ""
echo "=== Build complete ==="
ls -lh "$OUTPUT_DIR"/dxc-doctor* 2>/dev/null
echo ""
echo "Run build/test-compat.sh to verify the binaries against old distros."
