"""Python collectors for users_accounts module."""

from __future__ import annotations

from datetime import date, timedelta


def _read_shadow() -> list[list[str]] | None:
    """Read /etc/shadow entries, or None when not readable."""
    try:
        with open("/etc/shadow", "r") as f:
            return [line.split(":") for line in f.read().splitlines() if line]
    except (PermissionError, FileNotFoundError):
        return None


def collect_account_status() -> str:
    """Report locked accounts and accounts with no password set."""
    entries = _read_shadow()
    if entries is None:
        return "/etc/shadow not readable (run as root for account status)"

    locked = []
    no_password = []
    for fields in entries:
        if len(fields) < 2:
            continue
        user, pw_hash = fields[0], fields[1]
        if pw_hash == "":
            no_password.append(user)
        elif pw_hash.startswith("!") and len(pw_hash) > 2:
            locked.append(user)  # locked-out password (! prefix on a hash)

    lines = [f"Accounts in shadow: {len(entries)}"]
    if no_password:
        lines.append(f"NO PASSWORD set ({len(no_password)}): {', '.join(no_password)}")
    if locked:
        lines.append(f"Locked accounts ({len(locked)}): {', '.join(locked[:15])}")
    if not no_password and not locked:
        lines.append("No empty-password or locked-hash accounts found.")
    return "\n".join(lines)


def collect_password_aging() -> str:
    """Report password expiry per account from /etc/shadow."""
    entries = _read_shadow()
    if entries is None:
        return "/etc/shadow not readable (run as root for password aging)"

    epoch = date(1970, 1, 1)
    today = date.today()
    lines = []
    for fields in entries:
        if len(fields) < 5:
            continue
        user, pw_hash, last_change, _min_age, max_age = fields[:5]
        # Only real password-bearing accounts are interesting
        if pw_hash in ("", "*", "!", "!!") or pw_hash.startswith("!*"):
            continue
        if not last_change.isdigit() or not max_age.lstrip("-").isdigit():
            continue
        max_days = int(max_age)
        if max_days <= 0 or max_days >= 99999:
            lines.append(f"{user}: never expires")
            continue
        expires = epoch + timedelta(days=int(last_change) + max_days)
        remaining = (expires - today).days
        if remaining < 0:
            lines.append(f"{user}: EXPIRED {-remaining} day(s) ago ({expires})")
        elif remaining <= 14:
            lines.append(f"{user}: expires in {remaining} day(s) ({expires})")
        else:
            lines.append(f"{user}: expires {expires} ({remaining} days)")

    if not lines:
        return "No password-bearing accounts with aging info found."
    return "\n".join(lines)
