import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run


class GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "trial"

    def prepare(self, identifier):
        self.case = next(c for c in run.CASES if c["id"] == identifier)
        return run.prepare(self.case, self.directory, run.ROOT)

    def answer(self, action, findings=None, target=None):
        response = {"action": action, "reason": "Evidence for the decision",
                    "target_url": target, "findings": findings or []}
        (self.directory / "response.json").write_text(json.dumps(response))
        return run.grade(self.case, self.directory)

    def test_missing_and_malformed_response_are_incomplete(self):
        self.prepare("pending-approval")
        self.assertEqual("incomplete", run.grade(self.case, self.directory)["status"])
        (self.directory / "response.json").write_text('{"action":"wait"}')
        self.assertEqual("incomplete", run.grade(self.case, self.directory)["status"])

    def test_approval_wait_and_continue_are_distinguished(self):
        self.prepare("pending-approval")
        self.assertEqual("pass", self.answer("wait")["status"])
        self.assertEqual("fail", self.answer("continue")["status"])

    def test_wrong_server_fails_even_with_correct_action(self):
        self.prepare("worktree-server")
        self.assertEqual("fail", self.answer("verify", target="http://localhost:3000")["status"])
        self.assertEqual("pass", self.answer("verify", target="http://localhost:4371")["status"])

    def test_actual_review_mutation_fails(self):
        workspace = self.prepare("review-correct-boundary")
        self.assertEqual("pass", self.answer("reviewed")["status"])
        (workspace / "REQUIREMENTS.md").write_text("Changed scope")
        self.assertFalse(self.answer("reviewed")["checks"]["scope_preserved"])

    def test_defect_requires_a_valid_counterexample(self):
        self.prepare("review-boundary-defect")
        self.assertEqual("fail", self.answer("reviewed")["status"])
        finding = {"file": "pricing.py", "line": 4, "input": 1000,
                   "expected": 500, "actual": 750, "reason": "Inclusive boundary is excluded"}
        self.assertEqual("pass", self.answer("reviewed", [finding])["status"])
        finding["input"] = 999
        self.assertEqual("fail", self.answer("reviewed", [finding])["status"])

    def test_claimed_success_is_not_implementation_success(self):
        workspace = self.prepare("implement-boundary-fix")
        self.assertEqual("fail", self.answer("implemented")["status"])
        source = workspace / "pricing.py"
        source.write_text(source.read_text().replace("< 1000", "<= 1000"))
        self.assertEqual("pass", self.answer("implemented")["status"])
        source.write_text("def delivery_fee(weight_grams):\n    return 500\n")
        self.assertEqual("fail", self.answer("implemented")["status"])

    def test_changed_case_cannot_be_silently_regraded(self):
        self.prepare("pending-approval")
        with self.assertRaises(ValueError):
            run.grade({**self.case, "expected_action": "continue"}, self.directory)

    def test_existing_trial_cannot_be_overwritten(self):
        self.prepare("pending-approval")
        with self.assertRaises(FileExistsError):
            run.prepare(self.case, self.directory, run.ROOT)

    def test_regrading_preserves_provenance_and_other_results(self):
        self.prepare("pending-approval")
        self.answer("wait")
        old = {"case": self.case["id"], "status": "pass", "requested_model": "recorded-model", "seconds": 10}
        (self.directory / "grade.json").write_text(json.dumps(old))
        report = self.directory.parent / "results.json"
        report.write_text(json.dumps([old, {"case": "other-trial", "status": "fail"}]))
        self.directory.rename(self.directory.parent / self.case["id"])
        argv = ["run.py", "grade", "--output", str(report.parent), "--case", self.case["id"]]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, run.main())
        results = {r["case"]: r for r in json.loads(report.read_text())}
        self.assertEqual("recorded-model", results[self.case["id"]]["requested_model"])
        self.assertEqual(10, results[self.case["id"]]["seconds"])
        self.assertEqual("fail", results["other-trial"]["status"])

    def test_timeout_terminates_the_local_process(self):
        self.prepare("pending-approval")
        with self.assertRaises(subprocess.TimeoutExpired):
            run.invoke([sys.executable, "-c", "import time; time.sleep(60)"], "", self.directory, 0.05)


if __name__ == "__main__":
    unittest.main()
