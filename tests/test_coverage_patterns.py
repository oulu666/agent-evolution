"""CPU-only tests for operation-pattern classification and the three metrics."""
from __future__ import annotations

import unittest

from fac_tinyagent.coverage_patterns import (
    OFFICIAL_PATTERNS,
    classify_item,
    classify_sql_query,
    experience_diversity,
    experience_identity,
    forgetting_and_recovery,
    pattern_coverage,
    skill_from_results,
    sql_features,
)


class SqlFeatureTests(unittest.TestCase):
    def test_filter_cmp_top(self):
        sql = "SELECT name FROM products WHERE price > 49.0 ORDER BY price DESC, id ASC LIMIT 3"
        self.assertEqual(classify_sql_query(sql), "db.filter_cmp_top")

    def test_filter_eq_top(self):
        sql = "SELECT name FROM employees WHERE department = 'Finance' ORDER BY salary DESC LIMIT 2"
        self.assertEqual(classify_sql_query(sql), "db.filter_eq_top")

    def test_top_n_no_where(self):
        sql = "SELECT product FROM sales ORDER BY amount DESC LIMIT 3"
        self.assertEqual(classify_sql_query(sql), "db.top_n")

    def test_filter_cmp_count(self):
        sql = "SELECT COUNT(*) AS n FROM employees WHERE age > 28"
        self.assertEqual(classify_sql_query(sql), "db.filter_cmp_count")

    def test_filter_eq_count(self):
        sql = "SELECT COUNT(*) AS n FROM sales WHERE product = 'Widget'"
        self.assertEqual(classify_sql_query(sql), "db.filter_eq_count")

    def test_multi_filter_count(self):
        sql = "SELECT COUNT(*) AS n FROM products WHERE category = 'Software' AND stock > 25"
        self.assertEqual(classify_sql_query(sql), "db.multi_filter_count")

    def test_group_count_filter(self):
        sql = "SELECT region, COUNT(*) AS n FROM sales WHERE amount > 420 GROUP BY region ORDER BY region"
        self.assertEqual(classify_sql_query(sql), "db.filter_cmp_group_count")
        # cmp must not be read from ORDER BY
        f = sql_features(sql)
        self.assertTrue(f["cmp"])
        self.assertTrue(f["group"])

    def test_min_max(self):
        self.assertEqual(classify_sql_query("SELECT MAX(salary) AS v FROM employees"), "db.min_max")
        self.assertEqual(
            classify_sql_query("SELECT MIN(stock) AS v FROM products WHERE stock > 200"),
            "db.min_max",
        )


class TemplateClassificationTests(unittest.TestCase):
    def test_template_id_wins(self):
        row = {
            "template_id": "target_db_filter_top",
            "tool_family": "database",
            "expected_tool": "db_query",
            "expected_arguments": {
                "sql": "SELECT name FROM products WHERE price > 19.99 ORDER BY price DESC, id ASC LIMIT 4"
            },
            "episode_id": "database-train-target_db_filter_top-000",
        }
        c = classify_item(row)
        self.assertEqual(c.pattern, "db.filter_cmp_top")
        self.assertEqual(c.source, "template_id")
        self.assertTrue(c.official)

    def test_python_wording_aliases(self):
        for tid in ("stats_median", "stats_median_prose", "target_median_natural"):
            c = classify_item({"template_id": tid, "expected_tool": "stats_median", "tool_family": "python"})
            self.assertEqual(c.pattern, "py.median")

    def test_file_last_match_aliases(self):
        for tid in ("file_last_match", "target_file_last_match", "e4_target_file_last_match"):
            c = classify_item({"template_id": tid, "expected_tool": "file_search", "tool_family": "file"})
            self.assertEqual(c.pattern, "file.search_last")

    def test_unmapped_template_falls_back(self):
        row = {
            "template_id": "not_a_real_template",
            "tool_family": "database",
            "expected_tool": "db_query",
            "expected_arguments": {"sql": "SELECT COUNT(*) AS n FROM employees"},
            "episode_id": "x-1",
        }
        c = classify_item(row)
        self.assertEqual(c.pattern, "db.count_all")
        self.assertEqual(c.source, "structural")

    def test_calendar_list_without_cue_is_unknown(self):
        c = classify_item({
            "tool_family": "calendar",
            "expected_tool": "calendar_list",
            "expected_arguments": {"date": "2026-07-03"},
            "prompt": "Please look at 2026-07-03.",
        })
        self.assertEqual(c.pattern, "cal.unknown")
        self.assertEqual(c.source, "unknown")


class MetricsTests(unittest.TestCase):
    def test_coverage_and_diversity_are_not_the_same(self):
        # Six slots, one pattern, one unique id repeated: coverage of that
        # single-pattern catalog is 1, uniqueness is 1/6.
        rows = [
            {
                "template_id": "target_db_filter_top",
                "expected_tool": "db_query",
                "expected_arguments": {"sql": "SELECT name FROM products WHERE price > 1 ORDER BY price DESC LIMIT 1"},
                "episode_id": "same-target",
                "tool_family": "database",
            }
        ] * 6
        cov = pattern_coverage(rows, catalog=("db.filter_cmp_top", "db.top_n"))
        div = experience_diversity(rows)
        self.assertEqual(cov.n_official_covered, 1)
        self.assertAlmostEqual(cov.coverage, 0.5)
        self.assertEqual(div.n_unique, 1)
        self.assertAlmostEqual(div.uniqueness, 1 / 6)

    def test_identity_prefers_episode_id(self):
        a = {"episode_id": "abc", "prompt": "one"}
        b = {"episode_id": "abc", "prompt": "two"}
        self.assertEqual(experience_identity(a), experience_identity(b))

    def test_skill_deficit_and_forgetting_gate(self):
        results = [
            {"joint_success": True, "tool_correct": True},
            {"joint_success": False, "tool_correct": True},
            {"joint_success": False, "tool_correct": False},
        ]
        s = skill_from_results(results)
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["skill"], 1 / 3)
        self.assertAlmostEqual(s["deficit"], 2 / 3)
        self.assertAlmostEqual(s["tool_accuracy"], 2 / 3)
        self.assertAlmostEqual(s["conditional_success"], 0.5)
        gated = forgetting_and_recovery(None, 0.0, 1.0)
        self.assertFalse(gated["may_use_forgetting_term"])
        named = forgetting_and_recovery(0.8, 0.0, 1.0)
        self.assertTrue(named["may_use_forgetting_term"])
        self.assertAlmostEqual(named["drop_t0_t1"], 0.8)
        self.assertAlmostEqual(named["recovery_t1_t2"], 1.0)

    def test_official_catalog_is_closed(self):
        self.assertEqual(len(OFFICIAL_PATTERNS), 42)
        self.assertIn("db.filter_cmp_top", OFFICIAL_PATTERNS)
        self.assertIn("cal.day_title_count", OFFICIAL_PATTERNS)


if __name__ == "__main__":
    unittest.main()
