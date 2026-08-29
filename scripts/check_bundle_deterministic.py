#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_hash(root: Path = ROOT) -> tuple[Path, str]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    subprocess.run([sys.executable, str(root / "scripts" / "build_bundle.py")], cwd=root, check=True)
    output = root / "dist" / f"考研数学一知识体系_v{version}.md"
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return output, digest


def main() -> int:
    try:
        output, first = build_hash()
        _, second = build_hash()
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}")
        return 1
    if first != second:
        print(f"ERROR: bundle is not deterministic: {first} != {second}")
        return 1
    print(f"Deterministic bundle: {output.relative_to(ROOT)}")
    print(f"SHA256: {first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
