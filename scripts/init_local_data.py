#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from local_data import ROOT, LocalDataError, load_contracts


def initialize_local_data(root: Path, target: Path, *, force: bool = False) -> list[Path]:
    contracts = load_contracts(root)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, contract in contracts.items():
        destination = target / f"{name}.csv"
        if destination.exists() and not force:
            continue
        shutil.copyfile(root / contract.template, destination)
        written.append(destination)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize ignored local learning-data files.")
    parser.add_argument("--target", type=Path, default=ROOT / "data" / "local")
    parser.add_argument("--force", action="store_true", help="Replace existing local CSV files.")
    args = parser.parse_args()
    try:
        written = initialize_local_data(ROOT, args.target.resolve(), force=args.force)
    except (OSError, LocalDataError) as error:
        print(f"ERROR: {error}")
        return 1
    if written:
        for path in written:
            print(f"Initialized {path}")
    else:
        print("Local data already exists; nothing was overwritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
