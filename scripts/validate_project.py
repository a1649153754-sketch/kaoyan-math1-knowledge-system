#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from content_audit import ContentAuditError, validate_content_audits
from exam_evidence import ExamEvidenceError, validate_exam_evidence
from local_data import PRIVATE_COLUMNS, LocalDataError, load_contracts

ROOT = Path(__file__).resolve().parents[1]

TOPIC_FILES = (
    "docs/01-calculus.md",
    "docs/02-linear-algebra.md",
    "docs/03-probability-statistics.md",
    "docs/04-method-library.md",
)
RESOURCE_FILES = {
    "docs/10-formula-cards.md": ("formula", 5),
    "docs/11-problem-archetypes.md": ("archetype", 6),
    "docs/12-counterexamples.md": ("counterexample", 4),
    "docs/13-personal-links.md": ("personal", 5),
}
REQUIRED_FILES = (
    "README.md",
    "VERSION",
    "CHANGELOG.md",
    "CITATION.cff",
    "zensical.toml",
    "data/released-identities.v1.json",
    "data/schemas/v1/manifest.json",
    "data/schemas/v1/progress.schema.json",
    "data/schemas/v1/questions.schema.json",
    "data/schemas/v1/errors.schema.json",
    "docs/index.md",
    "docs/00-overview.md",
    *TOPIC_FILES,
    "docs/05-maintenance-loop.md",
    "docs/06-checklists.md",
    "docs/07-theorem-index.md",
    "docs/08-decision-trees.md",
    "docs/09-review-templates.md",
    *RESOURCE_FILES,
    "docs/14-project-maintenance.md",
    "docs/15-local-data.md",
    "docs/16-exam-evidence-index.md",
)
TOPIC_RE = re.compile(r"^-\s+([HLPM]\d+\.\d+)\s+(.+)$")
CHAPTER_RE = re.compile(r"^##\s+([HLPM]\d+)\b")
CHECKLIST_RE = re.compile(r"^-\s+\[ \]\s+([HLPM]\d+\.\d+-[a-z])\b")
RESOURCE_ID_RE = re.compile(r"^(?:F-[A-Z0-9]+-\d+|Q-[A-Z]\d+|B-[A-Z]\d+|J-\d+)$")
TOPIC_EXACT_RE = re.compile(r"(?<![A-Za-z0-9.-])([HLPM]\d+\.\d+)(?![A-Za-z0-9.-])")
TOPIC_RANGE_RE = re.compile(r"\b([HLPM]\d+)\.(\d+)\s*[-–—]\s*(?:([HLPM]\d+)\.)?(\d+)\b")
CHECKLIST_REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9.-])([HLPM]\d+\.\d+-[a-z])\b")
CHAPTER_REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9.-])([HLPM]\d+)(?![A-Za-z0-9.-])")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+['\"].*?['\"])?\)")


class ProjectValidationError(RuntimeError):
    """A deterministic project-contract violation."""


@dataclass(frozen=True)
class ResourceRow:
    resource_id: str
    kind: str
    source: str
    line: int
    cells: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class Catalog:
    chapters: frozenset[str]
    topics: dict[str, str]
    checklist_items: frozenset[str]
    resources: dict[str, ResourceRow]


def fail(message: str) -> None:
    raise ProjectValidationError(message)


def read_text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8").lstrip("\ufeff")


def natural_key(value: str) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value))


def split_markdown_row(line: str) -> list[str]:
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            current.append(character)
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    cells.append("".join(current).strip())
    if cells and not cells[0]:
        cells.pop(0)
    if cells and not cells[-1]:
        cells.pop()
    return cells


def validate_required_files(root: Path) -> None:
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.exists() or path.stat().st_size == 0:
            fail(f"required file missing or empty: {relative}")


def collect_topics(root: Path) -> tuple[set[str], dict[str, str]]:
    chapters: set[str] = set()
    topics: dict[str, str] = {}
    for relative in TOPIC_FILES:
        current_chapter: str | None = None
        for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
            chapter_match = CHAPTER_RE.match(line)
            if chapter_match:
                current_chapter = chapter_match.group(1)
                if current_chapter in chapters:
                    fail(f"duplicate chapter ID {current_chapter}: {relative}:{line_number}")
                chapters.add(current_chapter)
                continue
            topic_match = TOPIC_RE.match(line)
            if not topic_match:
                continue
            topic_id = topic_match.group(1)
            if current_chapter is None:
                fail(f"topic appears before its chapter: {relative}:{line_number}")
            if topic_id.split(".", 1)[0] != current_chapter:
                fail(f"topic {topic_id} is outside chapter {current_chapter}: {relative}:{line_number}")
            if topic_id in topics:
                fail(f"duplicate topic ID {topic_id}: {relative}:{line_number}")
            topics[topic_id] = f"{relative}:{line_number}"
    return chapters, topics


