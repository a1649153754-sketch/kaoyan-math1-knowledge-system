#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Iterable

from local_data import (
    ROOT,
    LocalDataError,
    load_contracts,
    read_dataset,
    validate_local_directory,
    write_csv,
)
from validate_project import collect_catalog


def _derived_interval(record: dict[str, str], dataset: str) -> str:
    start_field = "last_review" if dataset == "progress" else "date"
    start = record.get(start_field, "")
    end = record.get("next_review", "")
    if not start or not end:
        return ""
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return ""
    return str(days) if days in {3, 7, 14} else ""


def migrate_directory(
    root: Path,
    source_dir: Path,
    output_dir: Path,
    *,
    force: bool = False,
    topic_ids: Iterable[str] = (),
    mother_ids: Iterable[str] = (),
) -> list[Path]:
    root = root.resolve()
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    contracts = load_contracts(root)
    known_topics = frozenset(topic_ids)
    known_mothers = frozenset(mother_ids)
    for name in contracts:
        destination = output_dir / f"{name}.csv"
        if destination.exists() and not force:
            raise LocalDataError(f"destination exists; use --force to replace it: {destination}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="knowledge-data-migration-", dir=output_dir.parent) as temp_name:
        temporary = Path(temp_name)
        for name, contract in contracts.items():
            dataset = read_dataset(
                source_dir / f"{name}.csv",
                contract,
                topic_ids=known_topics,
                mother_ids=known_mothers,
            )
            extras = tuple(field for field in dataset.header if field not in contract.header)
            target_header = contract.header + extras
            migrated: list[dict[str, str]] = []
            for source in dataset.rows:
                record = {field: source.get(field, "") for field in target_header}
                record["review_count"] = record.get("review_count", "") or "0"
                record["review_interval_days"] = (
                    record.get("review_interval_days", "") or _derived_interval(record, name)
                )
                record["schema_version"] = contract.version
                migrated.append(record)
            write_csv(temporary / f"{name}.csv", target_header, migrated)

        validate_local_directory(
            root,
            temporary,
            topic_ids=known_topics,
            mother_ids=known_mothers,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for name in contracts:
            destination = output_dir / f"{name}.csv"
            shutil.copyfile(temporary / f"{name}.csv", destination)
            written.append(destination)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy local CSV data to schema v1.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "local")
    parser.add_argument("--force", action="store_true", help="Replace destination CSV files.")
    args = parser.parse_args()
    try:
        catalog = collect_catalog(ROOT)
        written = migrate_directory(
            ROOT,
            args.source_dir,
            args.output_dir,
            force=args.force,
            topic_ids=catalog.topics,
            mother_ids=(item for item in catalog.resources if item.startswith("Q-")),
        )
    except (OSError, LocalDataError) as error:
        print(f"ERROR: {error}")
        return 1
    for path in written:
        print(f"Migrated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
