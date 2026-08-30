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


if __name__ == "__main__":
    unittest.main()
