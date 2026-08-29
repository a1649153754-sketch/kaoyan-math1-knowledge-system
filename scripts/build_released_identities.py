#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_project import ROOT, collect_catalog, current_identities


def payload(root: Path, snapshot_version: str) -> dict[str, object]:
    return {
        "schemaVersion": "1",
        "snapshotVersion": snapshot_version,
        "policy": (
            "Every published formal-node, checklist-item, and F/Q/B/J resource ID is an immutable identity. "
            "Later releases may add IDs; removal, reuse, or resource-type changes require an explicit deprecation migration."
        ),
        **current_identities(collect_catalog(root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or check the released stable-identity baseline.")
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in baseline differs.")
    parser.add_argument("--snapshot-version", help="Version whose published identities are being frozen.")
    args = parser.parse_args()

    output = ROOT / "data" / "released-identities.v1.json"
    snapshot_version = args.snapshot_version
    if not snapshot_version and args.check and output.exists():
        snapshot_version = json.loads(output.read_text(encoding="utf-8")).get("snapshotVersion")
    snapshot_version = snapshot_version or (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    content = json.dumps(payload(ROOT, snapshot_version), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            raise SystemExit("released identity baseline is stale")
        print("Released identity baseline is current")
        return 0
    output.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
