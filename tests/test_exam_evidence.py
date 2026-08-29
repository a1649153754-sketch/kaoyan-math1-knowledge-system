from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from exam_evidence import (  # noqa: E402
    INDEX_FILE,
    MANIFEST_FILE,
    MOCK_FILE,
    OFFICIAL_FILE,
    ExamEvidenceError,
    validate_exam_evidence,
)
from validate_project import collect_catalog  # noqa: E402


class ExamEvidenceContractTests(unittest.TestCase):
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

    def load(self, relative: Path) -> dict[str, object]:
        return json.loads((self.repo / relative).read_text(encoding="utf-8"))

    def write(self, relative: Path, value: object) -> None:
        (self.repo / relative).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def assert_invalid(self, expected: str) -> None:
        with self.assertRaises(ExamEvidenceError) as context:
            validate_exam_evidence(self.repo, collect_catalog(self.repo))
        self.assertIn(expected, str(context.exception))

    def first_question(self) -> tuple[dict[str, object], dict[str, object]]:
        official = self.load(OFFICIAL_FILE)
        return official, official["papers"][0]["questions"][0]

    def test_repository_baseline_passes(self) -> None:
        stats = validate_exam_evidence(self.repo, collect_catalog(self.repo))
        self.assertEqual(stats["officialPapers"], 17)
        self.assertEqual(stats["officialQuestions"], 385)
        self.assertEqual(stats["officialMarks"], 2550)
        self.assertGreater(stats["mockQuestions"], 0)

    def test_prompt_field_is_rejected(self) -> None:
        official, question = self.first_question()
        question["prompt"] = "must not be published"
        self.write(OFFICIAL_FILE, official)
        self.assert_invalid("unsafe or incomplete official question fields")

    def test_unknown_node_is_rejected(self) -> None:
        official, question = self.first_question()
        question["nodeIds"] = ["H99.99"]
        question["coreNodeIds"] = ["H99.99"]
        question["supportNodeIds"] = []
        self.write(OFFICIAL_FILE, official)
        self.assert_invalid("unknown formal nodes")

    def test_unknown_mother_is_rejected(self) -> None:
        official, question = self.first_question()
        question["primaryMotherId"] = "Q-H99"
        self.write(OFFICIAL_FILE, official)
        self.assert_invalid("invalid primary mother")

    def test_2026_truthfulness_boundary_is_rejected(self) -> None:
        official = self.load(OFFICIAL_FILE)
        official["papers"][-1]["officialAnswerAvailable"] = True
        self.write(OFFICIAL_FILE, official)
        self.assert_invalid("2026 truthfulness boundary")

    def test_long_route_label_is_rejected(self) -> None:
        official, question = self.first_question()
        question["routeLabel"] = "x" * 49
        self.write(OFFICIAL_FILE, official)
        self.assert_invalid("route label is empty or too long")

    def test_stale_reverse_index_is_rejected(self) -> None:
        indexes = self.load(INDEX_FILE)
        indexes["byYear"].pop("2010")
        self.write(INDEX_FILE, indexes)
        self.assert_invalid("reverse indexes are stale")

    def test_mock_item_level_field_is_rejected(self) -> None:
        mock = self.load(MOCK_FILE)
        mock["difficulty"]["provider"] = "must not be published"
        self.write(MOCK_FILE, mock)
        self.assert_invalid("forbidden item-level field")

    def test_mock_small_cohort_is_rejected(self) -> None:
        mock = self.load(MOCK_FILE)
        row = copy.deepcopy(mock["topNodes"][0])
        row["questionCount"] = mock["suppressionThreshold"] - 1
        mock["topNodes"].append(row)
        self.write(MOCK_FILE, mock)
        self.assert_invalid("suppressed cohort")

    def test_manifest_hash_mismatch_is_rejected(self) -> None:
        manifest = self.load(MANIFEST_FILE)
        manifest["artifacts"]["officialQuestions"]["sha256"] = "0" * 64
        self.write(MANIFEST_FILE, manifest)
        self.assert_invalid("manifest hash mismatch")


if __name__ == "__main__":
    unittest.main()
