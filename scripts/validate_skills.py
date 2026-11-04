#!/usr/bin/env python3
"""Check every skill in skills/. Standard library only, so it runs anywhere.

    python scripts/validate_skills.py

Fails on: bad frontmatter, a name that differs from the folder, a missing LICENSE or
README, a skill not listed in the catalogue, likely secrets, machine paths, and
oversized or forbidden files.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MAX_FILE = 25 * 1024 * 1024
MAX_DESC = 1024
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORBIDDEN_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "_out", "projects"}
TEXT = {".md", ".py", ".mjs", ".js", ".jsx", ".ts", ".css", ".html", ".yaml", ".yml", ".json", ".txt", ".ini", ".example", ".toml", ".sh"}
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[bap]-[A-Za-z0-9-]{20,}|"
                    r"eyJhbGciOi[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
MACHINE = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[a-z0-9._-]+|/home/[a-z0-9._-]+/|/Users/[a-z0-9._-]+/")
# placeholder-style paths in docs are fine
MACHINE_OK = re.compile(r"Users[\\/]+(you|me|name|user|username|example)\b", re.I)


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not k.startswith((" ", "\t")):
            out[k.strip()] = v.strip().strip('"\'')
    return out


def main() -> int:
    errors: list[str] = []
    try:
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FAIL marketplace.json: {e}")
        return 1
    listed = {s.rstrip("/").split("/")[-1] for p in market.get("plugins", []) for s in p.get("skills", [])}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    folders = sorted(d for d in SKILLS.iterdir() if d.is_dir()) if SKILLS.exists() else []
    if not folders:
        errors.append("no skills found in skills/")
    for d in folders:
        name = d.name
        if not NAME.match(name):
            errors.append(f"{name}: folder must be lowercase kebab-case")
        sk = d / "SKILL.md"
        if not sk.exists():
            errors.append(f"{name}: missing SKILL.md")
            continue
        fm = frontmatter(sk)
        for key in ("name", "description", "version", "license", "author"):
            if not fm.get(key):
                errors.append(f"{name}: frontmatter is missing '{key}'")
        if fm.get("name") and fm["name"] != name:
            errors.append(f"{name}: frontmatter name is '{fm['name']}'")
        if len(fm.get("description", "")) > MAX_DESC:
            errors.append(f"{name}: description is {len(fm['description'])} chars (max {MAX_DESC})")
        for need in ("README.md", "LICENSE"):
            if not (d / need).exists():
                errors.append(f"{name}: missing {need}")
        if name not in listed:
            errors.append(f"{name}: not listed in .claude-plugin/marketplace.json")
        if f"skills/{name}" not in readme:
            errors.append(f"{name}: not listed in README.md")
        for f in d.rglob("*"):
            rel = f.relative_to(ROOT).as_posix()
            if any(p in FORBIDDEN_DIRS for p in f.relative_to(d).parts):
                errors.append(f"{rel}: forbidden folder")
                continue
            if not f.is_file():
                continue
            if f.name == ".env" or f.name.endswith(".pem"):
                errors.append(f"{rel}: must not be committed")
            if f.stat().st_size > MAX_FILE:
                errors.append(f"{rel}: over {MAX_FILE // 1024 // 1024} MB")
            if f.suffix.lower() in TEXT or f.name == ".env.example":
                body = f.read_text(encoding="utf-8", errors="ignore")
                if SECRET.search(body):
                    errors.append(f"{rel}: looks like it contains a secret")
                for m in MACHINE.finditer(body):
                    if not MACHINE_OK.search(m.group(0)):
                        errors.append(f"{rel}: machine-specific path: {m.group(0)}")
                        break
    missing = listed - {d.name for d in folders}
    for name in sorted(missing):
        errors.append(f"marketplace.json lists '{name}', but skills/{name} does not exist")
    for e in errors:
        print(f"FAIL {e}")
    print(f"{len(folders)} skills checked, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
