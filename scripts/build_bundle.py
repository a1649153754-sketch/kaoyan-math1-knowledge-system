#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DIST = ROOT / "dist"

ORDER = [
    "00-overview.md",
    "01-calculus.md",
    "02-linear-algebra.md",
    "03-probability-statistics.md",
    "04-method-library.md",
    "05-maintenance-loop.md",
    "06-checklists.md",
    "07-theorem-index.md",
    "08-decision-trees.md",
    "09-review-templates.md",
    "10-formula-cards.md",
    "11-problem-archetypes.md",
    "12-counterexamples.md",
    "13-personal-links.md",
    "14-project-maintenance.md",
    "15-local-data.md",
    "16-exam-evidence-index.md",
    "17-sprint-manual.md",
]

version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST.mkdir(exist_ok=True)
parts = []
for name in ORDER:
    path = DOCS / name
    if not path.exists():
        raise FileNotFoundError(path)
    parts.append(path.read_text(encoding="utf-8").strip())

bundle = "\n\n".join(parts) + "\n"
bundle = re.sub(
    r"^# 考研数学一知识体系 v[^\n]+",
    f"# 考研数学一知识体系 v{version}",
    bundle,
    count=1,
)
output = DIST / f"考研数学一知识体系_v{version}.md"
output.write_text(bundle, encoding="utf-8", newline="\n")
print(f"Wrote {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")
