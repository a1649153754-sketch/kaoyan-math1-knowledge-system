#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from local_data import ROOT, DatasetRows, LocalDataError, validate_local_directory
from validate_project import TOPIC_FILES, TOPIC_RE, collect_catalog, natural_key, read_text


def _date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _nodes(record: dict[str, str], dataset: str) -> list[str]:
    value = record.get("node_id", "") if dataset == "progress" else record.get("node_ids", "")
    return [item.strip() for item in value.split(";") if item.strip()]


def _due_date(record: dict[str, str], dataset: str) -> date | None:
    explicit = _date(record.get("next_review", ""))
    if explicit:
        return explicit
    interval = record.get("review_interval_days", "")
    if interval not in {"3", "7", "14"}:
        return None
    base_field = "last_review" if dataset == "progress" else "date"
    base = _date(record.get(base_field, ""))
    return base + timedelta(days=int(interval)) if base else None


def _topic_titles(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in TOPIC_FILES:
        for line in read_text(root, relative).splitlines():
            match = TOPIC_RE.match(line)
            if match:
                result[match.group(1)] = match.group(2).strip()
    return result


def _markdown(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def calculate_weakness(
    datasets: dict[str, DatasetRows],
    titles: dict[str, str],
) -> list[tuple[str, str, float, list[str]]]:
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, Counter[str]] = defaultdict(Counter)
    progress_titles: dict[str, str] = {}
    priority_weight = {"A+": 1.4, "A": 1.2, "B": 1.0, "C": 0.8, "": 1.0}
    result_weight = {"wrong": 12.0, "partial": 6.0, "skipped": 8.0, "correct": 0.0}
    severity_weight = {"": 8.0, "low": 5.0, "medium": 8.0, "high": 12.0, "critical": 16.0}

    for record in datasets["progress"].rows:
        node_id = record["node_id"]
        if record.get("title"):
            progress_titles[node_id] = record["title"]
        level = int(record.get("level") or 0)
        weight = priority_weight.get(record.get("priority", ""), 1.0)
        score = max(0, 4 - level) * 5.0 * weight
        if record.get("status") == "paused":
            score *= 0.5
        scores[node_id] += score
        if score:
            reasons[node_id][f"掌握 {level} 级"] += 1

    for record in datasets["questions"].rows:
        result = record.get("result", "")
        base = result_weight.get(result, 0.0)
        difficulty = int(record.get("difficulty") or 0)
        score = base * (1.0 + difficulty / 200.0)
        for node_id in _nodes(record, "questions"):
            scores[node_id] += score
            if score:
                reasons[node_id][f"{result} 题"] += 1

    for record in datasets["errors"].rows:
        if record.get("status") == "resolved":
            continue
        score = severity_weight.get(record.get("severity", ""), 8.0)
        for node_id in _nodes(record, "errors"):
            scores[node_id] += score
            reasons[node_id][f"未关闭错因 {record.get('error_tag', '')}"] += 1

    ranked: list[tuple[str, str, float, list[str]]] = []
    for node_id, score in scores.items():
        if score <= 0:
            continue
        reason_text = [f"{name}×{count}" for name, count in reasons[node_id].most_common()]
        ranked.append((node_id, progress_titles.get(node_id) or titles.get(node_id, ""), round(score, 1), reason_text))
    ranked.sort(key=lambda item: (-item[2], natural_key(item[0])))
    return ranked


def _record_label(record: dict[str, str], dataset: str) -> str:
    if dataset == "progress":
        return record.get("title") or record.get("node_id", "")
    if dataset == "questions":
        parts = [record.get("source", ""), record.get("year", ""), record.get("question_no", "")]
        return " ".join(item for item in parts if item)
    return " ".join(item for item in (record.get("error_id", ""), record.get("summary", "")) if item)


def collect_retests(datasets: dict[str, DatasetRows], as_of: date) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for dataset, values in datasets.items():
        for record in values.rows:
            due = _due_date(record, dataset)
            if due is None:
                continue
            delta = (due - as_of).days
            if delta > 14:
                continue
            items.append(
                {
                    "dataset": dataset,
                    "label": _record_label(record, dataset),
                    "nodes": ";".join(_nodes(record, dataset)),
                    "due": due,
                    "delta": delta,
                }
            )
    items.sort(key=lambda item: (item["due"], item["dataset"], item["label"]))
    return items


def _render_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["暂无记录。"]
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(_markdown(cell) for cell in row) + " |" for row in rows)
    return output


