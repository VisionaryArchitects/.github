#!/usr/bin/env python3
"""Dependency-free validation for the public Visionary GitHub defaults repository."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    ".pre-commit-config.yaml",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/governance-ci.yml",
)

SECRET_PATTERNS = {
    "GitHub token": re.compile("gh" + r"[opsu]_[A-Za-z0-9_]{20,}"),
    "GitHub fine-grained token": re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile("AK" + r"IA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer credential": re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
}
WINDOWS_LOCAL_PATH = re.compile(
    r"(?i)(?:^|[\s`'\"(])(?:[A-Z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+)"
)
UNIX_LOCAL_PATH = re.compile(r"(?:^|[\s`'\"(])/(?:Users|home|tmp)/")
PINNED_ACTION = re.compile(r"^\s*uses:\s*[^./\s]+/[^@\s]+@([0-9a-f]{40})(?:\s*#.*)?$")
CONFLICT_MARKERS = ("<" * 7, "=" * 7, ">" * 7)


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}", failures)

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.stat().st_size > 1_048_576:
            fail(f"file exceeds bounded public-data scan size: {relative}", failures)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in CONFLICT_MARKERS):
            fail(f"merge-conflict marker: {relative}", failures)
        for number, line in enumerate(text.splitlines(), start=1):
            if line.endswith((" ", "\t")):
                fail(f"trailing whitespace: {relative}:{number}", failures)
        if WINDOWS_LOCAL_PATH.search(text) or UNIX_LOCAL_PATH.search(text):
            fail(f"machine-local absolute path: {relative}", failures)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                fail(f"possible {label}: {relative}", failures)

    workflows = ROOT / ".github" / "workflows"
    for path in sorted(workflows.glob("*.y*ml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("uses:") and not PINNED_ACTION.match(line):
                fail(f"action is not pinned to a full commit SHA: {path.name}:{number}", failures)

    if failures:
        print("Governance validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Governance validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
