#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED = [
    "README.md",
    "VERSION",
    "zensical.toml",
    "docs/index.md",
    "docs/00-overview.md",
    "docs/01-calculus.md",
    "docs/02-linear-algebra.md",
    "docs/03-probability-statistics.md",
    "docs/04-method-library.md",
    "docs/05-maintenance-loop.md",
    "docs/06-checklists.md",
    "docs/07-theorem-index.md",
    "docs/08-decision-trees.md",
    "docs/09-review-templates.md",
    "docs/10-formula-cards.md",
    "docs/11-problem-archetypes.md",
    "docs/12-counterexamples.md",
    "docs/13-personal-links.md",
    "docs/14-project-maintenance.md",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


for rel in REQUIRED:
    path = ROOT / rel
    if not path.exists() or path.stat().st_size == 0:
        fail(f"required file missing or empty: {rel}")

with (ROOT / "zensical.toml").open("rb") as fh:
    config = tomllib.load(fh)

project = config.get("project", {})
if project.get("site_name") != "考研数学一知识体系":
    fail("unexpected site_name")


def flatten_nav(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from flatten_nav(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from flatten_nav(item)


for nav_path in flatten_nav(project.get("nav", [])):
    if nav_path.startswith(("http://", "https://")):
        continue
    if not (DOCS / nav_path).exists():
        fail(f"navigation target does not exist: {nav_path}")

markdown_files = sorted(DOCS.glob("*.md"))
text = "\n".join(path.read_text(encoding="utf-8") for path in markdown_files)

if "sandbox:/" in text or "/mnt/data/" in text:
    fail("container-only link leaked into documentation")

patterns = {
    "checklist": r"(?m)^- \[ \]",
    "formula": r"(?m)^\| (F-[A-Z0-9-]+) \|",
    "archetype": r"(?m)^\| (Q-[A-Z0-9-]+) \|",
    "counterexample": r"(?m)^\| (B-[A-Z0-9-]+) \|",
    "personal": r"(?m)^\| (J-\d+) \|",
}
expected = {
    "checklist": 321,
    "formula": 212,
    "archetype": 68,
    "counterexample": 40,
    "personal": 12,
}

stats = {}
for name, pattern in patterns.items():
    matches = re.findall(pattern, text)
    stats[name] = len(matches)
    if len(matches) != expected[name]:
        fail(f"{name} count changed: expected {expected[name]}, got {len(matches)}")
    if name != "checklist":
        duplicates = [key for key, count in Counter(matches).items() if count > 1]
        if duplicates:
            fail(f"duplicate {name} IDs: {duplicates[:10]}")

version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    fail(f"VERSION is not semantic version format: {version}")

print("Project validation passed")
print(f"  version:         {version}")
print(f"  checklist items: {stats['checklist']}")
print(f"  formula cards:   {stats['formula']}")
print(f"  archetypes:      {stats['archetype']}")
print(f"  counterexamples: {stats['counterexample']}")
print(f"  personal links:  {stats['personal']}")
