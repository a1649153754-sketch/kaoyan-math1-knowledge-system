from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_project import ProjectValidationError, validate_project  # noqa: E402


class ProjectContractTests(unittest.TestCase):
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

    def replace(self, relative: str, old: str, new: str) -> None:
        path = self.repo / relative
        content = path.read_text(encoding="utf-8")
        self.assertIn(old, content)
        path.write_text(content.replace(old, new, 1), encoding="utf-8", newline="\n")

    def assert_invalid(self, expected: str) -> None:
        with self.assertRaises(ProjectValidationError) as context:
            validate_project(self.repo)
        self.assertIn(expected, str(context.exception))

    def test_repository_baseline_passes(self) -> None:
        stats = validate_project(self.repo)
        self.assertEqual(stats["knowledgeNodes"], 253)
        self.assertEqual(stats["checklistItems"], 321)
        self.assertEqual(stats["resources"], 332)
        self.assertEqual(stats["unresolvedResourceMentions"], 0)

    def test_dangling_resource_topic_is_rejected(self) -> None:
        self.replace("docs/13-personal-links.md", "H7.5 / P3.9", "H7.5 / P3.99")
        self.assert_invalid("unknown formal topic P3.99")

    def test_reverse_topic_range_is_rejected(self) -> None:
        self.replace("docs/11-problem-archetypes.md", "P6.3-P6.8", "P6.8-P6.3")
        self.assert_invalid("invalid topic range P6.8-P6.3")

    def test_released_identity_removal_is_rejected(self) -> None:
        path = self.repo / "docs/04-method-library.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines = [line for line in lines if not line.startswith("- M7.4 ")]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        self.assert_invalid("released knowledgeNodes were removed or renamed")

    def test_duplicate_resource_id_is_rejected(self) -> None:
        path = self.repo / "docs/11-problem-archetypes.md"
        content = path.read_text(encoding="utf-8")
        duplicate = next(line for line in content.splitlines() if line.startswith("| Q-P01 |"))
        path.write_text(content + "\n" + duplicate + "\n", encoding="utf-8", newline="\n")
        self.assert_invalid("duplicate resource ID Q-P01")

    def test_empty_resource_field_is_rejected(self) -> None:
        self.replace(
            "docs/11-problem-archetypes.md",
            "| Q-P01 | 条件概率、至少/至多、分阶段 |",
            "| Q-P01 |  |",
        )
        self.assert_invalid("Q-P01 has empty required cells")

    def test_broken_local_link_is_rejected(self) -> None:
        path = self.repo / "README.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n[broken](docs/does-not-exist.md)\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assert_invalid("broken local link")

    def test_incompatible_csv_header_is_rejected(self) -> None:
        self.replace("data/progress.csv", "node_id,title,priority", "title,node_id,priority")
        self.assert_invalid("CSV header is not append-only compatible")

    def test_private_identity_column_is_rejected(self) -> None:
        path = self.repo / "data/progress.csv"
        rows = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(f"{row},email" for row in rows) + "\n", encoding="utf-8", newline="\n")
        self.assert_invalid("public CSV template contains private identity columns")


if __name__ == "__main__":
    unittest.main()
