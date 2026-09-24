"""Small dependency-free secret scan for CI.

It intentionally looks for high-confidence credential formats rather than trying to
secret-scan arbitrary prose.  It complements, and does not replace, a dedicated scanner.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PATTERNS = {
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".next", "reports", "__pycache__"}
SKIP_SUFFIXES = {".db", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".pyc"}


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in {".env", ".env.local"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(root)}: possible {name}")
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if findings:
        print("Secret scan failed:")
        print("\n".join(findings))
        raise SystemExit(1)
    print("Secret scan passed")


if __name__ == "__main__":
    main()