def render_weak_nodes(as_of: date, ranked: list[tuple[str, str, float, list[str]]]) -> str:
    rows = [[node_id, title, f"{score:.1f}", "；".join(reasons)] for node_id, title, score, reasons in ranked[:20]]
    lines = [
        "# 本地薄弱节点报告",
        "",
        f"> 生成基准日：{as_of.isoformat()}。本文件来自 `data/local/`，请勿提交到公开仓库。",
        "",
        "分数综合考虑掌握等级、优先级、错/半错题、难度及未关闭错因，只用于安排复习顺序。",
        "",
        *_render_table(["节点", "名称", "薄弱分", "证据"], rows),
        "",
    ]
    return "\n".join(lines)


def render_retests(as_of: date, items: list[dict[str, object]]) -> str:
    lines = [
        "# 3/7/14 天复测安排",
        "",
        f"> 生成基准日：{as_of.isoformat()}。逾期项目计入 3 天窗口。",
        "",
    ]
    windows = (("3 天窗口（含逾期）", -10**9, 3), ("7 天窗口", 4, 7), ("14 天窗口", 8, 14))
    for title, lower, upper in windows:
        rows = []
        for item in items:
            delta = int(item["delta"])
            if lower <= delta <= upper:
                state = f"逾期 {-delta} 天" if delta < 0 else ("今天" if delta == 0 else f"{delta} 天后")
                rows.append([item["due"], item["dataset"], item["label"], item["nodes"], state])
        lines.extend([f"## {title}", "", *_render_table(["日期", "类型", "记录", "节点", "距离"], rows), ""])
    return "\n".join(lines)


def render_weekly(
    as_of: date,
    datasets: dict[str, DatasetRows],
    ranked: list[tuple[str, str, float, list[str]]],
    retests: list[dict[str, object]],
) -> str:
    start = as_of - timedelta(days=6)
    questions = [row for row in datasets["questions"].rows if (day := _date(row.get("date", ""))) and start <= day <= as_of]
    errors = [row for row in datasets["errors"].rows if (day := _date(row.get("date", ""))) and start <= day <= as_of]
    results = Counter(row.get("result", "") for row in questions)
    tags = Counter(tag for row in errors for tag in row.get("error_tag", "").split(";") if tag)
    total_minutes = sum(float(row.get("time_minutes") or 0) for row in questions)
    open_errors = sum(row.get("status") != "resolved" for row in datasets["errors"].rows)
    next_week = [item for item in retests if int(item["delta"]) <= 7]
    focus = "、".join(item[0] for item in ranked[:5]) or "暂无"
    top_tags = "、".join(f"{tag}×{count}" for tag, count in tags.most_common()) or "暂无"

    lines = [
        "# 本地周复盘",
        "",
        f"> 统计区间：{start.isoformat()}—{as_of.isoformat()}。本文件不得进入 Git、Pages 或 Release。",
        "",
        "## 本周数据",
        "",
        f"- 题目记录：{len(questions)}；正确 {results['correct']}、半对 {results['partial']}、错误 {results['wrong']}、跳过 {results['skipped']}。",
        f"- 记录用时：{total_minutes:.1f} 分钟。",
        f"- 新增错因：{len(errors)}；当前全部未关闭错因：{open_errors}。",
        f"- 本周错因标签：{top_tags}。",
        "",
        "## 下周最小动作",
        "",
        f"- 优先节点：{focus}。",
        f"- 未来 7 天（含逾期）复测记录：{len(next_week)} 项。",
        "- 每个薄弱节点只安排一个可验证动作；完成后更新证据、等级和下一次复测日期。",
        "",
    ]
    return "\n".join(lines)


def generate_reports(root: Path, data_dir: Path, output_dir: Path, *, as_of: date) -> dict[str, Path]:
    catalog = collect_catalog(root)
    datasets = validate_local_directory(
        root,
        data_dir,
        topic_ids=catalog.topics,
        mother_ids=(item for item in catalog.resources if item.startswith("Q-")),
    )
    titles = _topic_titles(root)
    ranked = calculate_weakness(datasets, titles)
    retests = collect_retests(datasets, as_of)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "weak": output_dir / "weak-nodes.md",
        "retests": output_dir / "retest-3-7-14.md",
        "weekly": output_dir / "weekly-review.md",
    }
    outputs["weak"].write_text(render_weak_nodes(as_of, ranked), encoding="utf-8", newline="\n")
    outputs["retests"].write_text(render_retests(as_of, retests), encoding="utf-8", newline="\n")
    outputs["weekly"].write_text(render_weekly(as_of, datasets, ranked, retests), encoding="utf-8", newline="\n")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ignored weak-node, retest and weekly reports.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "local")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    output_dir = args.output_dir or args.data_dir / "reports"
    try:
        outputs = generate_reports(ROOT, args.data_dir.resolve(), output_dir.resolve(), as_of=args.as_of)
    except (OSError, LocalDataError) as error:
        print(f"ERROR: {error}")
        return 1
    for path in outputs.values():
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
