#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from exam_evidence import (
    EVIDENCE_ROOT,
    INDEX_FILE,
    MANIFEST_FILE,
    MOCK_FILE,
    OFFICIAL_FILE,
    OFFICIAL_YEARS,
    RELEASE_VERSION,
    SCHEMA_FILES,
    SCHEMA_VERSION,
    ExamEvidenceError,
    assign_mothers,
    build_mother_catalog,
    build_reverse_indexes,
    derive_error_causes,
    natural_key,
    sha256_file,
    validate_exam_evidence,
    write_json,
)
from validate_project import ROOT, collect_catalog

CANONICAL_INDEX = Path("content/exams/index.v1.json")
REGISTRIES = (
    Path("data/official-ingestion-registry.v1.json"),
    Path("data/mock-ingestion-registry.v1.json"),
)
SUPPRESSION_THRESHOLD = 5


def fail(message: str) -> None:
    raise ExamEvidenceError(message)


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read downstream source {path}: {error}")
    if not isinstance(value, dict):
        fail(f"downstream JSON root must be an object: {path}")
    return value


def resolve_source_file(source: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        fail("downstream packet path is missing")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        fail(f"unsafe downstream packet path: {relative}")
    source = source.resolve()
    resolved = (source / candidate).resolve()
    try:
        resolved.relative_to(source)
    except ValueError:
        fail(f"downstream packet escapes source root: {relative}")
    if not resolved.is_file():
        fail(f"downstream packet does not exist: {relative}")
    return resolved


def load_packet_rows(source: Path) -> tuple[dict[str, object], list[tuple[str, str, dict[str, object]]]]:
    index_path = resolve_source_file(source, CANONICAL_INDEX.as_posix())
    index = read_json(index_path)
    if index.get("schema") != "yansuan/canonical-exam-index@1" or index.get("runtimeCutover") is not True:
        fail("downstream canonical exam index is not the active v1 runtime source")

    rows: list[tuple[str, str, dict[str, object]]] = []
    seen: set[str] = set()
    for entry in index.get("papers", []):
        if not isinstance(entry, dict):
            fail("invalid paper entry in downstream canonical index")
        paper_id = entry.get("paperId")
        corpus = entry.get("corpus")
        if not isinstance(paper_id, str) or corpus not in {"official", "mock"}:
            fail("invalid paper identity/corpus in downstream canonical index")
        packet = read_json(resolve_source_file(source, entry.get("packet")))
        rows.append((paper_id, corpus, packet))
        seen.add(paper_id)

    for registry_relative in REGISTRIES:
        registry = read_json(resolve_source_file(source, registry_relative.as_posix()))
        for entry in registry.get("entries", []):
            if not isinstance(entry, dict) or entry.get("enabled") is not True:
                continue
            paper_id = entry.get("paperId")
            if not isinstance(paper_id, str) or paper_id in seen:
                continue
            corpus = "official" if registry_relative.name.startswith("official") else "mock"
            packet = read_json(resolve_source_file(source, entry.get("packet")))
            rows.append((paper_id, corpus, packet))
            seen.add(paper_id)
    return index, rows


def packet_paper(paper_id: str, corpus: str, packet: dict[str, object]) -> dict[str, object]:
    paper = packet.get("paper")
    if not isinstance(paper, dict):
        fail(f"packet has no paper object: {paper_id}")
    if paper.get("id") != paper_id or paper.get("corpus") != corpus:
        fail(f"packet identity/corpus mismatch: {paper_id}")
    questions = paper.get("questions")
    if not isinstance(questions, list) or not questions:
        fail(f"packet has no questions: {paper_id}")
    return paper


def safe_tags(question: dict[str, object], catalog) -> tuple[list[str], list[str], list[str]]:
    tags = question.get("knowledgeTags")
    if not isinstance(tags, list) or not tags:
        fail(f"question has no explicit knowledge tags: {question.get('id')}")
    core: list[str] = []
    support: list[str] = []
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("nodeId"), str):
            fail(f"invalid knowledge tag: {question.get('id')}")
        node_id = tag["nodeId"]
        if node_id not in catalog.topics:
            fail(f"unknown upstream node {node_id}: {question.get('id')}")
        destination = core if tag.get("relation") == "core" else support
        if node_id not in destination:
            destination.append(node_id)
    if not core:
        core.append(support.pop(0))
    node_ids = sorted(set(core) | set(support), key=natural_key)
    return node_ids, sorted(core, key=natural_key), sorted(support, key=natural_key)


