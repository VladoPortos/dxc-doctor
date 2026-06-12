"""Data models for DXC Doctor."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    label: str
    status: str = "pending"  # "ok", "warning", "error", "skipped", "pending"
    output: str = ""
    error: str = ""
    duration: float = 0.0
    returncode: int | None = None  # exit code for command checks, None otherwise


@dataclass
class SeverityRule:
    """A single severity classification rule from plugin.yaml.

    Rules are evaluated in order against the check's combined output
    (stdout + stderr, case-insensitive regex search). The first match wins.
    """

    pattern: str
    status: str  # "ok", "warning", "error", "skipped"


@dataclass
class CheckDefinition:
    """A single check defined in a plugin manifest."""

    name: str
    label: str
    type: str  # "command", "file", "python"
    command: str = ""
    path: str = ""
    function: str = ""
    timeout: int = 30
    # None  -> default classification (exit code + built-in text heuristics)
    # []    -> exit-code-only classification (text heuristics disabled)
    # [...] -> custom rules first, then exit-code fallback
    severity: list[SeverityRule] | None = None


@dataclass
class PluginManifest:
    """Loaded plugin manifest from plugin.yaml."""

    name: str
    label: str
    description: str
    version: str = "1.0"
    author: str = ""
    requires_root: bool = False
    category: str = "general"
    enabled: bool = True
    detect: str = ""
    detected: bool = True
    disabled_reason: str = ""
    checks: list[CheckDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> PluginManifest:
        checks = []
        for c in data.get("checks", []):
            severity = None
            if "severity" in c:
                severity = [
                    SeverityRule(pattern=r["pattern"], status=r["status"])
                    for r in (c["severity"] or [])
                ]
            checks.append(CheckDefinition(
                name=c["name"],
                label=c.get("label", c["name"]),
                type=c["type"],
                command=c.get("command", ""),
                path=c.get("path", ""),
                function=c.get("function", ""),
                timeout=int(c.get("timeout", 30)),
                severity=severity,
            ))
        return cls(
            name=data["name"],
            label=data.get("label", data["name"]),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            author=data.get("author", ""),
            requires_root=data.get("requires_root", False),
            category=data.get("category", "general"),
            enabled=data.get("enabled", True),
            detect=data.get("detect", ""),
            checks=checks,
        )
