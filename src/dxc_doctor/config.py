"""CLI argument parsing and configuration."""

from __future__ import annotations

import argparse
import os
from datetime import datetime


def default_output_dir() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join("/tmp", f"dxc-doctor-{timestamp}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dxc-doctor",
        description="DXC Doctor - Linux diagnostic data collection tool",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run in non-interactive batch mode (no TUI)",
    )
    parser.add_argument(
        "--modules",
        type=str,
        default="",
        help="Comma-separated list of modules to run (batch mode)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output directory path",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Do not create a ZIP file of the output",
    )
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List available modules with detection state as JSON and exit",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    args = parser.parse_args(argv)
    if not args.output:
        args.output = default_output_dir()
    return args