def safe_question(question: dict[str, object], catalog, mothers) -> dict[str, object]:
    question_id = question.get("id")
    year = question.get("year")
    if year is None and isinstance(question_id, str) and len(question_id) >= 4:
        try:
            year = int(question_id[:4])
        except ValueError:
            pass
    difficulty = question.get("difficulty100")
    if not isinstance(difficulty, dict):
        fail(f"question has no 100-point difficulty: {question_id}")
    difficulty_score = difficulty.get("score")
    difficulty_band = difficulty.get("band")
    if not isinstance(difficulty_score, int) or not isinstance(difficulty_band, str):
        fail(f"invalid 100-point difficulty: {question_id}")
    node_ids, core, support = safe_tags(question, catalog)
    subject = question.get("subject")
    if not isinstance(subject, str):
        fail(f"question subject is missing: {question_id}")
    primary, auxiliary, route_label = assign_mothers(subject, core, support, mothers)
    return {
        "id": question_id,
        "year": year,
        "no": question.get("no"),
        "type": question.get("type"),
        "score": question.get("score"),
        "subject": subject,
        "difficulty100": difficulty_score,
        "difficultyBand": difficulty_band,
        "nodeIds": node_ids,
        "coreNodeIds": core,
        "supportNodeIds": support,
        "primaryMotherId": primary,
        "auxiliaryMotherIds": auxiliary,
        "routeLabel": route_label,
        "errorCauseTags": derive_error_causes(difficulty),
    }


def build_official(rows, catalog, mothers) -> dict[str, object]:
    papers: list[dict[str, object]] = []
    official_rows = [(paper_id, packet) for paper_id, corpus, packet in rows if corpus == "official"]
    official_rows.sort(key=lambda row: row[0])
    for paper_id, packet in official_rows:
        paper = packet_paper(paper_id, "official", packet)
        year = paper.get("year")
        if year not in OFFICIAL_YEARS:
            continue
        questions = [safe_question(question, catalog, mothers) for question in paper["questions"]]
        questions.sort(key=lambda question: question["no"])
        output: dict[str, object] = {
            "year": year,
            "status": "reconstructed" if year == 2026 else "official-archive",
            "boundaryNote": (
                "考后重构、多源交叉、答案经模型独立复算；非官方原卷、非官方答案，不代表人工确认。"
                if year == 2026
                else "仅确认考试年份与数学（一）归档身份；本索引不发布题面、答案或解析。"
            ),
            "questionCount": len(questions),
            "totalScore": sum(question["score"] for question in questions),
            "questions": questions,
        }
        if year == 2026:
            source = paper.get("source") if isinstance(paper.get("source"), dict) else {}
            if source.get("officialSourceAvailable") is not False or source.get("officialAnswerAvailable") is not False:
                fail("downstream 2026 source does not preserve the required non-official boundary")
            output["officialOriginalAvailable"] = False
            output["officialAnswerAvailable"] = False
        papers.append(output)
    years = tuple(paper["year"] for paper in papers)
    if years != OFFICIAL_YEARS:
        fail(f"downstream official coverage must be exactly 2010-2026: {years}")
    question_count = sum(paper["questionCount"] for paper in papers)
    total_marks = sum(paper["totalScore"] for paper in papers)
    return {
        "$schema": "kaoyan-math1/exam-evidence/official-questions@1",
        "schemaVersion": SCHEMA_VERSION,
        "scope": {
            "startYear": OFFICIAL_YEARS[0],
            "endYear": OFFICIAL_YEARS[-1],
            "paperCount": len(papers),
            "questionCount": question_count,
            "totalMarks": total_marks,
        },
        "rightsBoundary": {
            "mode": "metadata-only",
            "includedFields": [
                "year",
                "question number",
                "question type",
                "score",
                "knowledge node",
                "mother archetype",
                "difficulty",
                "short route label",
                "derived error-cause tag",
            ],
            "excludedFields": ["prompt", "answer", "analysis", "diagram", "pitfalls", "source files"],
            "note": "索引只发布事实性元数据与本仓库知识体系的衍生挂接，不复制完整题面、答案或解析。",
        },
        "papers": papers,
    }


