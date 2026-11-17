"""CPU tests for independent study tasks, commitments, and executable gold."""
import tempfile
import unittest
from pathlib import Path

from fac_tinyagent.config import PROJECT_ROOT
from fac_tinyagent.research_data import (FAMILIES, SPLITS, generate_study,
                                        task_signature, verify_study)
from fac_tinyagent.utils import read_jsonl


class ResearchDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = PROJECT_ROOT / "data_phase2"
        cls.output = cls.root / "study"
        cls.manifest = generate_study(cls.source, cls.output, 20261109)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unique_isolated_coverage_and_executable_gold(self):
        expected_tools = {
            "file": {"file_read", "file_search", "file_list", "file_write"},
            "database": {"db_query", "db_schema", "db_list_tables"},
            "python": {"stats_mean", "stats_median", "stats_std", "stats_percentile",
                       "stats_correlation", "stats_linear_regression"},
            "calendar": {"calendar_list", "calendar_search", "calendar_count",
                         "calendar_attendees", "calendar_free_slots"},
        }
        all_signatures = set()
        for family in FAMILIES:
            old = {task_signature(row) for split in ("train", "val", "test")
                   for row in read_jsonl(self.source / family / (split + ".jsonl"))}
            for split, n in (("probe", 24), ("sealed_test", 60)):
                rows = read_jsonl(self.output / family / (split + ".jsonl"))
                signatures = {task_signature(row) for row in rows}
                self.assertEqual(len(rows), n)
                self.assertEqual(len(signatures), n)
                self.assertFalse(signatures & old)
                self.assertFalse(signatures & all_signatures)
                self.assertEqual({row["expected_tool"] for row in rows}, expected_tools[family])
                self.assertTrue(all(row["evaluation_only"] for row in rows))
                self.assertTrue(all(row["selection_allowed"] == (split == "probe") for row in rows))
                self.assertNotIn("\\", self.manifest["families"][family][split]["path"])
                all_signatures.update(signatures)
        self.assertEqual(verify_study(self.output)["total_verified"], 336)
        self.assertTrue(all(not Path(record["path"]).is_absolute()
                            for record in self.manifest["legacy_files"]))

    def test_reproducible_tasks_and_refuse_overwrite(self):
        second = self.root / "reproduced"
        generated = generate_study(self.source, second, 20261109)
        for family in FAMILIES:
            for split in SPLITS:
                self.assertEqual(generated["families"][family][split]["sha256"],
                                 self.manifest["families"][family][split]["sha256"])
        with self.assertRaises(FileExistsError):
            generate_study(self.source, self.output, 20261109)

    def test_sealed_hash_detects_edit(self):
        path = self.output / "calendar" / "sealed_test.jsonl"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "Data hash mismatch"):
                verify_study(self.output)
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
