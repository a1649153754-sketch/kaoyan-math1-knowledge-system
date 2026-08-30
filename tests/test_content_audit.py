from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from content_audit import ContentAuditError, validate_content_audits  # noqa: E402


class ContentAuditContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        shutil.copytree(
            ROOT,
            self.repo,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "site", "dist"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def mutate(self, relative: str, pattern: str, replacement: str, *, regex: bool = False) -> None:
        path = self.repo / relative
        text = path.read_text(encoding="utf-8")
        if regex:
            updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
            self.assertEqual(count, 1, pattern)
        else:
            self.assertIn(pattern, text)
            updated = text.replace(pattern, replacement, 1)
        path.write_text(updated, encoding="utf-8", newline="\n")

    def assert_invalid(self, expected: str) -> None:
        with self.assertRaises(ContentAuditError) as context:
            validate_content_audits(self.repo)
        self.assertIn(expected, str(context.exception))

    def test_all_chapters_cards_evidence_and_explanations_pass(self) -> None:
        stats = validate_content_audits(self.repo)
        self.assertEqual(len(stats["auditedChapters"]), 35)
        self.assertEqual(stats["auditedNodes"], 253)
        self.assertEqual(stats["detailedExplanations"], 87)
        self.assertEqual(stats["gentleExplanations"], 253)
        self.assertEqual(stats["nodeSelfChecks"], 253)
        self.assertEqual(stats["zeroEvidenceNodes"], 71)

    def test_missing_whole_chapter_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", r"^## H0\b.*?(?=^## H1\b)", "", regex=True)
        self.assert_invalid("formal node coverage differs from released baseline")

    def test_missing_node_card_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", r"^#### H0\.1\b.*?(?=^#### H0\.2\b)", "", regex=True)
        self.assert_invalid("execution card coverage mismatch for H0")

    def test_missing_execution_field_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "- **适用条件**：", "- **条件检查**：")
        self.assert_invalid("execution card fields missing for H0.1")

    def test_card_title_must_match_formal_node(self) -> None:
        self.mutate("docs/01-calculus.md", r"^#### H0\.1 [^\n]+$", "#### H0.1 错误标题", regex=True)
        self.assert_invalid("execution card title mismatch for H0.1")

    def test_stale_question_count_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "公开真题 7 题，挂接分值 37 分", "公开真题 6 题，挂接分值 37 分")
        self.assert_invalid("stale public question count for H0.2")

    def test_stale_linked_score_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "公开真题 7 题，挂接分值 37 分", "公开真题 7 题，挂接分值 36 分")
        self.assert_invalid("stale linked score for H0.2")

    def test_stale_average_difficulty_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "平均难度 37.0", "平均难度 38.0")
        self.assert_invalid("stale average difficulty for H0.2")

    def test_zero_evidence_node_cannot_invent_mother_link(self) -> None:
        self.mutate(
            "docs/01-calculus.md",
            "平均难度 暂无；当前无公开逐题证据",
            "平均难度 暂无；主挂接以 `Q-H01` 为代表；当前无公开逐题证据",
        )
        self.assert_invalid("zero-evidence node has invented mother link: H0.1")

    def test_unknown_source_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "来源**：S-H0-1；证据口径见 E-H0-1", "来源**：S-H0-99；证据口径见 E-H0-1")
        self.assert_invalid("unknown or missing source IDs for H0.1")

    def test_explanation_cannot_be_too_short(self) -> None:
        short = "### 核心讲解1：定义域是所有变形的地基\n\n**为什么成立**：短。\n\n**怎么用**：短。\n\n**小例题 / 路线演示**：短。\n\n**哪里会失效**：短。\n\n"
        self.mutate(
            "docs/01-calculus.md",
            r"^### 核心讲解1：定义域是所有变形的地基\b.*?(?=^### 核心讲解2：)",
            short,
            regex=True,
        )
        self.assert_invalid("detailed explanation is too short in H0")

    def test_explanation_requires_all_reasoning_segments(self) -> None:
        self.mutate("docs/01-calculus.md", "**为什么成立**：", "**原理说明**：")
        self.assert_invalid("detailed explanation lacks '为什么成立' in H0")

    def test_missing_gentle_explanation_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "- **温柔讲解**：", "- **节点寄语**：")
        self.assert_invalid("execution card fields missing for H0.1")

    def test_missing_node_self_check_is_rejected(self) -> None:
        self.mutate("docs/01-calculus.md", "- **自测追问**：", "- **复习提示**：")
        self.assert_invalid("execution card fields missing for H0.1")

    def test_node_self_check_must_match_its_title(self) -> None:
        self.mutate(
            "docs/01-calculus.md",
            "围绕“基本初等函数：幂、指数、对数、三角、反三角函数的定义域、值域、图像与单调性”说一遍",
            "围绕“完全无关的主题”说一遍",
        )
        self.assert_invalid("node self-check is not tied to its title: H0.1")

    def test_node_self_check_requires_a_boundary_prompt(self) -> None:
        self.mutate(
            "docs/01-calculus.md",
            r"^- \*\*自测追问\*\*：[^\n]+$",
            "- **自测追问**：围绕“基本初等函数”说明对象、条件和计算步骤："
            "再把每一个代数变形的来由完整说清楚，并用定义检查最后的表达式是否满足题目要求；"
            "还要另选两个不同的函数逐一核对定义域、值域、单调区间和图像变化是否一致。",
            regex=True,
        )
        self.assert_invalid("node self-check lacks a boundary prompt: H0.1")

    def test_gentle_explanation_cannot_be_too_short(self) -> None:
        self.mutate(
            "docs/01-calculus.md",
            r"^- \*\*温柔讲解\*\*：[^\n]+$",
            "- **温柔讲解**：`H0.1` 别急，我们慢慢来。",
            regex=True,
        )
        self.assert_invalid("gentle explanation is too short for H0.1")

    def test_gentle_explanations_cannot_be_duplicated(self) -> None:
        path = self.repo / "docs/01-calculus.md"
        text = path.read_text(encoding="utf-8")
        matches = list(re.finditer(r"^- \*\*温柔讲解\*\*：([^\n]+)$", text, re.MULTILINE))
        self.assertGreaterEqual(len(matches), 2)
        repeated = (
            "`H0.1` 与 `H0.2` 先别急，我们把对象、条件、第一动作和停止边界慢慢拆开。"
            "先写定义域，再检查每一步是否双向成立；遇到分支、零点或不可逆变形时就稳稳停下来补条件。"
            "完成后用定义、反算和最小反例各检查一次，这样不是在拖慢速度，而是在让后面的推理更可靠。"
            "等你能亲口解释为什么这样起步、又为什么在这里停止，这两个节点就不再只是背诵，而会成为可以反复调用的判断力。"
            "哪怕今天只把第一步做对也很好，明天再回来补第二步；每一次清楚的小检查，都会让整条知识链更稳一些。"
        )
        duplicate = f"- **温柔讲解**：{repeated}"
        for match in reversed(matches[:2]):
            text = text[: match.start()] + duplicate + text[match.end() :]
        path.write_text(text, encoding="utf-8", newline="\n")
        self.assert_invalid("duplicate gentle explanation for H0.2 and H0.1")


if __name__ == "__main__":
    unittest.main()
