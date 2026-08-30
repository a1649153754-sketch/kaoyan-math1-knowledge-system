#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

TOPIC_FILES = (
    "docs/01-calculus.md",
    "docs/02-linear-algebra.md",
    "docs/03-probability-statistics.md",
    "docs/04-method-library.md",
)
REQUIRED_CHAPTER_HEADINGS = (
    "真题证据概览",
    "节点执行卡",
    "章末路线选择",
    "达标标准",
    "来源与证据边界",
)
REQUIRED_FIELDS = ("触发信号", "适用条件", "执行动作", "失效边界", "母题证据", "来源", "温柔讲解")
EXPLANATION_LABELS = ("为什么成立", "怎么用", "小例题 / 路线演示", "哪里会失效")
CHAPTER_RE = re.compile(r"^##\s+([HLPM]\d+)\b")
NODE_RE = re.compile(r"^-\s+([HLPM]\d+\.\d+)\s+(.+)$")
CARD_HEADER_RE = re.compile(r"^####\s+([HLPM]\d+\.\d+)\s+(.+)$")
FIELD_RE = re.compile(r"^-\s+\*\*(触发信号|适用条件|执行动作|失效边界|母题证据|来源|温柔讲解)\*\*：(.+)$")
EXPLANATION_RE = re.compile(r"^###\s+核心讲解(?:\d+|[一二三四五六七八九十]+)：(.+)$")
EVIDENCE_RE = re.compile(
    r"公开真题\s+(\d+)\s+题，挂接分值\s+(\d+)\s+分，平均难度\s+(暂无|\d+(?:\.\d+)?)"
)
MOTHER_ID_RE = re.compile(r"`(Q-[HLPM]\d+)`")
SOURCE_ID_RE = re.compile(r"\b([SE]-[HLPM]\d+-\d+)\b")
SOURCE_DEFINITION_RE = re.compile(r"^-\s+\*\*([SE]-[HLPM]\d+-\d+)\*\*：")


class ContentAuditError(RuntimeError):
    """A chapter execution card, explanation, or evidence claim is invalid."""


def fail(message: str) -> None:
    raise ContentAuditError(message)


def _load_json(root: Path, relative: str) -> dict[str, object]:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {relative} for content audit: {error}")
    if not isinstance(value, dict):
        fail(f"{relative} root must be an object")
    return value


def _released_nodes(root: Path) -> set[str]:
    baseline = _load_json(root, "data/released-identities.v1.json")
    nodes = baseline.get("knowledgeNodes")
    if not isinstance(nodes, list) or not all(isinstance(value, str) for value in nodes):
        fail("released identity baseline has no valid knowledgeNodes list")
    return set(nodes)


def _evidence_by_node(root: Path) -> dict[str, dict[str, object]]:
    official = _load_json(root, "data/exam-evidence/v1/official-questions.json")
    rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    mothers: dict[str, set[str]] = defaultdict(set)
    for paper in official.get("papers", []):
        for question in paper.get("questions", []):
            for node_id in set(question.get("nodeIds", [])):
                rows[node_id].append(question)
                primary = question.get("primaryMotherId")
                if isinstance(primary, str):
                    mothers[node_id].add(primary)
                mothers[node_id].update(
                    value for value in question.get("auxiliaryMotherIds", []) if isinstance(value, str)
                )
    result: dict[str, dict[str, object]] = {}
    for node_id in set(rows) | set(mothers):
        linked = rows[node_id]
        result[node_id] = {
            "count": len(linked),
            "score": sum(int(row["score"]) for row in linked),
            "difficulty": (
                sum(int(row["difficulty100"]) for row in linked) / len(linked) if linked else None
            ),
            "mothers": mothers[node_id],
        }
    return result


def _short_title(description: str) -> str:
    return description.rstrip("。").split("：", 1)[0]


