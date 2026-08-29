#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from local_data import ROOT, LocalDataError, validate_local_directory
from validate_project import collect_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate private local learning data against public schemas.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "local")
    args = parser.parse_args()
    try:
        catalog = collect_catalog(ROOT)
        datasets = validate_local_directory(
            ROOT,
            args.data_dir.resolve(),
            topic_ids=catalog.topics,
            mother_ids=(item for item in catalog.resources if item.startswith("Q-")),
        )
    except (OSError, LocalDataError) as error:
        print(f"ERROR: {error}")
        return 1
    print("Local data validation passed")
    for name, dataset in datasets.items():
        print(f"  {name}: {len(dataset.rows)} rows ({dataset.detected_version})")
        for warning in dataset.warnings:
            print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
