#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = Path("data/exam-evidence/v1")
OFFICIAL_FILE = EVIDENCE_ROOT / "official-questions.json"
MOCK_FILE = EVIDENCE_ROOT / "mock-aggregate.json"
INDEX_FILE = EVIDENCE_ROOT / "indexes.json"
MANIFEST_FILE = EVIDENCE_ROOT / "manifest.json"
SCHEMA_FILES = (
    EVIDENCE_ROOT / "schemas/official-questions.schema.json",
    EVIDENCE_ROOT / "schemas/mock-aggregate.schema.json",
    EVIDENCE_ROOT / "schemas/indexes.schema.json",
)
SCHEMA_VERSION = "1.0.0"
RELEASE_VERSION = "1.4.0"
OFFICIAL_YEARS = tuple(range(2010, 2027))
EXPECTED_OFFICIAL_QUESTIONS = 385
EXPECTED_OFFICIAL_MARKS = 2550
QUESTION_ID_RE = re.compile(r"^(20\d{2})-M1-Q(\d{2})$")
TOPIC_RE = re.compile(r"(?<![A-Za-z0-9.-])([HLPM]\d+\.\d+)(?![A-Za-z0-9.-])")
TOPIC_RANGE_RE = re.compile(r"\b([HLPM]\d+)\.(\d+)\s*[-–—]\s*(?:([HLPM]\d+)\.)?(\d+)\b")
CHAPTER_RE = re.compile(r"(?<![A-Za-z0-9.-])([HLPM]\d+)(?![A-Za-z0-9.-])")
SUBJECT_PREFIX = {"高等数学": "Q-H", "线性代数": "Q-L", "概率论": "Q-P"}
ERROR_CAUSES = {
    "insight": "route-choice",
    "calculation": "calculation",
    "knowledgeBreadth": "knowledge-connection",
    "conditionTraps": "condition-check",
    "routeCoupling": "route-coupling",
}
FOUNDATION_FALLBACKS = {
    "H0.1": "Q-H05",
    "H0.2": "Q-H02",
    "H0.3": "Q-H01",
    "H0.4": "Q-H09",
    "H0.5": "Q-H34",
    "L0.1": "Q-L08",
    "L0.2": "Q-L11",
    "L0.3": "Q-L14",
    "L0.4": "Q-L08",
}
QUESTION_FIELDS = {
    "id",
    "year",
    "no",
    "type",
    "score",
    "subject",
    "difficulty100",
    "difficultyBand",
    "nodeIds",
    "coreNodeIds",
    "supportNodeIds",
    "primaryMotherId",
    "auxiliaryMotherIds",
    "routeLabel",
    "errorCauseTags",
}
OFFICIAL_TOP_LEVEL_FIELDS = {"$schema", "schemaVersion", "scope", "rightsBoundary", "papers"}
OFFICIAL_PAPER_FIELDS = {"year", "status", "boundaryNote", "questionCount", "totalScore", "questions"}
OFFICIAL_2026_FIELDS = OFFICIAL_PAPER_FIELDS | {"officialOriginalAvailable", "officialAnswerAvailable"}
MOCK_TOP_LEVEL_FIELDS = {
    "$schema",
    "schemaVersion",
    "privacyMode",
    "itemLevelPublished",
    "suppressionThreshold",
    "paperCount",
    "questionCount",
    "totalMarks",
    "years",
    "bySubject",
    "byQuestionType",
    "difficulty",
    "topNodes",
    "topMothers",
    "rightsBoundary",
}
FORBIDDEN_ITEM_FIELDS = {"prompt", "answer", "analysis", "pitfalls", "diagram", "source", "sources"}


class ExamEvidenceError(RuntimeError):
    """A copyright, truthfulness, identity, or index-contract violation."""


@dataclass(frozen=True)
class MotherArchetype:
    mother_id: str
    subject: str
    node_ids: frozenset[str]
    route_label: str


def fail(message: str) -> None:
    raise ExamEvidenceError(message)


def natural_key(value: str) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value))


def load_json(root: Path, relative: Path | str) -> dict[str, object]:
    path = root / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {Path(relative).as_posix()}: {error}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {Path(relative).as_posix()}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(collect_keys(child))
    return keys


