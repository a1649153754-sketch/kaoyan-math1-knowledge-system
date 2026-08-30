from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_sprint_manual import (  # noqa: E402
    SprintManualError,
    validate_sprint_manual,
    validate_sprint_selection,
)


class SprintManualContractTests(unittest.TestCase):
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

    def selection(self) -> tuple[Path, dict[str, object]]:
        path = self.repo / "data/sprint-guide/v1/selection.json"
        return path, json.loads(path.read_text(encoding="utf-8"))

    def save(self, path: Path, value: dict[str, object]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def assert_invalid(self, expected: str, *, generated: bool = False) -> None:
        function = validate_sprint_manual if generated else validate_sprint_selection
        with self.assertRaises(SprintManualError) as context:
            function(self.repo)
        self.assertIn(expected, str(context.exception))

    def test_selection_and_generated_manual_pass(self) -> None:
        stats = validate_sprint_manual(self.repo)
        self.assertEqual(
            stats,
            {
                "objectiveCandidates": 56,
                "prerequisiteAdditions": 0,
                "selectedFormulas": 64,
                "theoremSections": 21,
                "counterexamples": 40,
            },
        )

    def test_candidate_rule_drift_is_rejected(self) -> None:
        path, value = self.selection()
        value["candidateRules"]["minimumQuestionCount"] = 9
        self.save(path, value)
        self.assert_invalid("candidate selection rules drifted")

    def test_missing_objective_candidate_is_rejected(self) -> None:
        path, value = self.selection()
        value["objectiveCandidateNodeIds"].pop()
        self.save(path, value)
        self.assert_invalid("candidate list does not match evidence rules")

    def test_duplicate_formula_id_is_rejected(self) -> None:
        path, value = self.selection()
        value["selectedFormulaIds"][1] = value["selectedFormulaIds"][0]
        self.save(path, value)
        self.assert_invalid("duplicate IDs: selectedFormulaIds")

    def test_unknown_formula_id_is_rejected(self) -> None:
        path, value = self.selection()
        value["selectedFormulaIds"][0] = "F-H2-99"
        self.save(path, value)
        self.assert_invalid("unknown IDs or exceeds 64 cards")

    def test_prerequisite_addition_requires_reason(self) -> None:
        path, value = self.selection()
        value["prerequisiteAdditions"] = [{"nodeId": "H0.1", "reason": ""}]
        self.save(path, value)
        self.assert_invalid("invalid prerequisite addition")

    def test_generated_manual_drift_is_rejected(self) -> None:
        path = self.repo / "docs/17-sprint-manual.md"
        path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8", newline="\n")
        self.assert_invalid("generated sprint manual is missing or stale", generated=True)


if __name__ == "__main__":
    unittest.main()