def collect_checklist_items(root: Path) -> set[str]:
    relative = "docs/06-checklists.md"
    items: set[str] = set()
    for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
        match = CHECKLIST_RE.match(line)
        if not match:
            continue
        item_id = match.group(1)
        if item_id in items:
            fail(f"duplicate checklist ID {item_id}: {relative}:{line_number}")
        items.add(item_id)
    return items


def collect_resources(root: Path) -> dict[str, ResourceRow]:
    resources: dict[str, ResourceRow] = {}
    for relative, (kind, required_columns) in RESOURCE_FILES.items():
        for line_number, line in enumerate(read_text(root, relative).splitlines(), 1):
            if not line.lstrip().startswith("|"):
                continue
            cells = split_markdown_row(line)
            if not cells or not RESOURCE_ID_RE.fullmatch(cells[0]):
                continue
            resource_id = cells[0]
            if resource_id in resources:
                fail(f"duplicate resource ID {resource_id}: {relative}:{line_number}")
            if len(cells) != required_columns:
                fail(
                    f"{resource_id} has {len(cells)} table cells; expected {required_columns}: "
                    f"{relative}:{line_number}"
                )
            empty_columns = [index + 1 for index, value in enumerate(cells) if not value.strip()]
            if empty_columns:
                fail(f"{resource_id} has empty required cells {empty_columns}: {relative}:{line_number}")
            resources[resource_id] = ResourceRow(
                resource_id=resource_id,
                kind=kind,
                source=relative,
                line=line_number,
                cells=tuple(cells),
                raw=line,
            )
    return resources


def collect_catalog(root: Path) -> Catalog:
    chapters, topics = collect_topics(root)
    checklist_items = collect_checklist_items(root)
    resources = collect_resources(root)
    return Catalog(frozenset(chapters), topics, frozenset(checklist_items), resources)


def validate_navigation(root: Path) -> None:
    with (root / "zensical.toml").open("rb") as handle:
        config = tomllib.load(handle)
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
        if not (root / "docs" / nav_path).exists():
            fail(f"navigation target does not exist: {nav_path}")


def _validate_topic_mentions(text: str, catalog: Catalog, source: str) -> int:
    checklist_mentions = list(CHECKLIST_REFERENCE_RE.finditer(text))
    scrubbed = CHECKLIST_REFERENCE_RE.sub(" ", text)
    found = 0
    for match in checklist_mentions:
        item_id = match.group(1)
        if item_id not in catalog.checklist_items:
            fail(f"unknown checklist item {item_id}: {source}")
        parent_topic = item_id.rsplit("-", 1)[0]
        if parent_topic not in catalog.topics:
            fail(
                f"checklist item {item_id} cannot be used as a resource topic because "
                f"{parent_topic} is not a formal node: {source}"
            )
        found += 1

    ranges = list(TOPIC_RANGE_RE.finditer(scrubbed))
    scrubbed = TOPIC_RANGE_RE.sub(" ", scrubbed)
    for match in ranges:
        start_root = match.group(1)
        end_root = match.group(3) or start_root
        start = int(match.group(2))
        end = int(match.group(4))
        if start_root != end_root or end < start or end - start > 50:
            fail(f"invalid topic range {match.group(0)}: {source}")
        missing = [
            f"{start_root}.{value}"
            for value in range(start, end + 1)
            if f"{start_root}.{value}" not in catalog.topics
        ]
        if missing:
            fail(f"topic range {match.group(0)} contains unknown formal nodes {missing}: {source}")
        found += end - start + 1

    for match in TOPIC_EXACT_RE.finditer(scrubbed):
        topic_id = match.group(1)
        if topic_id not in catalog.topics:
            fail(f"unknown formal topic {topic_id}: {source}")
        found += 1
    return found


