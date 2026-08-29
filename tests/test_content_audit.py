from __future__ import annotations

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

    def replace(self, old: str, new: str) -> None:
        path = self.repo / "docs/01-calculus.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    def assert_invalid(self, expected: str) -> None:
        with self.assertRaises(ContentAuditError) as context:
            validate_content_audits(self.repo)
        self.assertIn(expected, str(context.exception))

    def test_h2_execution_cards_pass(self) -> None:
        stats = validate_content_audits(self.repo)
        self.assertEqual(stats["auditedChapters"], ["H2"])
        self.assertEqual(stats["auditedNodes"], 10)

    def test_missing_execution_field_is_rejected(self) -> None:
        self.replace("- **适用条件**：点导数要求", "- **条件检查**：点导数要求")
        self.assert_invalid("execution card fields missing for H2.1")

    def test_stale_question_count_is_rejected(self) -> None:
        self.replace("公开真题 13 题", "公开真题 12 题")
        self.assert_invalid("stale public question count for H2.1")

    def test_unknown_source_is_rejected(self) -> None:
        self.replace("来源**：S-H2-1；证据口径见 E-H2-1", "来源**：S-H2-99；证据口径见 E-H2-1")
        self.assert_invalid("unknown or missing source IDs for H2.1")


if __name__ == "__main__":
    unittest.main()
