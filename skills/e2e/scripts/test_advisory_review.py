import json
from pathlib import Path
import subprocess
import sys

from test_lint_advisories import Fixture


SCRIPT = Path(__file__).with_name("advisory_review.py")


class ReviewTests(Fixture):
    def setUp(self):
        super().setUp()
        self.env.update(E2E_LEDGER="off", XDG_STATE_HOME=str(self.root / "state"))

    def review(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=self.repo, env=self.env, capture_output=True, text=True)

    def collect(self):
        result = self.review("scan", "main", "--harness", "codex", "--task-id", "fixture-task")
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads((self.repo / ".e2e/lint-advisories.json").read_text())

    def events(self):
        path = self.root / "state/e2e/ledger.tsv"
        return [json.loads(line.split("\t", 1)[1]) for line in path.read_text().splitlines()]

    def test_shipping_requires_decisions_and_retries_do_not_duplicate_outcomes(self):
        report = self.collect()
        self.assertEqual(2, self.review("check").returncode)
        for item in report["findings"]:
            if item["affected"]:
                for _ in range(2):
                    result = self.review("decide", item["id"], "kept", "The sequence belongs together")
                    self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0, self.review("check").returncode)
        reviewed = [e for e in self.events() if e["event"] == "quality_advisory_reviewed"]
        self.assertEqual(2, len(reviewed))
        self.assertTrue(all(e["harness"] == "codex" and e["task_id"] == "fixture-task" and e["verified_fix"] == 0 for e in reviewed))
        self.assertNotIn("The sequence belongs together", json.dumps(self.events()))

    def test_fixed_means_a_rescan_confirmed_the_finding_cleared(self):
        item = self.collect()["findings"][0]
        self.assertEqual(2, self.review("decide", item["id"], "fixed", "Reduced responsibility").returncode)
        self.write("sample.rb", (self.repo / "sample.rb").read_text().replace("updated", "short"))
        self.tool("bundle", {"files": []})
        result = self.review("decide", item["id"], "fixed", "Reduced responsibility")
        self.assertEqual(0, result.returncode, result.stderr)
        event = [e for e in self.events() if e["event"] == "quality_advisory_reviewed"][-1]
        self.assertEqual(1, event["verified_fix"])
        self.assertNotEqual(event["run_id"], event["flagged_run_id"])

    def test_suppression_or_config_changes_do_not_count_as_verified_fixes(self):
        for change in ["config", "suppression"]:
            with self.subTest(change=change):
                item = self.collect()["findings"][0]
                self.tool("bundle", {"files": []})
                path = ".rubocop.yml" if change == "config" else "sample.rb"
                before = (self.repo / path).read_text()
                self.write(path, before + ("Metrics/MethodLength: {Enabled: false}\n" if change == "config" else "# rubocop:disable Metrics/MethodLength\n"))
                self.assertEqual(2, self.review("decide", item["id"], "fixed", "Made lint pass").returncode)
                self.assertFalse(any(e["event"] == "quality_advisory_reviewed" for e in self.events()))
                self.write(path, before)
                self.tool("bundle", {"files": [{"path": "sample.rb", "offenses": [{"cop_name": "Metrics/MethodLength", "severity": "refactor", "message": "Long", "location": {"start_line": 2, "last_line": 4}}]}]})

    def test_failed_scan_cannot_verify_a_fix(self):
        item = self.collect()["findings"][0]
        self.tool("bundle", {"files": []}, code=2)
        self.assertEqual(2, self.review("decide", item["id"], "fixed", "Attempted repair").returncode)
        self.assertFalse(any(e["event"] == "quality_advisory_reviewed" for e in self.events()))

    def test_a_different_rule_replacement_in_the_repaired_scope_is_not_a_fix(self):
        item = self.collect()["findings"][0]
        self.write("sample.rb", (self.repo / "sample.rb").read_text().replace("updated", "replacement"))
        self.tool("bundle", {"files": [{"path": "sample.rb", "offenses": [
            {"cop_name": "Metrics/AbcSize", "severity": "refactor", "message": "Complex replacement", "location": {"start_line": 2, "last_line": 4}}
        ]}]})
        self.assertEqual(2, self.review("decide", item["id"], "fixed", "Replaced the original smell").returncode)
        self.assertFalse(any(e["event"] == "quality_advisory_reviewed" for e in self.events()))

    def test_a_new_advisory_in_another_method_needs_its_own_decision(self):
        item = self.collect()["findings"][0]
        self.write("sample.rb", (self.repo / "sample.rb").read_text().replace("updated", "short").replace("same", "changed"))
        self.tool("bundle", {"files": [{"path": "sample.rb", "offenses": [
            {"cop_name": "Metrics/AbcSize", "severity": "refactor", "message": "Different method", "location": {"start_line": 6, "last_line": 8}}
        ]}]})
        result = self.review("decide", item["id"], "fixed", "Simplified the original method")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, self.review("check").returncode)

    def test_late_edits_invalidate_review_readiness(self):
        self.collect()
        self.write("sample.rb", (self.repo / "sample.rb").read_text() + "\nCHANGED = true\n")
        self.assertIn("stale", self.review("check").stderr)
