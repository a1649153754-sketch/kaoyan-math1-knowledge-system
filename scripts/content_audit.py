#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

AUDITED_CHAPTERS = {
    "H2": {
        "file": "docs/01-calculus.md",
        "nodes": tuple(f"H2.{number}" for number in range(1, 11)),
        "explanations": (),
    },
    "H3": {
        "file": "docs/01-calculus.md",
        "nodes": tuple(f"H3.{number}" for number in range(1, 12)),
        "explanations": (
            "核心讲解一：换元与分部为什么有效",
            "核心讲解二：定积分与导数为什么互逆",
            "核心讲解三：反常积分先判极限，再谈计算",
            "核心讲解四：应用题统一成“强度 × 微元”",
        ),
    },
}
REQUIRED_FIELDS = ("触发信号", "适用条件", "执行动作", "失效边界", "母题证据", "来源")
CARD_HEADER_RE = re.compile(r"^####\s+([HLPM]\d+\.\d+)\s+(.+)$")
FIELD_RE = re.compile(r"^-\s+\*\*(触发信号|适用条件|执行动作|失效边界|母题证据|来源)\*\*：(.+)$")
EVIDENCE_COUNT_RE = re.compile(r"公开真题\s+(\d+)\s+题")
SOURCE_ID_RE = re.compile(r"\b([SE]-[HLPM]\d+-\d+)\b")
SOURCE_DEFINITION_RE = re.compile(r"^-\s+\*\*([SE]-[HLPM]\d+-\d+)\*\*：")


class ContentAuditError(RuntimeError):
    """A chapter execution card or evidence claim is incomplete/stale."""


def fail(message: str) -> None:
    raise ContentAuditError(message)


def _read_official(root: Path) -> dict[str, object]:
    relative = Path("data/exam-evidence/v1/official-questions.json")
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read exam evidence for content audit: {error}")
    if not isinstance(value, dict):
        fail("official exam evidence root must be an object")
    return value


def _question_counts(official: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paper in official.get("papers", []):
        for question in paper.get("questions", []):
            for node_id in set(question.get("nodeIds", [])):
                counts[node_id] = counts.get(node_id, 0) + 1
    return counts


def _chapter_section(text: str, chapter: str, relative: str) -> list[str]:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if re.match(rf"^##\s+{re.escape(chapter)}\b", line)), None)
    if start is None:
        fail(f"audited chapter heading missing: {chapter} in {relative}")
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return lines[start:end]


def validate_content_audits(root: Path) -> dict[str, object]:
    root = root.resolve()
    counts = _question_counts(_read_official(root))
    audited_nodes = 0
    for chapter, config in AUDITED_CHAPTERS.items():
        relative = config["file"]
        text = (root / relative).read_text(encoding="utf-8").lstrip("\ufeff")
        section = _chapter_section(text, chapter, relative)
        source_definitions = {
            match.group(1)
            for line in section
            if (match := SOURCE_DEFINITION_RE.match(line))
        }
        cards: dict[str, dict[str, str]] = {}
        current: str | None = None
        for line in section:
            header = CARD_HEADER_RE.match(line)
            if header:
                current = header.group(1)
                if current in cards:
                    fail(f"duplicate execution card: {current}")
                cards[current] = {}
                continue
            field = FIELD_RE.match(line)
            if field and current is not None:
                name, value = field.groups()
                if name in cards[current]:
                    fail(f"duplicate {name} field in execution card: {current}")
                cards[current][name] = value.strip()

        expected_nodes = tuple(config["nodes"])
        if set(cards) != set(expected_nodes):
            missing = sorted(set(expected_nodes) - set(cards))
            extra = sorted(set(cards) - set(expected_nodes))
            fail(f"execution card coverage mismatch for {chapter}: missing={missing}, extra={extra}")
        for node_id in expected_nodes:
            fields = cards[node_id]
            missing_fields = [name for name in REQUIRED_FIELDS if not fields.get(name)]
            if missing_fields:
                fail(f"execution card fields missing for {node_id}: {missing_fields}")
            evidence_match = EVIDENCE_COUNT_RE.search(fields["母题证据"])
            if not evidence_match:
                fail(f"mother evidence has no public question count: {node_id}")
            claimed = int(evidence_match.group(1))
            actual = counts.get(node_id, 0)
            if claimed != actual:
                fail(f"stale public question count for {node_id}: claimed={claimed}, actual={actual}")
            source_ids = set(SOURCE_ID_RE.findall(fields["来源"]))
            if not source_ids or not source_ids.issubset(source_definitions):
                fail(f"unknown or missing source IDs for {node_id}: {sorted(source_ids - source_definitions)}")
            if not any(source_id.startswith("S-") for source_id in source_ids):
                fail(f"execution card has no mathematical source: {node_id}")
            if not any(source_id.startswith("E-") for source_id in source_ids):
                fail(f"execution card has no evidence source: {node_id}")
            audited_nodes += 1
        for heading in config["explanations"]:
            marker = f"### {heading}"
            try:
                start = section.index(marker)
            except ValueError:
                fail(f"required detailed explanation missing in {chapter}: {heading}")
            end = next(
                (index for index in range(start + 1, len(section)) if section[index].startswith("### ")),
                len(section),
            )
            explanation = "\n".join(section[start + 1 : end]).strip()
            if len(explanation) < 400:
                fail(f"detailed explanation is too short in {chapter}: {heading}")
    return {"auditedChapters": sorted(AUDITED_CHAPTERS), "auditedNodes": audited_nodes}
