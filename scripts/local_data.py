#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "data/schemas/v1/manifest.json"
EXPECTED_DATASETS = ("progress", "questions", "errors")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
PRIVATE_COLUMNS = {
    "name",
    "full_name",
    "phone",
    "mobile",
    "email",
    "school",
    "wechat",
    "qq",
    "姓名",
    "电话",
    "邮箱",
    "学校",
}


class LocalDataError(RuntimeError):
    """A local-data contract violation that is safe to show to the user."""


@dataclass(frozen=True)
class DatasetContract:
    name: str
    version: str
    template: str
    schema_path: str
    header: tuple[str, ...]
    legacy_headers: tuple[tuple[str, ...], ...]
    required: frozenset[str]
    properties: dict[str, dict[str, object]]


@dataclass(frozen=True)
class DatasetRows:
    name: str
    path: Path
    header: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    detected_version: str
    warnings: tuple[str, ...]


def fail(message: str) -> None:
    raise LocalDataError(message)


def _read_json(root: Path, relative: str) -> dict[str, object]:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {relative}: {error}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {relative}")
    return value


def load_contracts(root: Path = ROOT) -> dict[str, DatasetContract]:
    root = root.resolve()
    manifest = _read_json(root, MANIFEST)
    version = str(manifest.get("schemaVersion", ""))
    if not SEMVER_RE.fullmatch(version):
        fail(f"invalid data schema version in {MANIFEST}: {version}")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or tuple(datasets) != EXPECTED_DATASETS:
        fail(f"{MANIFEST} must declare datasets in order: {EXPECTED_DATASETS}")

    contracts: dict[str, DatasetContract] = {}
    for name in EXPECTED_DATASETS:
        entry = datasets.get(name)
        if not isinstance(entry, dict):
            fail(f"missing dataset entry: {name}")
        template = str(entry.get("template", ""))
        schema_path = str(entry.get("schema", ""))
        schema = _read_json(root, schema_path)
        if schema.get("x-dataset") != name or schema.get("x-schema-version") != version:
            fail(f"schema identity mismatch: {schema_path}")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not True:
            fail(f"schema must be an append-compatible object: {schema_path}")

        raw_header = schema.get("x-csv-header")
        if not isinstance(raw_header, list) or not raw_header or not all(isinstance(x, str) for x in raw_header):
            fail(f"invalid x-csv-header: {schema_path}")
        header = tuple(raw_header)
        if len(header) != len(set(header)):
            fail(f"duplicate fields in x-csv-header: {schema_path}")

        raw_legacy = schema.get("x-legacy-headers", [])
        if not isinstance(raw_legacy, list):
            fail(f"invalid x-legacy-headers: {schema_path}")
        legacy_headers: list[tuple[str, ...]] = []
        for legacy in raw_legacy:
            if not isinstance(legacy, list) or not legacy or not all(isinstance(x, str) for x in legacy):
                fail(f"invalid legacy header: {schema_path}")
            legacy_tuple = tuple(legacy)
            if header[: len(legacy_tuple)] != legacy_tuple:
                fail(f"legacy header is not a prefix of current header: {schema_path}")
            legacy_headers.append(legacy_tuple)

        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            fail(f"schema properties/required are invalid: {schema_path}")
        if set(header) != set(properties) or not set(required).issubset(header):
            fail(f"schema fields do not match x-csv-header: {schema_path}")
        if not template or not (root / template).exists():
            fail(f"public template missing: {template}")
        contracts[name] = DatasetContract(
            name=name,
            version=version,
            template=template,
            schema_path=schema_path,
            header=header,
            legacy_headers=tuple(legacy_headers),
            required=frozenset(str(item) for item in required),
            properties={str(key): value for key, value in properties.items() if isinstance(value, dict)},
        )
    return contracts


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[list[str]]]:
    if not path.exists():
        fail(f"local dataset missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        fail(f"CSV has no header: {path}")
    return tuple(rows[0]), rows[1:]


def classify_header(header: tuple[str, ...], contract: DatasetContract, source: Path) -> tuple[str, list[str]]:
    if len(header) != len(set(header)):
        fail(f"duplicate CSV fields: {source}")
    risky = PRIVATE_COLUMNS.intersection(field.casefold() for field in header)
    if risky:
        fail(f"private identity columns are forbidden: {source}: {sorted(risky)}")

    if header[: len(contract.header)] == contract.header:
        return contract.version, []
    for legacy in contract.legacy_headers:
        if header[: len(legacy)] == legacy:
            return "legacy", [f"{source.name} uses a legacy header; run migrate_local_data.py"]
    fail(f"CSV header is neither current nor append-compatible legacy: {source}")


def _validate_property(value: str, rules: dict[str, object], source: str) -> None:
    if value == "":
        return
    enum = rules.get("enum")
    if isinstance(enum, list) and value not in enum:
        fail(f"value {value!r} is outside enum: {source}")
    pattern = rules.get("pattern")
    if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
        fail(f"value {value!r} does not match {pattern}: {source}")
    if rules.get("format") == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            fail(f"invalid ISO date {value!r}: {source}")
    min_length = rules.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        fail(f"value is shorter than {min_length}: {source}")


def _split_semicolon(value: str, source: str) -> list[str]:
    if not value:
        return []
    raw = value.split(";")
    if any(not item.strip() for item in raw):
        fail(f"empty semicolon-delimited item: {source}")
    return [item.strip() for item in raw]


def read_dataset(
    path: Path,
    contract: DatasetContract,
    *,
    topic_ids: Iterable[str] = (),
    mother_ids: Iterable[str] = (),
) -> DatasetRows:
    header, raw_rows = _read_csv(path)
    detected_version, warnings = classify_header(header, contract, path)
    known_topics = frozenset(topic_ids)
    known_mothers = frozenset(mother_ids)
    records: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for line_number, raw in enumerate(raw_rows, 2):
        if not any(cell.strip() for cell in raw):
            continue
        if len(raw) != len(header):
            fail(f"CSV row width mismatch: {path}:{line_number}")
        record = {field: value.strip() for field, value in zip(header, raw)}
        for field in contract.required:
            if not record.get(field, ""):
                fail(f"required field {field} is empty: {path}:{line_number}")
        for field, rules in contract.properties.items():
            if field in record:
                _validate_property(record[field], rules, f"{path}:{line_number}:{field}")

        if contract.name == "progress":
            node_ids = [record.get("node_id", "")]
            unique_key = record.get("node_id", "")
        else:
            node_ids = _split_semicolon(record.get("node_ids", ""), f"{path}:{line_number}:node_ids")
            unique_key = record.get("error_id", "") if contract.name == "errors" else ""
        if known_topics:
            unknown = [node_id for node_id in node_ids if node_id and node_id not in known_topics]
            if unknown:
                fail(f"unknown formal node IDs {unknown}: {path}:{line_number}")
        mother_id = record.get("mother_id", "")
        if mother_id and known_mothers and mother_id not in known_mothers:
            fail(f"unknown mother_id {mother_id}: {path}:{line_number}")
        if unique_key:
            if unique_key in seen_keys:
                fail(f"duplicate {contract.name} key {unique_key}: {path}:{line_number}")
            seen_keys.add(unique_key)
        if "schema_version" in record and record["schema_version"] not in {"", contract.version}:
            fail(f"unsupported schema_version {record['schema_version']}: {path}:{line_number}")
        records.append(record)

    return DatasetRows(
        name=contract.name,
        path=path,
        header=header,
        rows=tuple(records),
        detected_version=detected_version,
        warnings=tuple(warnings),
    )


def validate_local_directory(
    root: Path,
    data_dir: Path,
    *,
    topic_ids: Iterable[str] = (),
    mother_ids: Iterable[str] = (),
) -> dict[str, DatasetRows]:
    contracts = load_contracts(root)
    known_topics = frozenset(topic_ids)
    known_mothers = frozenset(mother_ids)
    result: dict[str, DatasetRows] = {}
    for name, contract in contracts.items():
        result[name] = read_dataset(
            data_dir / f"{name}.csv",
            contract,
            topic_ids=known_topics,
            mother_ids=known_mothers,
        )
    return result


def write_csv(path: Path, header: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = tuple(header)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