def aggregate_rows(counter: Counter[str], id_key: str) -> list[dict[str, object]]:
    return [
        {id_key: key, "questionCount": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], natural_key(item[0])))
        if count >= SUPPRESSION_THRESHOLD
    ]


def summarized_group(stats: dict[str, list[int]], marks: Counter[str]) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "questionCount": len(scores),
            "totalMarks": marks[name],
            "meanDifficulty100": round(sum(scores) / len(scores), 2),
        }
        for name, scores in sorted(stats.items())
    ]


def build_mock(rows, catalog, mothers) -> dict[str, object]:
    paper_count = 0
    question_count = 0
    total_marks = 0
    years: set[int] = set()
    scores: list[int] = []
    bands: Counter[str] = Counter()
    subjects: dict[str, list[int]] = defaultdict(list)
    subject_marks: Counter[str] = Counter()
    types: dict[str, list[int]] = defaultdict(list)
    type_marks: Counter[str] = Counter()
    nodes: Counter[str] = Counter()
    mother_ids: Counter[str] = Counter()
    for paper_id, corpus, packet in rows:
        if corpus != "mock":
            continue
        paper = packet_paper(paper_id, corpus, packet)
        paper_count += 1
        if isinstance(paper.get("year"), int):
            years.add(paper["year"])
        for question in paper["questions"]:
            safe = safe_question(question, catalog, mothers)
            score = safe["difficulty100"]
            mark = safe["score"]
            question_count += 1
            total_marks += mark
            scores.append(score)
            bands[safe["difficultyBand"]] += 1
            subjects[safe["subject"]].append(score)
            subject_marks[safe["subject"]] += mark
            types[safe["type"]].append(score)
            type_marks[safe["type"]] += mark
            nodes.update(safe["nodeIds"])
            mother_ids.update([safe["primaryMotherId"], *safe["auxiliaryMotherIds"]])
    if not scores:
        fail("downstream mock corpus is empty")
    return {
        "$schema": "kaoyan-math1/exam-evidence/mock-aggregate@1",
        "schemaVersion": SCHEMA_VERSION,
        "privacyMode": "anonymous-aggregate-only",
        "itemLevelPublished": False,
        "suppressionThreshold": SUPPRESSION_THRESHOLD,
        "paperCount": paper_count,
        "questionCount": question_count,
        "totalMarks": total_marks,
        "years": sorted(years),
        "bySubject": summarized_group(subjects, subject_marks),
        "byQuestionType": summarized_group(types, type_marks),
        "difficulty": {
            "minimum": min(scores),
            "maximum": max(scores),
            "mean": round(sum(scores) / len(scores), 2),
            "bands": [{"name": name, "questionCount": count} for name, count in sorted(bands.items())],
        },
        "topNodes": aggregate_rows(nodes, "nodeId"),
        "topMothers": aggregate_rows(mother_ids, "motherId"),
        "rightsBoundary": {
            "mode": "anonymous-aggregate-only",
            "note": "来源再发布权未逐项确认；不公开卷名、机构、逐题身份、题面、答案、解析或路线。",
        },
    }