def _chapter_sections(text: str, relative: str) -> list[tuple[str, list[str]]]:
    lines = text.splitlines()
    starts = [(index, match.group(1)) for index, line in enumerate(lines) if (match := CHAPTER_RE.match(line))]
    if not starts:
        fail(f"no formal chapters discovered in {relative}")
    result: list[tuple[str, list[str]]] = []
    for position, (start, chapter) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        result.append((chapter, lines[start:end]))
    return result


def _require_chapter_structure(chapter: str, section: list[str]) -> None:
    for heading in REQUIRED_CHAPTER_HEADINGS:
        if not any(line.startswith(f"### {heading}") for line in section):
            fail(f"required chapter section missing in {chapter}: {heading}")


def _formal_nodes(chapter: str, section: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section:
        match = NODE_RE.match(line)
        if not match:
            continue
        node_id, description = match.groups()
        if node_id.split(".", 1)[0] != chapter:
            continue
        if node_id in result:
            fail(f"duplicate formal node definition: {node_id}")
        result[node_id] = description.strip()
    if not result:
        fail(f"formal node list missing for chapter: {chapter}")
    return result


def _cards(section: list[str]) -> dict[str, dict[str, object]]:
    cards: dict[str, dict[str, object]] = {}
    current: str | None = None
    for line in section:
        header = CARD_HEADER_RE.match(line)
        if header:
            current, title = header.groups()
            if current in cards:
                fail(f"duplicate execution card: {current}")
            cards[current] = {"title": title.strip(), "fields": {}}
            continue
        field = FIELD_RE.match(line)
        if field and current is not None:
            name, value = field.groups()
            fields = cards[current]["fields"]
            if name in fields:
                fail(f"duplicate {name} field in execution card: {current}")
            fields[name] = value.strip()
    return cards


def _explanations(chapter: str, section: list[str], minimum: int) -> int:
    starts = [(index, match.group(1)) for index, line in enumerate(section) if (match := EXPLANATION_RE.match(line))]
    if len(starts) < minimum:
        fail(f"required detailed explanations missing in {chapter}: expected>={minimum}, actual={len(starts)}")
    for start, title in starts:
        end = next(
            (index for index in range(start + 1, len(section)) if section[index].startswith("### ")),
            len(section),
        )
        body = "\n".join(section[start + 1 : end]).strip()
        if len(body) < 400:
            fail(f"detailed explanation is too short in {chapter}: {title}")
        for label in EXPLANATION_LABELS:
            if f"**{label}**：" not in body:
                fail(f"detailed explanation lacks '{label}' in {chapter}: {title}")
    return len(starts)


def _validate_evidence(node_id: str, claim: str, actual: dict[str, object]) -> bool:
    match = EVIDENCE_RE.search(claim)
    if not match:
        fail(f"mother evidence fields are incomplete for {node_id}")
    claimed_count, claimed_score, claimed_difficulty = match.groups()
    count = int(actual.get("count", 0))
    score = int(actual.get("score", 0))
    difficulty = actual.get("difficulty")
    if int(claimed_count) != count:
        fail(f"stale public question count for {node_id}: claimed={claimed_count}, actual={count}")
    if int(claimed_score) != score:
        fail(f"stale linked score for {node_id}: claimed={claimed_score}, actual={score}")
    if count == 0:
        if claimed_difficulty != "暂无":
            fail(f"zero-evidence node has invented difficulty: {node_id}")
        if MOTHER_ID_RE.search(claim):
            fail(f"zero-evidence node has invented mother link: {node_id}")
        return True
    if claimed_difficulty == "暂无" or abs(float(claimed_difficulty) - float(difficulty)) > 0.051:
        fail(
            f"stale average difficulty for {node_id}: "
            f"claimed={claimed_difficulty}, actual={float(difficulty):.1f}"
        )
    cited = set(MOTHER_ID_RE.findall(claim))
    valid_mothers = set(actual.get("mothers", set()))
    if not cited or not cited.issubset(valid_mothers):
        fail(f"unknown or missing mother evidence for {node_id}: {sorted(cited - valid_mothers)}")
    return False


def validate_content_audits(root: Path) -> dict[str, object]:
    root = root.resolve()
    released_nodes = _released_nodes(root)
    evidence = _evidence_by_node(root)
    discovered_nodes: set[str] = set()
    discovered_chapters: set[str] = set()
    explanation_count = 0
    zero_evidence_nodes = 0
    gentle_explanations: dict[str, str] = {}

    for relative in TOPIC_FILES:
        try:
            text = (root / relative).read_text(encoding="utf-8").lstrip("\ufeff")
        except OSError as error:
            fail(f"cannot read topic body {relative}: {error}")
        for chapter, section in _chapter_sections(text, relative):
            if chapter in discovered_chapters:
                fail(f"duplicate chapter across topic bodies: {chapter}")
            discovered_chapters.add(chapter)
            _require_chapter_structure(chapter, section)
            formal = _formal_nodes(chapter, section)
            cards = _cards(section)
            if set(cards) != set(formal):
                missing = sorted(set(formal) - set(cards))
                extra = sorted(set(cards) - set(formal))
                fail(f"execution card coverage mismatch for {chapter}: missing={missing}, extra={extra}")
            source_definitions = {
                match.group(1) for line in section if (match := SOURCE_DEFINITION_RE.match(line))
            }
            for node_id, description in formal.items():
                discovered_nodes.add(node_id)
                card = cards[node_id]
                expected_title = _short_title(description)
                if card["title"] != expected_title:
                    fail(
                        f"execution card title mismatch for {node_id}: "
                        f"expected='{expected_title}', actual='{card['title']}'"
                    )
                fields = card["fields"]
                missing_fields = [name for name in REQUIRED_FIELDS if not fields.get(name)]
                if missing_fields:
                    fail(f"execution card fields missing for {node_id}: {missing_fields}")
                gentle = str(fields["温柔讲解"])
                if len(gentle) < 220:
                    fail(f"gentle explanation is too short for {node_id}: {len(gentle)} characters")
                if f"`{node_id}`" not in gentle:
                    fail(f"gentle explanation is not tied to its node ID: {node_id}")
                if not any(marker in gentle for marker in ("别急", "慢一点", "没关系", "稳稳", "不用", "不妨", "轻轻", "温顺", "责怪")):
                    fail(f"gentle explanation lacks a supportive tone marker: {node_id}")
                if gentle in gentle_explanations:
                    fail(
                        f"duplicate gentle explanation for {node_id} and "
                        f"{gentle_explanations[gentle]}"
                    )
                gentle_explanations[gentle] = node_id
                zero_evidence_nodes += int(
                    _validate_evidence(
                        node_id,
                        str(fields["母题证据"]),
                        evidence.get(node_id, {"count": 0, "score": 0, "difficulty": None, "mothers": set()}),
                    )
                )
                source_ids = set(SOURCE_ID_RE.findall(str(fields["来源"])))
                unknown = source_ids - source_definitions
                if not source_ids or unknown:
                    fail(f"unknown or missing source IDs for {node_id}: {sorted(unknown)}")
                if not any(value.startswith("S-") for value in source_ids):
                    fail(f"execution card has no mathematical source: {node_id}")
                if not any(value.startswith("E-") for value in source_ids):
                    fail(f"execution card has no evidence source: {node_id}")
            explanation_count += _explanations(chapter, section, 3 if len(formal) >= 8 else 2)

    if discovered_nodes != released_nodes:
        missing = sorted(released_nodes - discovered_nodes)
        extra = sorted(discovered_nodes - released_nodes)
        fail(f"formal node coverage differs from released baseline: missing={missing}, extra={extra}")
    return {
        "auditedChapters": sorted(discovered_chapters),
        "auditedNodes": len(discovered_nodes),
        "detailedExplanations": explanation_count,
        "gentleExplanations": len(gentle_explanations),
        "zeroEvidenceNodes": zero_evidence_nodes,
    }