def _association_nodes(text: str, catalog) -> set[str]:
    nodes: set[str] = set()
    scrubbed = text
    for match in TOPIC_RANGE_RE.finditer(text):
        start_root = match.group(1)
        end_root = match.group(3) or start_root
        start = int(match.group(2))
        end = int(match.group(4))
        if start_root == end_root and start <= end:
            nodes.update(
                f"{start_root}.{number}"
                for number in range(start, end + 1)
                if f"{start_root}.{number}" in catalog.topics
            )
    scrubbed = TOPIC_RANGE_RE.sub(" ", scrubbed)
    nodes.update(match.group(1) for match in TOPIC_RE.finditer(scrubbed) if match.group(1) in catalog.topics)
    scrubbed = TOPIC_RE.sub(" ", scrubbed)
    for match in CHAPTER_RE.finditer(scrubbed):
        chapter = match.group(1)
        nodes.update(topic for topic in catalog.topics if topic.split(".", 1)[0] == chapter)
    return nodes


def _short_label(value: str, limit: int = 48) -> str:
    cleaned = re.sub(r"[`$\\{}]", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" 。；;")
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def build_mother_catalog(catalog) -> dict[str, MotherArchetype]:
    mothers: dict[str, MotherArchetype] = {}
    for resource_id, row in catalog.resources.items():
        if not resource_id.startswith("Q-"):
            continue
        prefix = resource_id[:3]
        subject = {"Q-H": "高等数学", "Q-L": "线性代数", "Q-P": "概率论"}.get(prefix)
        if not subject:
            fail(f"unsupported mother archetype namespace: {resource_id}")
        association = row.cells[3]
        nodes = _association_nodes(association, catalog)
        if not nodes:
            fail(f"mother archetype has no formal nodes: {resource_id}")
        route = _short_label(row.cells[2])
        if not route:
            fail(f"mother archetype has no public route label: {resource_id}")
        mothers[resource_id] = MotherArchetype(resource_id, subject, frozenset(nodes), route)
    return mothers


def assign_mothers(
    subject: str,
    core_nodes: Iterable[str],
    support_nodes: Iterable[str],
    mothers: dict[str, MotherArchetype],
) -> tuple[str, list[str], str]:
    core = frozenset(core_nodes)
    support = frozenset(support_nodes)
    prefix = SUBJECT_PREFIX.get(subject)
    if prefix is None:
        fail(f"unsupported subject for mother assignment: {subject}")
    ranked: list[tuple[float, str]] = []
    core_chapters = {node.split(".", 1)[0] for node in core}
    support_chapters = {node.split(".", 1)[0] for node in support}
    for mother_id, mother in mothers.items():
        if not mother_id.startswith(prefix):
            continue
        core_overlap = len(core & mother.node_ids)
        support_overlap = len(support & mother.node_ids)
        mother_chapters = {node.split(".", 1)[0] for node in mother.node_ids}
        core_chapter_overlap = len(core_chapters & mother_chapters)
        support_chapter_overlap = len(support_chapters & mother_chapters)
        if core_overlap + support_overlap + core_chapter_overlap + support_chapter_overlap == 0:
            continue
        specificity = 1.0 / max(1, len(mother.node_ids))
        proximity = 0.0
        for node in core | support:
            chapter, number = node.split(".", 1)
            same_chapter = [candidate for candidate in mother.node_ids if candidate.startswith(chapter + ".")]
            if same_chapter:
                proximity += 1.0 / (1 + min(abs(int(number) - int(candidate.split(".", 1)[1])) for candidate in same_chapter))
        ranked.append(
            (
                core_overlap * 100
                + support_overlap * 30
                + core_chapter_overlap * 10
                + support_chapter_overlap * 3
                + proximity
                + specificity,
                mother_id,
            )
        )
    if not ranked:
        fallback_ids = [FOUNDATION_FALLBACKS[node] for node in sorted(core | support, key=natural_key) if node in FOUNDATION_FALLBACKS]
        fallback_ids = list(dict.fromkeys(fallback_ids))
        if fallback_ids:
            primary = fallback_ids[0]
            auxiliary = fallback_ids[1:3]
            return primary, auxiliary, mothers[primary].route_label
        fail(f"no mother archetype covers {subject} nodes {sorted(core | support, key=natural_key)}")
    ranked.sort(key=lambda item: (-item[0], natural_key(item[1])))
    primary = ranked[0][1]
    auxiliary = [mother_id for _, mother_id in ranked[1:3]]
    return primary, auxiliary, mothers[primary].route_label


def derive_error_causes(difficulty: dict[str, object]) -> list[str]:
    components = difficulty.get("components") if isinstance(difficulty, dict) else None
    if not isinstance(components, dict):
        return ["knowledge-connection"]
    scores: dict[str, int] = {}
    for component, tag in ERROR_CAUSES.items():
        value = components.get(component)
        if isinstance(value, dict) and isinstance(value.get("score"), (int, float)):
            scores[tag] = int(value["score"])
    if not scores:
        return ["knowledge-connection"]
    maximum = max(scores.values())
    threshold = max(5, int(maximum * 0.55))
    selected = [tag for tag, score in scores.items() if score >= threshold]
    return sorted(selected)