def validate_resource_references(catalog: Catalog) -> None:
    for row in catalog.resources.values():
        source = f"{row.source}:{row.line} ({row.resource_id})"
        # Downstream consumers scan the complete resource row, so validate every
        # exact/range mention rather than trusting only the association column.
        _validate_topic_mentions(row.raw, catalog, source)

        if row.kind == "formula":
            match = re.fullmatch(r"F-([HLPM]\d+)-\d+", row.resource_id)
            if not match or match.group(1) not in catalog.chapters:
                fail(f"formula ID does not map to a formal chapter: {source}")
        elif row.kind in {"archetype", "personal"}:
            association = row.cells[3] if row.kind == "archetype" else row.cells[2]
            found = _validate_topic_mentions(association, catalog, source)
            for match in CHAPTER_REFERENCE_RE.finditer(association):
                chapter_id = match.group(1)
                if chapter_id not in catalog.chapters:
                    fail(f"unknown chapter {chapter_id}: {source}")
                found += 1
            if found == 0:
                fail(f"resource has no formal topic or chapter association: {source}")


def current_identities(catalog: Catalog) -> dict[str, object]:
    return {
        "knowledgeNodes": sorted(catalog.topics, key=natural_key),
        "checklistItems": sorted(catalog.checklist_items, key=natural_key),
        "resources": sorted(catalog.resources, key=natural_key),
        "resourceKinds": {
            resource_id: catalog.resources[resource_id].kind
            for resource_id in sorted(catalog.resources, key=natural_key)
        },
    }


def validate_released_identities(root: Path, catalog: Catalog) -> None:
    relative = "data/released-identities.v1.json"
    try:
        baseline = json.loads(read_text(root, relative))
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {relative}: {error}")
    if baseline.get("schemaVersion") != "1":
        fail(f"unsupported released identity schema in {relative}")
    if not SEMVER_RE.fullmatch(str(baseline.get("snapshotVersion", ""))):
        fail(f"invalid snapshotVersion in {relative}")

    current = current_identities(catalog)
    for key in ("knowledgeNodes", "checklistItems", "resources"):
        released = baseline.get(key)
        if not isinstance(released, list) or len(released) != len(set(released)):
            fail(f"{relative}.{key} must be a unique array")
        missing = sorted(set(released) - set(current[key]), key=natural_key)
        if missing:
            fail(f"released {key} were removed or renamed: {missing[:20]}")

    released_kinds = baseline.get("resourceKinds")
    if not isinstance(released_kinds, dict):
        fail(f"{relative}.resourceKinds must be an object")
    changed = [
        resource_id
        for resource_id, kind in released_kinds.items()
        if current["resourceKinds"].get(resource_id) != kind
    ]
    if changed:
        fail(f"released resource IDs changed namespace/type: {changed[:20]}")


