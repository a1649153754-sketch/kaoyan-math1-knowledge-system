#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from exam_evidence import (
    INDEX_FILE,
    MANIFEST_FILE,
    MOCK_FILE,
    OFFICIAL_FILE,
    SCHEMA_FILES,
    ExamEvidenceError,
    build_reverse_indexes,
    load_json,
    sha256_file,
    validate_exam_evidence,
    write_json,
)
from validate_project import ROOT, collect_catalog


def refresh_manifest_hashes() -> None:
    manifest = load_json(ROOT, MANIFEST_FILE)
    artifact_paths = {
        "officialQuestions": OFFICIAL_FILE,
        "mockAggregate": MOCK_FILE,
        "indexes": INDEX_FILE,
        "officialQuestionsSchema": SCHEMA_FILES[0],
        "mockAggregateSchema": SCHEMA_FILES[1],
        "indexesSchema": SCHEMA_FILES[2],
    }
    manifest["artifacts"] = {
        name: {"path": relative.as_posix(), "sha256": sha256_file(ROOT / relative)}
        for name, relative in artifact_paths.items()
    }
    write_json(ROOT / MANIFEST_FILE, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify public exam-evidence reverse indexes.")
    parser.add_argument("--write", action="store_true", help="Regenerate indexes and refresh manifest hashes")
    parser.add_argument("--check", action="store_true", help="Verify committed artifacts without changing files")
    args = parser.parse_args()
    if args.write == args.check:
        parser.error("choose exactly one of --write or --check")
    try:
        if args.write:
            official = load_json(ROOT, OFFICIAL_FILE)
            write_json(ROOT / INDEX_FILE, build_reverse_indexes(official))
            refresh_manifest_hashes()
        stats = validate_exam_evidence(ROOT, collect_catalog(ROOT))
    except (ExamEvidenceError, OSError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Exam evidence indexes are current")
    print(f"  official questions: {stats['officialQuestions']}")
    print(f"  indexed mothers:    {stats['indexedMothers']}")
    print(f"  indexed nodes:      {stats['indexedNodes']}")
    print(f"  mock questions:     {stats['mockQuestions']} (anonymous aggregate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