def _accumulate(target: dict[str, dict[str, set[object]]], key: str, question: dict[str, object]) -> None:
    bucket = target.setdefault(
        key,
        {"questionIds": set(), "years": set(), "motherIds": set(), "nodeIds": set(), "errorCauseTags": set()},
    )
    bucket["questionIds"].add(question["id"])
    bucket["years"].add(question["year"])
    bucket["motherIds"].add(question["primaryMotherId"])
    bucket["motherIds"].update(question["auxiliaryMotherIds"])
    bucket["nodeIds"].update(question["nodeIds"])
    bucket["errorCauseTags"].update(question["errorCauseTags"])


def _finalize_reverse(values: dict[str, dict[str, set[object]]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for key in sorted(values, key=natural_key):
        bucket = values[key]
        question_ids = sorted(bucket["questionIds"], key=natural_key)
        result[key] = {
            "questionCount": len(question_ids),
            "questionIds": question_ids,
            "years": sorted(bucket["years"]),
            "motherIds": sorted(bucket["motherIds"], key=natural_key),
            "nodeIds": sorted(bucket["nodeIds"], key=natural_key),
            "errorCauseTags": sorted(bucket["errorCauseTags"]),
        }
    return result


def build_reverse_indexes(official: dict[str, object]) -> dict[str, object]:
    by_year: dict[str, dict[str, set[object]]] = {}
    by_mother: dict[str, dict[str, set[object]]] = {}
    by_node: dict[str, dict[str, set[object]]] = {}
    by_error: dict[str, dict[str, set[object]]] = {}
    for paper in official.get("papers", []):
        for question in paper.get("questions", []):
            _accumulate(by_year, str(question["year"]), question)
            for mother_id in [question["primaryMotherId"], *question["auxiliaryMotherIds"]]:
                _accumulate(by_mother, mother_id, question)
            for node_id in question["nodeIds"]:
                _accumulate(by_node, node_id, question)
            for tag in question["errorCauseTags"]:
                _accumulate(by_error, tag, question)
    return {
        "$schema": "kaoyan-math1/exam-evidence/indexes@1",
        "schemaVersion": SCHEMA_VERSION,
        "byYear": _finalize_reverse(by_year),
        "byMother": _finalize_reverse(by_mother),
        "byNode": _finalize_reverse(by_node),
        "byErrorCause": _finalize_reverse(by_error),
    }


def _iter_questions(official: dict[str, object]):
    for paper in official.get("papers", []):
        for question in paper.get("questions", []):
            yield paper, question


def validate_exam_evidence(root: Path, catalog) -> dict[str, object]:
    root = root.resolve()
    for relative in (*SCHEMA_FILES, OFFICIAL_FILE, MOCK_FILE, INDEX_FILE, MANIFEST_FILE):
        if not (root / relative).exists():
            fail(f"exam evidence artifact missing: {relative.as_posix()}")
    for relative in SCHEMA_FILES:
        schema = load_json(root, relative)
        if schema.get("type") != "object" or not schema.get("$id"):
            fail(f"invalid exam evidence schema: {relative.as_posix()}")

    official = load_json(root, OFFICIAL_FILE)
    mock = load_json(root, MOCK_FILE)
    indexes = load_json(root, INDEX_FILE)
    manifest = load_json(root, MANIFEST_FILE)
    if official.get("$schema") != "kaoyan-math1/exam-evidence/official-questions@1":
        fail("official exam evidence schema identity mismatch")
    if set(official) != OFFICIAL_TOP_LEVEL_FIELDS:
        fail("official exam evidence top-level fields mismatch")
    if mock.get("$schema") != "kaoyan-math1/exam-evidence/mock-aggregate@1":
        fail("mock aggregate schema identity mismatch")
    if set(mock) != MOCK_TOP_LEVEL_FIELDS:
        fail("mock aggregate top-level fields mismatch")
    if manifest.get("releaseVersion") != RELEASE_VERSION:
        fail("exam evidence manifest release version mismatch")
    if any(value.get("schemaVersion") != SCHEMA_VERSION for value in (official, mock, indexes, manifest)):
        fail("exam evidence schema version mismatch")

    mothers = build_mother_catalog(catalog)
    years = [paper.get("year") for paper in official.get("papers", [])]
    if tuple(years) != OFFICIAL_YEARS:
        fail(f"official evidence years must be 2010-2026 in order: {years}")
    question_ids: set[str] = set()
    question_count = 0
    total_marks = 0
    for paper, question in _iter_questions(official):
        expected_paper_fields = OFFICIAL_2026_FIELDS if paper.get("year") == 2026 else OFFICIAL_PAPER_FIELDS
        if set(paper) != expected_paper_fields:
            fail(f"official paper fields mismatch: {paper.get('year')}")
        question_count += 1
        total_marks += question.get("score", 0)
        if set(question) != QUESTION_FIELDS:
            extra = sorted(set(question) - QUESTION_FIELDS)
            missing = sorted(QUESTION_FIELDS - set(question))
            fail(f"unsafe or incomplete official question fields {question.get('id')}: extra={extra}, missing={missing}")
        if FORBIDDEN_ITEM_FIELDS.intersection(question):
            fail(f"copyright-sensitive field leaked into official index: {question.get('id')}")
        match = QUESTION_ID_RE.fullmatch(str(question.get("id", "")))
        if not match or int(match.group(1)) != paper.get("year") or int(match.group(2)) != question.get("no"):
            fail(f"question identity mismatch: {question.get('id')}")
        if question["id"] in question_ids:
            fail(f"duplicate official evidence question: {question['id']}")
        question_ids.add(question["id"])
        if question.get("year") != paper.get("year"):
            fail(f"question year mismatch: {question['id']}")
        if question.get("type") not in {"选择题", "填空题", "解答题"} or question.get("subject") not in SUBJECT_PREFIX:
            fail(f"invalid question type/subject: {question['id']}")
        if not isinstance(question.get("score"), (int, float)) or question["score"] <= 0:
            fail(f"invalid score: {question['id']}")
        if not isinstance(question.get("difficulty100"), int) or not 0 <= question["difficulty100"] <= 100:
            fail(f"invalid difficulty100: {question['id']}")
        if not isinstance(question.get("difficultyBand"), str) or not question["difficultyBand"].strip():
            fail(f"invalid difficulty band: {question['id']}")
        if not isinstance(question.get("routeLabel"), str) or not 1 <= len(question["routeLabel"]) <= 48:
            fail(f"route label is empty or too long: {question['id']}")
        nodes = question.get("nodeIds")
        core = question.get("coreNodeIds")
        support = question.get("supportNodeIds")
        if (
            not isinstance(nodes, list)
            or not isinstance(core, list)
            or not isinstance(support, list)
            or not nodes
            or not core
            or len(nodes) != len(set(nodes))
            or len(core) != len(set(core))
            or len(support) != len(set(support))
            or set(core) & set(support)
            or set(nodes) != set(core) | set(support)
        ):
            fail(f"node role partition mismatch: {question['id']}")
        unknown_nodes = sorted(set(nodes) - set(catalog.topics), key=natural_key)
        if unknown_nodes:
            fail(f"unknown formal nodes in exam evidence {question['id']}: {unknown_nodes}")
        primary = question.get("primaryMotherId")
        auxiliary = question.get("auxiliaryMotherIds")
        if primary not in mothers or not str(primary).startswith(SUBJECT_PREFIX[question["subject"]]):
            fail(f"invalid primary mother: {question['id']}")
        if not isinstance(auxiliary, list) or len(auxiliary) > 2 or primary in auxiliary or len(auxiliary) != len(set(auxiliary)):
            fail(f"invalid auxiliary mothers: {question['id']}")
        if any(mother_id not in mothers for mother_id in auxiliary):
            fail(f"unknown auxiliary mother: {question['id']}")
        expected_primary, expected_auxiliary, expected_route = assign_mothers(
            question["subject"], core, support, mothers
        )
        if (primary, auxiliary, question["routeLabel"]) != (
            expected_primary,
            expected_auxiliary,
            expected_route,
        ):
            fail(f"mother assignment or route label is stale: {question['id']}")
        if (
            not isinstance(question.get("errorCauseTags"), list)
            or not question["errorCauseTags"]
            or len(question["errorCauseTags"]) != len(set(question["errorCauseTags"]))
            or not set(question["errorCauseTags"]).issubset(ERROR_CAUSES.values())
        ):
            fail(f"invalid error cause tags: {question['id']}")

    for paper in official["papers"]:
        if paper.get("questionCount") != len(paper["questions"]):
            fail(f"official paper question count mismatch: {paper.get('year')}")
        if paper.get("totalScore") != sum(question["score"] for question in paper["questions"]):
            fail(f"official paper score mismatch: {paper.get('year')}")

    scope = official.get("scope", {})
    if scope.get("paperCount") != len(OFFICIAL_YEARS) or scope.get("questionCount") != question_count:
        fail("official evidence scope counts mismatch")
    if scope.get("totalMarks") != total_marks:
        fail("official evidence total marks mismatch")
    if question_count != EXPECTED_OFFICIAL_QUESTIONS or total_marks != EXPECTED_OFFICIAL_MARKS:
        fail("official evidence release baseline must remain 385 questions / 2550 marks")
    paper2026 = official["papers"][-1]
    required_boundary = {
        "status": "reconstructed",
        "officialOriginalAvailable": False,
        "officialAnswerAvailable": False,
    }
    if any(paper2026.get(key) != value for key, value in required_boundary.items()):
        fail("2026 truthfulness boundary must say reconstructed, non-official original and non-official answer")
    if not all(term in paper2026.get("boundaryNote", "") for term in ("非官方原卷", "非官方答案")):
        fail("2026 truthfulness boundary note must explicitly say non-official original and answer")
    if any(paper.get("status") != "official-archive" for paper in official["papers"][:-1]):
        fail("2010-2025 official archive status mismatch")

    if mock.get("privacyMode") != "anonymous-aggregate-only" or mock.get("itemLevelPublished") is not False:
        fail("mock evidence must remain anonymous aggregate only")
    forbidden_mock = {"paperId", "questionId", "provider", "routeLabel", "prompt", "answer", "analysis"}
    if forbidden_mock.intersection(collect_keys(mock)):
        fail("mock aggregate contains a forbidden item-level field name")
    threshold = mock.get("suppressionThreshold")
    if not isinstance(threshold, int) or threshold < 5:
        fail("mock aggregate suppression threshold must be at least 5")
    for key in ("topNodes", "topMothers"):
        if any(row.get("questionCount", 0) < threshold for row in mock.get(key, [])):
            fail(f"mock aggregate contains a suppressed cohort: {key}")
    for key in ("bySubject", "byQuestionType"):
        rows = mock.get(key)
        if not isinstance(rows, list) or sum(row.get("questionCount", 0) for row in rows) != mock.get("questionCount"):
            fail(f"mock aggregate question totals mismatch: {key}")
        if sum(row.get("totalMarks", 0) for row in rows) != mock.get("totalMarks"):
            fail(f"mock aggregate mark totals mismatch: {key}")
    difficulty = mock.get("difficulty")
    bands = difficulty.get("bands") if isinstance(difficulty, dict) else None
    if not isinstance(bands, list) or sum(row.get("questionCount", 0) for row in bands) != mock.get("questionCount"):
        fail("mock aggregate difficulty-band totals mismatch")

    expected_indexes = build_reverse_indexes(official)
    if indexes != expected_indexes:
        fail("exam evidence reverse indexes are stale")
    artifacts = manifest.get("artifacts", {})
    artifact_paths = {
        "officialQuestions": OFFICIAL_FILE,
        "mockAggregate": MOCK_FILE,
        "indexes": INDEX_FILE,
        "officialQuestionsSchema": SCHEMA_FILES[0],
        "mockAggregateSchema": SCHEMA_FILES[1],
        "indexesSchema": SCHEMA_FILES[2],
    }
    if set(artifacts) != set(artifact_paths):
        fail("exam evidence manifest artifact set mismatch")
    for name, relative in artifact_paths.items():
        row = artifacts.get(name, {})
        if row.get("path") != relative.as_posix() or row.get("sha256") != sha256_file(root / relative):
            fail(f"exam evidence manifest hash mismatch: {name}")
    expected_counts = {
        "officialPapers": len(OFFICIAL_YEARS),
        "officialQuestions": question_count,
        "officialMarks": total_marks,
        "mockPapers": mock.get("paperCount"),
        "mockQuestions": mock.get("questionCount"),
    }
    if manifest.get("counts") != expected_counts:
        fail("exam evidence manifest counts mismatch")
    boundaries = manifest.get("truthfulnessBoundary")
    if not isinstance(boundaries, dict) or not all(
        term in str(boundaries.get("year2026", "")) for term in ("非官方原卷", "非官方答案")
    ):
        fail("exam evidence manifest lost the 2026 truthfulness boundary")
    return {
        "officialPapers": len(OFFICIAL_YEARS),
        "officialQuestions": question_count,
        "officialMarks": total_marks,
        "mockPapers": mock.get("paperCount"),
        "mockQuestions": mock.get("questionCount"),
        "indexedMothers": len(indexes.get("byMother", {})),
        "indexedNodes": len(indexes.get("byNode", {})),
    }
