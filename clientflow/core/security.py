"""
security.py — redaction, roles and honest boundaries.

Three small pieces that every reviewer asks about:

  redact()        identity numbers never reach a log line
  Role / can()    a matrix instead of scattered if-statements
  require_token() write endpoints refuse requests without the shared token

None of this is authentication. There is no user database, no session, no MFA.
It is deliberately the *smallest* thing that means "the automation cannot be
triggered by anyone who can reach the port". The docs say so plainly.
"""

from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass, field

# ---- redaction -------------------------------------------------------------
EMIRATES_ID = re.compile(r"\b\d{3}-\d{4}-\d{7}-\d\b|\b784\d{12}\b")
PASSPORT = re.compile(r"\b[A-Z]\d{7,8}\b")
CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
# Credentials in log lines are the other classic leak: `password=...`, `Bearer abc123`.
SECRET_KV = re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*\S+")
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"\b(?:\+971|0)\d{8,9}\b")


def redact(text: str, *, emails: bool = False, phones: bool = False) -> str:
    """Mask identity numbers. Email/phone only when asked, because they are often
    the legitimate key you need to trace a case by."""
    if not text:
        return ""
    out = EMIRATES_ID.sub("[ID-REDACTED]", text)
    out = PASSPORT.sub("[PASSPORT-REDACTED]", out)
    out = CARD.sub("[CARD-REDACTED]", out)
    out = SECRET_KV.sub(lambda m: f"{m.group(1)}=[SECRET-REDACTED]", out)
    out = BEARER.sub("Bearer [SECRET-REDACTED]", out)
    if emails:
        out = EMAIL.sub("[EMAIL-REDACTED]", out)
    if phones:
        out = PHONE.sub("[PHONE-REDACTED]", out)
    return out


def preview(text: str, limit: int = 160) -> str:
    """Redact first, truncate second. Doing it the other way round lets half an
    ID number survive at the cut."""
    return redact(" ".join((text or "").split()))[:limit]


# ---- roles -----------------------------------------------------------------
@dataclass(frozen=True)
class Role:
    name: str
    capabilities: frozenset = field(default_factory=frozenset)


VIEWER = Role("viewer", frozenset({"read"}))
OPERATOR = Role("operator", frozenset({"read", "run_jobs", "create_drafts"}))
APPROVER = Role("approver", frozenset({"read", "run_jobs", "create_drafts", "approve"}))
ADMIN = Role("admin", frozenset({"read", "run_jobs", "create_drafts", "approve", "admin"}))

ROLES = {r.name: r for r in (VIEWER, OPERATOR, APPROVER, ADMIN)}


class PermissionDenied(Exception):
    pass


def can(role: Role | str, capability: str) -> bool:
    role = ROLES[role] if isinstance(role, str) else role
    return capability in role.capabilities


def require(role: Role | str, capability: str) -> None:
    if not can(role, capability):
        name = role if isinstance(role, str) else role.name
        raise PermissionDenied(f"role '{name}' cannot '{capability}'")


# ---- token -----------------------------------------------------------------
TOKEN_ENV = "BUREAU_API_TOKEN"


def api_token() -> str | None:
    """Read the token from the environment at call time, never at import time,
    and never from a file in the repository."""
    return os.environ.get(TOKEN_ENV) or None


def token_ok(header_value: str | None) -> bool:
    expected = api_token()
    if not expected:
        # No token configured: write endpoints stay closed rather than open.
        return False
    return bool(header_value) and hmac.compare_digest(header_value.strip(), expected)


def assert_no_hardcoded_secrets(source: str) -> None:
    """Guard used by the test suite: catch the mistake of pasting a key into code."""
    patterns = [
        r"sk-[A-Za-z0-9]{16,}",
        r"AKIA[0-9A-Z]{16}",
        r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
        r"(?i)api[_-]?key\s*=\s*['\"][A-Za-z0-9]{12,}['\"]",
    ]
    for pat in patterns:
        if re.search(pat, source):
            raise AssertionError(f"possible hardcoded secret matching {pat!r}")