def build_manifest(source: Path, source_index: dict[str, object], official, mock) -> dict[str, object]:
    artifact_paths = {
        "officialQuestions": OFFICIAL_FILE,
        "mockAggregate": MOCK_FILE,
        "indexes": INDEX_FILE,
        "officialQuestionsSchema": SCHEMA_FILES[0],
        "mockAggregateSchema": SCHEMA_FILES[1],
        "indexesSchema": SCHEMA_FILES[2],
    }
    source_index_path = source / CANONICAL_INDEX
    baseline = source_index.get("baseline") if isinstance(source_index.get("baseline"), dict) else {}
    return {
        "$schema": "kaoyan-math1/exam-evidence/manifest@1",
        "schemaVersion": SCHEMA_VERSION,
        "releaseVersion": RELEASE_VERSION,
        "generatedAt": source_index.get("generatedAt"),
        "sourceSnapshot": {
            "project": "yansuan-protocol-local-private-layer",
            "canonicalSchema": source_index.get("schema"),
            "baselineId": baseline.get("id"),
            "baselineSemanticHash": baseline.get("semanticHash"),
            "canonicalIndexSha256": hashlib.sha256(source_index_path.read_bytes()).hexdigest(),
            "officialYearRange": [OFFICIAL_YEARS[0], OFFICIAL_YEARS[-1]],
        },
        "truthfulnessBoundary": {
            "official": "2010—2025 仅作官方年份/科目归档索引；不发布题面、答案或解析。",
            "year2026": "考后重构；非官方原卷、非官方答案。",
            "mock": "仅匿名聚合；再发布权未确认的卷材不进入逐题公开索引。",
        },
        "counts": {
            "officialPapers": official["scope"]["paperCount"],
            "officialQuestions": official["scope"]["questionCount"],
            "officialMarks": official["scope"]["totalMarks"],
            "mockPapers": mock["paperCount"],
            "mockQuestions": mock["questionCount"],
        },
        "artifacts": {
            name: {"path": relative.as_posix(), "sha256": sha256_file(ROOT / relative)}
            for name, relative in artifact_paths.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a copyright-safe public exam evidence index.")
    parser.add_argument("--source", required=True, type=Path, help="Path to the local downstream 研算协议 project")
    parser.add_argument("--write", action="store_true", help="Write generated artifacts to data/exam-evidence/v1")
    args = parser.parse_args()
    try:
        source = args.source.resolve()
        if not source.is_dir():
            fail(f"downstream source directory does not exist: {source}")
        catalog = collect_catalog(ROOT)
        mothers = build_mother_catalog(catalog)
        source_index, rows = load_packet_rows(source)
        official = build_official(rows, catalog, mothers)
        mock = build_mock(rows, catalog, mothers)
        indexes = build_reverse_indexes(official)
        if not args.write:
            print(json.dumps({"official": official["scope"], "mockPapers": mock["paperCount"], "mockQuestions": mock["questionCount"]}, ensure_ascii=False, indent=2))
            print("Dry run only; pass --write to update public artifacts.")
            return 0
        (ROOT / EVIDENCE_ROOT).mkdir(parents=True, exist_ok=True)
        write_json(ROOT / OFFICIAL_FILE, official)
        write_json(ROOT / MOCK_FILE, mock)
        write_json(ROOT / INDEX_FILE, indexes)
        for schema in SCHEMA_FILES:
            if not (ROOT / schema).is_file():
                fail(f"schema must exist before import: {schema.as_posix()}")
        write_json(ROOT / MANIFEST_FILE, build_manifest(source, source_index, official, mock))
        stats = validate_exam_evidence(ROOT, catalog)
    except (ExamEvidenceError, OSError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {EVIDENCE_ROOT.as_posix()}")
    print(f"  official: {stats['officialPapers']} papers, {stats['officialQuestions']} questions, {stats['officialMarks']} marks")
    print(f"  mock:     {stats['mockPapers']} papers, {stats['mockQuestions']} questions (anonymous aggregate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
