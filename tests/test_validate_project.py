from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from local_data import LocalDataError  # noqa: E402
from content_audit import ContentAuditError  # noqa: E402
from exam_evidence import ExamEvidenceError  # noqa: E402
from build_sprint_manual import SprintManualError  # noqa: E402
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
        with self.assertRaises((ContentAuditError, ExamEvidenceError, LocalDataError, ProjectValidationError, SprintManualError)) as context:
            validate_project(self.repo)
        self.assertIn(expected, str(context.exception))

    def test_repository_baseline_passes(self) -> None:
        stats = validate_project(self.repo)
        self.assertEqual(stats["knowledgeNodes"], 253)
        self.assertEqual(stats["checklistItems"], 321)
        self.assertEqual(stats["resources"], 332)
        self.assertEqual(stats["dataSchemaVersion"], "1.0.0")
        self.assertEqual(stats["examEvidence"]["officialQuestions"], 385)
        self.assertEqual(len(stats["contentAudit"]["auditedChapters"]), 35)
        self.assertEqual(stats["contentAudit"]["auditedNodes"], 253)
        self.assertEqual(stats["contentAudit"]["detailedExplanations"], 87)
        self.assertEqual(stats["contentAudit"]["zeroEvidenceNodes"], 71)
        self.assertEqual(stats["sprintManual"]["objectiveCandidates"], 56)
        self.assertEqual(stats["sprintManual"]["selectedFormulas"], 64)
        self.assertEqual(stats["sprintManual"]["theoremSections"], 21)
        self.assertEqual(stats["sprintManual"]["counterexamples"], 40)
        self.assertEqual(stats["mathRendering"], {"engine": "MathJax 3", "arithmatex": True})
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

    def test_disabled_arithmatex_is_rejected(self) -> None:
        self.replace(
            "zensical.toml",
            "pymdownx.arithmatex.generic = true",
            "pymdownx.arithmatex.generic = false",
        )
        self.assert_invalid("Zensical math rendering requires pymdownx.arithmatex.generic = true")

    def test_incompatible_csv_header_is_rejected(self) -> None:
        self.replace("data/progress.csv", "node_id,title,priority", "title,node_id,priority")
        self.assert_invalid("CSV header is not append-only compatible")

    def test_private_identity_column_is_rejected(self) -> None:
        path = self.repo / "data/progress.csv"
        rows = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(f"{row},email" for row in rows) + "\n", encoding="utf-8", newline="\n")
        self.assert_invalid("public CSV template contains private identity columns")

    def test_public_csv_data_row_is_rejected(self) -> None:
        path = self.repo / "data/progress.csv"
        header = path.read_text(encoding="utf-8").strip().split(",")
        path.write_text(
            ",".join(header) + "\n" + ",".join("" for _ in header) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assert_invalid("public CSV template must be header-only")

    def test_schema_cannot_break_legacy_prefix(self) -> None:
        self.replace(
            "data/schemas/v1/progress.schema.json",
            '"node_id", "title", "priority", "level"',
            '"title", "node_id", "priority", "level"',
        )
        self.assert_invalid("legacy header is not a prefix")

    def test_tracked_local_private_file_is_rejected(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)
        private_file = self.repo / "data/local/progress-private.csv"
        private_file.write_text("node_id,score\nH1.5,42\n", encoding="utf-8", newline="\n")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "-f", "data/local/progress-private.csv"],
            check=True,
        )
        self.assert_invalid("private local data is tracked by Git")

    def test_untracked_local_reports_do_not_affect_public_validation(self) -> None:
        report = self.repo / "data/local/reports/weekly-review.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("[private broken link](missing.md)\n/mnt/data/private\n", encoding="utf-8")
        stats = validate_project(self.repo)
        self.assertEqual(stats["dataSchemaVersion"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
