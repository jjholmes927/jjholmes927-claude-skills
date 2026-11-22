import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import compare
import run


SHIP = {"id": "ship-case", "kind": "decision", "sources": ["skills/ship/SKILL.md"], "task": "t", "expected_action": "wait"}
VERIFY = {"id": "verify-case", "kind": "verdict", "sources": ["skills/verify/SKILL.md"], "task": "t",
          "expected_action": "continue", "expected_verdict": "pass"}
GATE = {"id": "gate-case", "kind": "gate", "sources": ["skills/ship/SKILL.md"], "task": "t"}


def checkout(root, files):
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


class SelectionTests(unittest.TestCase):
    def test_a_change_anywhere_in_a_skill_folder_selects_its_cases(self):
        cases = [SHIP, VERIFY, GATE]
        self.assertEqual([SHIP], compare.covering(cases, {"skills/ship/references/landing.md"}))
        self.assertEqual([SHIP, VERIFY], compare.covering(cases, {"skills/ship/SKILL.md", "skills/verify/SKILL.md"}))
        self.assertEqual([], compare.covering(cases, {"README.md", "skills/brief/SKILL.md"}))


class KeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = checkout(Path(self.tmp.name), {"skills/ship/SKILL.md": "rules", "skills/ship/references/a.md": "a",
                                                  "skills/verify/SKILL.md": "v"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_follows_the_skill_folder_model_and_runs(self):
        key = compare.cache_key(SHIP, self.root, "opus", 3)
        self.assertEqual(key, compare.cache_key(SHIP, self.root, "opus", 3))
        self.assertNotEqual(key, compare.cache_key(SHIP, self.root, "sonnet", 3))
        self.assertNotEqual(key, compare.cache_key(SHIP, self.root, "opus", 1))
        (self.root / "skills/verify/SKILL.md").write_text("changed")
        self.assertEqual(key, compare.cache_key(SHIP, self.root, "opus", 3))
        (self.root / "skills/ship/references/a.md").write_text("changed")
        self.assertNotEqual(key, compare.cache_key(SHIP, self.root, "opus", 3))

    def test_key_follows_the_case_itself(self):
        key = compare.cache_key(SHIP, self.root, "opus", 3)
        self.assertNotEqual(key, compare.cache_key({**SHIP, "expected_action": "continue"}, self.root, "opus", 3))


class ParseTests(unittest.TestCase):
    def test_counts_passes_and_leaves_errored_cases_out(self):
        report = {"cases": [
            {"name": "ship-case", "arms": {"with": [{"passed": True, "error": None}, {"passed": False, "error": None},
                                                   {"passed": True, "error": None}]}},
            {"name": "verify-case", "arms": {"with": [{"passed": False, "error": "exit 1: You've hit your limit"},
                                                     {"passed": True, "error": None}]}},
        ]}
        self.assertEqual({"ship-case": {"passed": 2, "runs": 3}}, compare.parse(report))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.base = checkout(Path(self.tmp.name) / "base", {"skills/ship/SKILL.md": "old", "skills/verify/SKILL.md": "v"})
        self.head = checkout(Path(self.tmp.name) / "head", {"skills/ship/SKILL.md": "new", "skills/verify/SKILL.md": "v"})

    def tearDown(self):
        self.tmp.cleanup()

    def results(self, base, head):
        def fake(root, cases, model, runs, concurrency):
            table = base if root == self.base else head
            return {c["id"]: table[c["id"]] for c in cases if c["id"] in table}
        return fake

    def test_reports_each_case_and_flags_a_real_drop(self):
        fake = self.results({"ship-case": {"passed": 3, "runs": 3}}, {"ship-case": {"passed": 1, "runs": 3}})
        with patch.object(compare, "run_version", side_effect=fake):
            rows = compare.compare([SHIP], self.base, self.head, "opus", 3, 4, self.cache)
        self.assertEqual([{"case": "ship-case", "before": 3, "after": 1, "runs": 3, "drop": True}], rows)

    def test_a_one_run_wobble_is_not_a_drop(self):
        fake = self.results({"ship-case": {"passed": 3, "runs": 3}}, {"ship-case": {"passed": 2, "runs": 3}})
        with patch.object(compare, "run_version", side_effect=fake):
            rows = compare.compare([SHIP], self.base, self.head, "opus", 3, 4, self.cache)
        self.assertFalse(rows[0]["drop"])

    def test_cached_results_are_not_run_again(self):
        fake = self.results({"ship-case": {"passed": 3, "runs": 3}}, {"ship-case": {"passed": 3, "runs": 3}})
        with patch.object(compare, "run_version", side_effect=fake) as runner:
            compare.compare([SHIP], self.base, self.head, "opus", 3, 4, self.cache)
            self.assertEqual(2, runner.call_count)
            compare.compare([SHIP], self.base, self.head, "opus", 3, 4, self.cache)
            self.assertEqual(2, runner.call_count)

    def test_unchanged_skill_reuses_the_same_result_for_both_sides(self):
        fake = self.results({"verify-case": {"passed": 2, "runs": 3}}, {"verify-case": {"passed": 0, "runs": 3}})
        with patch.object(compare, "run_version", side_effect=fake) as runner:
            rows = compare.compare([VERIFY], self.base, self.head, "opus", 3, 4, self.cache)
        self.assertEqual(1, runner.call_count)
        self.assertEqual((2, 2), (rows[0]["before"], rows[0]["after"]))

    def test_errored_cases_are_reported_and_not_cached(self):
        fake = self.results({"ship-case": {"passed": 3, "runs": 3}}, {})
        with patch.object(compare, "run_version", side_effect=fake):
            rows = compare.compare([SHIP], self.base, self.head, "opus", 3, 4, self.cache)
        self.assertIsNone(rows[0]["after"])
        self.assertFalse(rows[0]["drop"])
        self.assertEqual(1, len(list(self.cache.iterdir())))


class TableTests(unittest.TestCase):
    def test_table_marks_drops_and_errors(self):
        text = compare.table([
            {"case": "a", "before": 3, "after": 3, "runs": 3, "drop": False},
            {"case": "b", "before": 3, "after": 1, "runs": 3, "drop": True},
            {"case": "c", "before": 3, "after": None, "runs": 3, "drop": False},
        ])
        self.assertIn("| a | 3/3 | 3/3 |  |", text)
        self.assertIn("| b | 3/3 | 1/3 | drop |", text)
        self.assertIn("| c | 3/3 | error |  |", text)
        self.assertIn("1 drop", text)


class MainTests(unittest.TestCase):
    def test_no_covered_change_runs_nothing(self):
        with patch.object(compare, "changed_files", return_value={"README.md"}), \
                patch.object(compare, "compare") as runner:
            self.assertEqual(0, compare.main(["origin/master", "--model", "opus"]))
        runner.assert_not_called()

    def test_exit_code_is_one_on_a_drop(self):
        row = {"case": "land-opted-in-green", "before": 3, "after": 0, "runs": 3, "drop": True}
        with patch.object(compare, "changed_files", return_value={"skills/ship/SKILL.md"}), \
                patch.object(compare, "base_checkout") as base, \
                patch.object(compare, "compare", return_value=[row]):
            base.return_value.__enter__.return_value = Path("/tmp/base")
            self.assertEqual(1, compare.main(["origin/master", "--model", "opus", "--case", "land-opted-in-green"]))


if __name__ == "__main__":
    unittest.main()
