#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = Path("data/sprint-guide/v1/selection.json")
OUTPUT_PATH = Path("docs/17-sprint-manual.md")
TOPIC_FILES = (
    "docs/01-calculus.md",
    "docs/02-linear-algebra.md",
    "docs/03-probability-statistics.md",
    "docs/04-method-library.md",
)
EXPECTED_RULES = {
    "minimumQuestionCount": 8,
    "minimumLinkedScore": 40,
    "minimumCrossChapterQuestionCount": 6,
    "difficultyAlternative": {"minimumAverageDifficulty": 50, "minimumQuestionCount": 4},
}
EXPECTED_FORMULA_SELECTION = {
    "selectionMode": "candidate-chapter round-robin",
    "domainQuotas": {"H": 36, "L": 14, "P": 14},
    "chapterOrder": "descending candidate impact",
    "withinChapterOrder": "memory-risk rank then stable formula ID",
}
NODE_RE = re.compile(r"^-\s+([HLPM]\d+\.\d+)\s+(.+)$", re.MULTILINE)
CARD_RE = re.compile(
    r"^####\s+([HLPM]\d+\.\d+)\s+.+?\n(?P<body>.*?)(?=^####\s+[HLPM]\d+\.\d+\b|^###\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
ACTION_RE = re.compile(r"^- \*\*执行动作\*\*：(.+)$", re.MULTILINE)


class SprintManualError(RuntimeError):
    """The v1.5 sprint selection or generated manual is invalid."""


def fail(message: str) -> None:
    raise SprintManualError(message)


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {path}")
    return value


def _natural_node(node_id: str) -> tuple[str, int, int]:
    match = re.fullmatch(r"([HLPM])(\d+)\.(\d+)", node_id)
    if not match:
        fail(f"invalid formal node ID in sprint selection: {node_id}")
    return match.group(1), int(match.group(2)), int(match.group(3))


def _topic_nodes(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    titles: dict[str, str] = {}
    actions: dict[str, str] = {}
    for relative in TOPIC_FILES:
        text = (root / relative).read_text(encoding="utf-8").lstrip("\ufeff")
        for match in NODE_RE.finditer(text):
            node_id, description = match.groups()
            if node_id in titles:
                fail(f"duplicate formal node while building sprint manual: {node_id}")
            titles[node_id] = description.rstrip("。").split("：", 1)[0]
        for match in CARD_RE.finditer(text):
            action = ACTION_RE.search(match.group("body"))
            if action:
                actions[match.group(1)] = action.group(1).strip()
    missing_actions = sorted(set(titles) - set(actions), key=_natural_node)
    if missing_actions:
        fail(f"formal nodes lack execution actions: {missing_actions}")
    return titles, actions


def _evidence_stats(root: Path) -> dict[str, dict[str, float | int]]:
    official = _load_json(root / "data/exam-evidence/v1/official-questions.json")
    rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    cross: dict[str, int] = defaultdict(int)
    for paper in official.get("papers", []):
        for question in paper.get("questions", []):
            nodes = set(question.get("nodeIds", []))
            chapters = {str(value).split(".", 1)[0] for value in nodes}
            for node_id in nodes:
                rows[node_id].append(question)
                if len(chapters) > 1:
                    cross[node_id] += 1
    result: dict[str, dict[str, float | int]] = {}
    for node_id, linked in rows.items():
        result[node_id] = {
            "questionCount": len(linked),
            "linkedScore": sum(int(row["score"]) for row in linked),
            "averageDifficulty": sum(int(row["difficulty100"]) for row in linked) / len(linked),
            "crossChapterQuestionCount": cross[node_id],
        }
    return result


def _objective_candidates(stats: dict[str, dict[str, float | int]]) -> list[str]:
    selected: list[str] = []
    for node_id, value in stats.items():
        count = int(value["questionCount"])
        score = int(value["linkedScore"])
        cross = int(value["crossChapterQuestionCount"])
        difficulty = float(value["averageDifficulty"])
        if count >= 8 or score >= 40 or cross >= 6 or (difficulty >= 50 and count >= 4):
            selected.append(node_id)
    return sorted(selected, key=_natural_node)


def _table_parts(line: str) -> list[str]:
    return [value.strip() for value in re.split(r"(?<!\\)\|", line)[1:-1]]


def _table_rows(root: Path, relative: str, id_pattern: str) -> dict[str, list[str]]:
    compiled = re.compile(id_pattern)
    rows: dict[str, list[str]] = {}
    for line in (root / relative).read_text(encoding="utf-8").splitlines():
        parts = _table_parts(line) if line.startswith("|") else []
        if parts and compiled.fullmatch(parts[0]):
            if parts[0] in rows:
                fail(f"duplicate table identity: {parts[0]}")
            rows[parts[0]] = parts
    return rows


def _memory_rank(memory: str) -> int:
    if "[背]" in memory and "[慎]" in memory:
        rank = 0
    elif "[背]" in memory:
        rank = 1
    elif "[慎]" in memory:
        rank = 2
    elif "[推]" in memory:
        rank = 3
    else:
        rank = 4
    return rank + (10 if "[拓]" in memory else 0)


def _expected_formulas(
    formula_rows: dict[str, list[str]],
    candidates: list[str],
    stats: dict[str, dict[str, float | int]],
) -> list[str]:
    impact: dict[str, float] = defaultdict(float)
    for node_id in candidates:
        value = stats[node_id]
        impact[node_id.split(".", 1)[0]] += (
            2 * int(value["questionCount"])
            + int(value["linkedScore"])
            + 3 * int(value["crossChapterQuestionCount"])
            + float(value["averageDifficulty"]) / 10
        )
    by_chapter: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for formula_id, row in formula_rows.items():
        chapter = formula_id.split("-")[1]
        by_chapter[chapter].append((_memory_rank(row[3]), formula_id))
    for rows in by_chapter.values():
        rows.sort()

    result: list[str] = []
    for domain, quota in EXPECTED_FORMULA_SELECTION["domainQuotas"].items():
        chapters = sorted(
            (chapter for chapter in by_chapter if chapter.startswith(domain) and impact[chapter] > 0),
            key=lambda chapter: (-impact[chapter], int(chapter[1:])),
        )
        positions = {chapter: 0 for chapter in chapters}
        domain_result: list[str] = []
        while len(domain_result) < quota:
            advanced = False
            for chapter in chapters:
                position = positions[chapter]
                if position < len(by_chapter[chapter]) and len(domain_result) < quota:
                    domain_result.append(by_chapter[chapter][position][1])
                    positions[chapter] += 1
                    advanced = True
            if not advanced:
                fail(f"not enough {domain} formulas to satisfy quota {quota}")
        result.extend(domain_result)
    return result


def _theorem_sections(root: Path) -> dict[str, tuple[str, str]]:
    text = (root / "docs/07-theorem-index.md").read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##\s+(7\.\d+)\s+(.+)$", text, re.MULTILINE))
    result: dict[str, tuple[str, str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1)] = (match.group(2).strip(), text[match.end() : end].strip())
    return result


def _unique_list(selection: dict[str, object], key: str) -> list[str]:
    value = selection.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        fail(f"sprint selection field must be a string list: {key}")
    if len(value) != len(set(value)):
        fail(f"sprint selection contains duplicate IDs: {key}")
    return value


def validate_sprint_selection(root: Path) -> dict[str, object]:
    root = root.resolve()
    selection = _load_json(root / SELECTION_PATH)
    if selection.get("schemaVersion") != "1.0.0" or selection.get("releaseVersion") != "1.5.0":
        fail("sprint selection schema/release version mismatch")
    if selection.get("candidateRules") != EXPECTED_RULES:
        fail("sprint candidate selection rules drifted")
    if selection.get("formulaSelection") != EXPECTED_FORMULA_SELECTION:
        fail("sprint formula selection rules drifted")

    titles, _ = _topic_nodes(root)
    stats = _evidence_stats(root)
    expected_candidates = _objective_candidates(stats)
    candidates = _unique_list(selection, "objectiveCandidateNodeIds")
    if candidates != expected_candidates:
        fail("objective sprint candidate list does not match evidence rules")

    additions = selection.get("prerequisiteAdditions")
    if not isinstance(additions, list):
        fail("prerequisiteAdditions must be a list")
    added_ids: list[str] = []
    for addition in additions:
        if not isinstance(addition, dict):
            fail("each prerequisite addition must be an object")
        node_id = addition.get("nodeId")
        reason = addition.get("reason")
        if node_id not in titles or not isinstance(reason, str) or not reason.strip():
            fail(f"invalid prerequisite addition: {addition}")
        added_ids.append(node_id)
    if len(added_ids) != len(set(added_ids)) or set(added_ids) & set(candidates):
        fail("prerequisite additions are duplicate or already objective candidates")

    formula_rows = _table_rows(root, "docs/10-formula-cards.md", r"F-[HLP]\d+-\d+")
    formulas = _unique_list(selection, "selectedFormulaIds")
    if len(formulas) > 64 or any(value not in formula_rows for value in formulas):
        fail("sprint formula selection contains unknown IDs or exceeds 64 cards")
    if formulas != _expected_formulas(formula_rows, candidates, stats):
        fail("sprint formula selection drifted from deterministic ranking")

    theorem_sections = _theorem_sections(root)
    theorem_ids = _unique_list(selection, "theoremSectionIds")
    if theorem_ids != list(theorem_sections):
        fail("sprint theorem checklist must contain all source sections in order")

    counter_rows = _table_rows(root, "docs/12-counterexamples.md", r"B-[HLP]\d+")
    counter_ids = _unique_list(selection, "counterexampleIds")
    if counter_ids != list(counter_rows):
        fail("sprint counterexample list must contain all source cards in order")
    return {
        "objectiveCandidates": len(candidates),
        "prerequisiteAdditions": len(added_ids),
        "selectedFormulas": len(formulas),
        "theoremSections": len(theorem_ids),
        "counterexamples": len(counter_ids),
    }


def _selection_reasons(value: dict[str, float | int]) -> str:
    reasons: list[str] = []
    if int(value["questionCount"]) >= 8:
        reasons.append("题数≥8")
    if int(value["linkedScore"]) >= 40:
        reasons.append("挂接分值≥40")
    if int(value["crossChapterQuestionCount"]) >= 6:
        reasons.append("跨章节题数≥6")
    if float(value["averageDifficulty"]) >= 50 and int(value["questionCount"]) >= 4:
        reasons.append("难度≥50且题数≥4")
    return "、".join(reasons)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_sprint_manual(root: Path) -> str:
    root = root.resolve()
    validate_sprint_selection(root)
    selection = _load_json(root / SELECTION_PATH)
    titles, actions = _topic_nodes(root)
    stats = _evidence_stats(root)
    candidates = selection["objectiveCandidateNodeIds"]
    additions = selection["prerequisiteAdditions"]
    formula_rows = _table_rows(root, "docs/10-formula-cards.md", r"F-[HLP]\d+-\d+")
    theorem_sections = _theorem_sections(root)
    counter_rows = _table_rows(root, "docs/12-counterexamples.md", r"B-[HLP]\d+")

    blocks = [
        "# v1.5 冲刺速查手册",
        "",
        "<!-- 此文件由 scripts/build_sprint_manual.py 确定性生成，请勿手工编辑。 -->",
        "",
        "这份手册把全库内容压缩成考前调用入口，但不会替代四份主题正文。候选节点严格由 2010—2026 去题面化真题索引计算；历史高频只决定复习顺序，不构成未来命题承诺。",
        "",
        "## 1. 选择口径",
        "",
        "正式节点满足以下任一条件即进入候选：题数不少于 8、挂接分值不少于 40、跨章节题数不少于 6，或平均难度不少于 50 且题数不少于 4。公式卡按候选章节证据强度排序，在高数、线代、概率三个域内轮转抽取 36/14/14 张；随后完整收录 21 组定理条件和 40 张反例卡。",
        "",
        f"本版共有 **{len(candidates)} 个客观候选节点**、**{len(additions)} 个有理由的前置追加节点**、**{len(selection['selectedFormulaIds'])} 张核心公式卡**。",
        "",
        "## 2. 高频节点与执行路线",
        "",
        "| 节点 | 主题 | 证据（题 / 分 / 跨章 / 难度） | 入选理由 | 最短执行路线 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for node_id in candidates:
        value = stats[node_id]
        evidence_text = (
            f"{value['questionCount']} / {value['linkedScore']} / "
            f"{value['crossChapterQuestionCount']} / {float(value['averageDifficulty']):.1f}"
        )
        blocks.append(
            f"| `{node_id}` | {_cell(titles[node_id])} | {evidence_text} | "
            f"{_selection_reasons(value)} | {_cell(actions[node_id])} |"
        )
    for addition in additions:
        node_id = addition["nodeId"]
        blocks.append(
            f"| `{node_id}` | {_cell(titles[node_id])} | 前置追加 | "
            f"{_cell(addition['reason'])} | {_cell(actions[node_id])} |"
        )

    blocks.extend(
        [
            "",
            "## 3. 64 张核心公式",
            "",
            "先读触发与条件，再看公式；标为 `[慎]` 的条目必须同时核对最后一列。",
            "",
            "| 编号 | 公式 / 结论 | 触发与条件 | 记忆 | 失效边界 / 检查 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for formula_id in selection["selectedFormulaIds"]:
        blocks.append("| " + " | ".join(formula_rows[formula_id]) + " |")

    blocks.extend(["", "## 4. 21 组定理条件检查表", ""])
    for theorem_id in selection["theoremSectionIds"]:
        title, body = theorem_sections[theorem_id]
        blocks.extend([f"### {theorem_id} {title}", "", body, ""])

    blocks.extend(
        [
            "## 5. 反例速翻页",
            "",
            "卡住时先看错误命题，再用最小反例阻止自己继续沿错误路线计算。",
            "",
            "| 边界 ID | 错误命题 | 正确版本 | 最小反例 / 失效原因 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for counter_id in selection["counterexampleIds"]:
        blocks.append("| " + " | ".join(counter_rows[counter_id]) + " |")
    blocks.extend(
        [
            "",
            "## 6. 使用节奏",
            "",
            "1. 先用第 2 节判断题目属于哪条执行路线，30 秒仍无法选路时回到对应主题正文。",
            "2. 写公式前用第 4 节逐项核对定理条件，尤其留意区间、光滑性、独立性、方向与参数边界。",
            "3. 得到结论后用第 5 节主动找一个最小反例；若反例能击穿自己的表述，就补回缺失条件。",
            "4. 错题记录仍写入本地私有层，公开仓库只保留通用节点、规则和去题面化证据。",
            "",
            "## 7. 生成与证据边界",
            "",
            "- 选择清单：[`selection.json`](../data/sprint-guide/v1/selection.json)。",
            "- 真题证据：[`official-questions.json`](../data/exam-evidence/v1/official-questions.json)，仅含版权安全的事实元数据与衍生标签。",
            "- 公式、定理和反例分别来自本仓库的 [公式卡](10-formula-cards.md)、[定理索引](07-theorem-index.md) 与 [反例库](12-counterexamples.md)。",
            "- 运行 `python scripts/build_sprint_manual.py --check` 可验证选择规则、ID 唯一性和生成文件是否漂移。",
            "",
        ]
    )
    return "\n".join(blocks)


def validate_sprint_manual(root: Path) -> dict[str, object]:
    root = root.resolve()
    stats = validate_sprint_selection(root)
    output = root / OUTPUT_PATH
    expected = render_sprint_manual(root)
    if not output.exists() or output.read_text(encoding="utf-8") != expected:
        fail(f"generated sprint manual is missing or stale: {OUTPUT_PATH}")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the deterministic v1.5 sprint manual.")
    parser.add_argument("--check", action="store_true", help="fail if the generated manual is missing or stale")
    args = parser.parse_args()
    expected = render_sprint_manual(ROOT)
    output = ROOT / OUTPUT_PATH
    if args.check:
        validate_sprint_manual(ROOT)
        print("Sprint manual is current (56 nodes, 64 formulas, 21 theorem sections, 40 counterexamples).")
        return 0
    output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
