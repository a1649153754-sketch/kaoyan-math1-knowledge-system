from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_local_reports import generate_reports  # noqa: E402
from init_local_data import initialize_local_data  # noqa: E402
from local_data import LocalDataError, load_contracts, validate_local_directory, write_csv  # noqa: E402
from migrate_local_data import migrate_directory  # noqa: E402
from validate_project import collect_catalog  # noqa: E402


class LocalDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.contracts = load_contracts(ROOT)
        self.catalog = collect_catalog(ROOT)
        self.mother_id = sorted(item for item in self.catalog.resources if item.startswith("Q-"))[0]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def topics(self):
        return self.catalog.topics

    @property
    def mothers(self):
        return (item for item in self.catalog.resources if item.startswith("Q-"))

    def write_legacy_fixture(self, directory: Path, *, extra_field: bool = False) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        rows = {
            "progress": {
                "node_id": "H1.5",
                "title": "极限计算方法",
                "priority": "A+",
                "level": "1",
                "last_review": "2026-08-26",
                "next_review": "2026-08-29",
                "status": "learning",
                "evidence": "限时训练",
                "notes": "",
            },
            "questions": {
                "date": "2026-08-28",
                "source": "official",
                "year": "2025",
                "question_no": "1",
                "mother_id": self.mother_id,
                "node_ids": "H1.5",
                "result": "wrong",
                "time_minutes": "12.5",
                "error_tags": "M",
                "next_review": "2026-08-31",
                "notes": "",
            },
            "errors": {
                "error_id": "E-0001",
                "date": "2026-08-28",
                "source": "official",
                "node_ids": "H1.5",
                "mother_id": self.mother_id,
                "error_tag": "M",
                "summary": "路线选择错误",
                "fix_action": "重做并口述",
                "next_review": "2026-09-04",
                "status": "open",
                "notes": "",
            },
        }
        for name, contract in self.contracts.items():
            header = contract.legacy_headers[0] + (("study_session",) if extra_field else ())
            row = dict(rows[name])
            if extra_field:
                row["study_session"] = "evening"
            write_csv(directory / f"{name}.csv", header, [row])

    def validate(self, directory: Path):
        return validate_local_directory(
            ROOT,
            directory,
            topic_ids=self.topics,
            mother_ids=self.mothers,
        )

    def test_initializer_creates_header_only_files_without_overwrite(self) -> None:
        target = self.base / "local"
        first = initialize_local_data(ROOT, target)
        self.assertEqual(len(first), 3)
        progress = target / "progress.csv"
        progress.write_text(progress.read_text(encoding="utf-8") + "# sentinel\n", encoding="utf-8")
        second = initialize_local_data(ROOT, target)
        self.assertEqual(second, [])
        self.assertIn("# sentinel", progress.read_text(encoding="utf-8"))

    def test_legacy_migration_appends_fields_and_preserves_extensions(self) -> None:
        source = self.base / "legacy"
        output = self.base / "migrated"
        self.write_legacy_fixture(source, extra_field=True)
        written = migrate_directory(
            ROOT,
            source,
            output,
            topic_ids=self.topics,
            mother_ids=self.mothers,
        )
        self.assertEqual(len(written), 3)
        datasets = self.validate(output)
        self.assertEqual(datasets["progress"].detected_version, "1.0.0")
        self.assertEqual(datasets["progress"].rows[0]["schema_version"], "1.0.0")
        self.assertEqual(datasets["progress"].rows[0]["review_interval_days"], "3")
        self.assertEqual(datasets["progress"].rows[0]["study_session"], "evening")

    def test_invalid_node_reference_is_rejected(self) -> None:
        source = self.base / "legacy"
        self.write_legacy_fixture(source)
        path = source / "progress.csv"
        content = path.read_text(encoding="utf-8").replace("H1.5", "H99.99")
        path.write_text(content, encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(LocalDataError, "unknown formal node IDs"):
            self.validate(source)

    def test_invalid_date_and_enum_are_rejected(self) -> None:
        source = self.base / "legacy"
        self.write_legacy_fixture(source)
        questions = source / "questions.csv"
        content = questions.read_text(encoding="utf-8").replace("2026-08-28", "2026-02-30")
        questions.write_text(content, encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(LocalDataError, "invalid ISO date"):
            self.validate(source)

    def test_private_identity_extension_is_rejected(self) -> None:
        target = self.base / "local"
        initialize_local_data(ROOT, target)
        contract = self.contracts["progress"]
        row = {field: "" for field in contract.header + ("email",)}
        row.update({"node_id": "H1.5", "email": "private@example.com"})
        write_csv(target / "progress.csv", contract.header + ("email",), [row])
        with self.assertRaisesRegex(LocalDataError, "private identity columns"):
            self.validate(target)

    def test_reports_are_deterministic_and_cover_weak_retest_weekly_views(self) -> None:
        source = self.base / "legacy"
        local = self.base / "local"
        reports = self.base / "reports"
        self.write_legacy_fixture(source)
        migrate_directory(
            ROOT,
            source,
            local,
            topic_ids=self.topics,
            mother_ids=self.mothers,
        )
        outputs = generate_reports(ROOT, local, reports, as_of=date(2026, 8, 29))
        first = {name: path.read_text(encoding="utf-8") for name, path in outputs.items()}
        outputs = generate_reports(ROOT, local, reports, as_of=date(2026, 8, 29))
        second = {name: path.read_text(encoding="utf-8") for name, path in outputs.items()}
        self.assertEqual(first, second)
        self.assertIn("H1.5", first["weak"])
        self.assertIn("3 天窗口", first["retests"])
        self.assertIn("错误 1", first["weekly"])


if __name__ == "__main__":
    unittest.main()