def validate_csv_templates(root: Path) -> str:
    contracts = load_contracts(root)
    versions = {contract.version for contract in contracts.values()}
    if len(versions) != 1:
        fail("public CSV schemas do not share one version")
    for contract in contracts.values():
        relative = contract.template
        path = root / relative
        if not path.exists() or path.stat().st_size == 0:
            fail(f"CSV template missing or empty: {relative}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        if not rows:
            fail(f"CSV template has no header: {relative}")
        header = tuple(rows[0])
        risky = PRIVATE_COLUMNS.intersection(field.casefold() for field in header)
        if risky:
            fail(f"public CSV template contains private identity columns {sorted(risky)}: {relative}")
        if header != contract.header:
            fail(f"CSV header is not append-only compatible: {relative}")
        if len(header) != len(set(header)):
            fail(f"CSV header contains duplicate fields: {relative}")
        if len(rows) != 1:
            fail(f"public CSV template must be header-only: {relative}")
    return versions.pop()


def validate_private_layer(root: Path) -> None:
    ignore_lines = {
        line.strip()
        for line in read_text(root, ".gitignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {"data/local/*", "!data/local/.gitkeep"}
    if not required.issubset(ignore_lines):
        fail(".gitignore must ignore data/local/* and retain only data/local/.gitkeep")
    keep = root / "data" / "local" / ".gitkeep"
    if not keep.exists():
        fail("data/local/.gitkeep is missing")

    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "data/local"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            fail(f"cannot inspect tracked local data: {result.stderr.strip()}")
        tracked = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
        leaked = [path for path in tracked if path != "data/local/.gitkeep"]
        if leaked:
            fail(f"private local data is tracked by Git: {leaked}")


def validate_local_links(root: Path) -> None:
    excluded_parts = {".git", ".venv", "site", "dist"}
    for markdown_file in sorted(root.rglob("*.md")):
        parts = markdown_file.relative_to(root).parts
        if excluded_parts.intersection(parts) or parts[:2] == ("data", "local"):
            continue
        relative = markdown_file.relative_to(root).as_posix()
        text = markdown_file.read_text(encoding="utf-8").lstrip("\ufeff")
        if "sandbox:/" in text or "/mnt/data/" in text:
            fail(f"container-only link leaked into documentation: {relative}")
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw_target = match.group(1).strip("<>")
            if raw_target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_target = unquote(raw_target.split("#", 1)[0].split("?", 1)[0])
            if not file_target:
                continue
            resolved = (markdown_file.parent / file_target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                fail(f"local link escapes repository: {relative} -> {raw_target}")
            if not resolved.exists():
                line_number = text.count("\n", 0, match.start()) + 1
                fail(f"broken local link: {relative}:{line_number} -> {raw_target}")


def validate_release_metadata(root: Path) -> str:
    version = read_text(root, "VERSION").strip()
    if not SEMVER_RE.fullmatch(version):
        fail(f"VERSION is not semantic version format: {version}")
    if f"**v{version}" not in read_text(root, "README.md"):
        fail("README current version does not match VERSION")
    if f"version: {version}" not in read_text(root, "CITATION.cff"):
        fail("CITATION.cff version does not match VERSION")
    if f"## [{version}]" not in read_text(root, "CHANGELOG.md"):
        fail("CHANGELOG has no entry for VERSION")
    major, minor, patch = map(int, version.split("."))
    release_dir = root / "releases" / (f"v{major}.{minor}" if patch == 0 else f"v{version}")
    if not (release_dir / "README.md").exists():
        fail(f"release note missing: {release_dir.relative_to(root).as_posix()}/README.md")
    return version


def validate_project(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    validate_required_files(root)
    validate_navigation(root)
    catalog = collect_catalog(root)
    validate_resource_references(catalog)
    validate_released_identities(root, catalog)
    data_schema_version = validate_csv_templates(root)
    validate_private_layer(root)
    validate_local_links(root)
    version = validate_release_metadata(root)
    exam_evidence = validate_exam_evidence(root, catalog)
    content_audit = validate_content_audits(root)
    resource_counts = Counter(row.kind for row in catalog.resources.values())
    return {
        "version": version,
        "chapters": len(catalog.chapters),
        "knowledgeNodes": len(catalog.topics),
        "checklistItems": len(catalog.checklist_items),
        "resources": len(catalog.resources),
        "resourceCounts": dict(sorted(resource_counts.items())),
        "dataSchemaVersion": data_schema_version,
        "examEvidence": exam_evidence,
        "contentAudit": content_audit,
        "unresolvedResourceMentions": 0,
    }


def main() -> int:
    try:
        stats = validate_project(ROOT)
    except (
        OSError,
        ContentAuditError,
        ExamEvidenceError,
        LocalDataError,
        ProjectValidationError,
        tomllib.TOMLDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Project validation passed")
    print(f"  version:                     {stats['version']}")
    print(f"  chapters:                    {stats['chapters']}")
    print(f"  formal knowledge nodes:      {stats['knowledgeNodes']}")
    print(f"  checklist items:             {stats['checklistItems']}")
    print(f"  resources:                   {stats['resources']} {stats['resourceCounts']}")
    print(f"  public data schema:          {stats['dataSchemaVersion']} (header-only templates)")
    print(
        "  official exam evidence:      "
        f"{stats['examEvidence']['officialPapers']} papers / {stats['examEvidence']['officialQuestions']} questions"
    )
    print(
        "  mock exam evidence:          "
        f"{stats['examEvidence']['mockPapers']} papers / {stats['examEvidence']['mockQuestions']} questions (aggregate only)"
    )
    print(
        "  audited execution cards:     "
        f"{stats['contentAudit']['auditedNodes']} nodes in {stats['contentAudit']['auditedChapters']}"
    )
    print(f"  unresolved resource mentions:{stats['unresolvedResourceMentions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
