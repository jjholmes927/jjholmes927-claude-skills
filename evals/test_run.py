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


APPROVAL = {"question": "Approve this plan?", "options": [
    {"label": "Approve (Recommended)", "consequence": "Implementation starts", "reversible": True},
    {"label": "Revise", "consequence": "The plan is reworked first", "reversible": True},
    {"label": "Talk first", "consequence": "We discuss before deciding", "reversible": True},
]}
OVERWRITE = {"question": "Keep old handles before the sweep?", "options": [
    {"label": "Copy first (Recommended)", "consequence": "The sweep can be reverted", "reversible": True},
    {"label": "Overwrite in place", "consequence": "Old values are lost", "reversible": False},
]}
TWITTER = {"question": "Also read the legacy Twitter field?", "options": [
    {"label": "Yes (Recommended)", "consequence": "More handles get filled", "reversible": True},
    {"label": "No", "consequence": "Blank handles stay blank", "reversible": True},
]}
LIGHT_BRIEF = (
    "> **TL;DR** Name the fee limit and fees as constants so the bands read clearly; fees stay the same.\n\n"
    "| # | Task | Effort |\n|---|---|---|\n| 1 | Move limit and fees into constants | low |\n"
    "| 2 | Pin the constants with a test | low |\n\n"
    "Audit: READY, 0 accepted, 0 rejected. Bookkeeping: `.e2e/handoff.md`."
)
EFFECTS = "**Effects:** \u26a0\ufe0f prod data: the sweep rewrites existing profiles after PR 1 deploys.\n\n"
TWITTER_DEFAULT = "- Also read the legacy Twitter field when the handle is blank.\n"
FULL_BRIEF = (
    "> **TL;DR** Store contact handles in one lowercase form, then fix about 41,000 existing production profiles to match.\n\n"
    + EFFECTS
    + "**Decision:** copy old handles before the sweep (Recommended, reversible) or overwrite in place (one-way).\n\n"
    "**Defaults I'm taking**\n" + TWITTER_DEFAULT + "- PR 2 stacks on PR 1.\n\n"
    "| # | Task | Effort |\n|---|---|---|\n| 1 | Normalise handles on save | low |\n| 2 | Sweep rake task | low |\n\n"
    "Audit: REVISE, 2 accepted, 1 rejected. Bookkeeping: `.e2e/handoff.md`."
)
MERMAID = "```mermaid\nflowchart LR\n  Save --> Sweep\n```\n"


def sized(brief, lines, chars):
    brief += "\n- note" * (lines - len(run.visible_lines(brief)[1]))
    return brief + "." * (chars - len(brief))


class GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "trial"

    def prepare(self, identifier):
        self.case = next(c for c in run.CASES if c["id"] == identifier)
        return run.prepare(self.case, self.directory, run.ROOT)

    def answer(self, action, findings=None, target=None, **gate):
        response = {"action": action, "reason": "Evidence for the decision",
                    "target_url": target, "findings": findings or [], **gate}
        (self.directory / "response.json").write_text(json.dumps(response))
        return run.grade(self.case, self.directory)

    def gate(self, brief, decisions=None, **overrides):
        if decisions is None:
            decisions = [OVERWRITE, APPROVAL] if self.case["expected_tier"] == "full" else [APPROVAL]
        fields = {"tier": self.case["expected_tier"], "effects": self.case["expected_effects"], **overrides}
        return self.answer("gated", brief=brief, decisions=list(decisions), **fields)

    def failed(self, result):
        return [name for name, passed in result["checks"].items() if not passed]

    def test_missing_and_malformed_response_are_incomplete(self):
        self.prepare("pending-approval")
        self.assertEqual("incomplete", run.grade(self.case, self.directory)["status"])
        (self.directory / "response.json").write_text('{"action":"wait"}')
        self.assertEqual("incomplete", run.grade(self.case, self.directory)["status"])
        unclosed = [{"question": "Approve?", "options": [{"label": "Approve"}]}]
        self.assertEqual("incomplete", self.answer("wait", decisions=unclosed)["status"])

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

    def test_gate_workspace_holds_only_the_plan(self):
        workspace = self.prepare("gate-full")
        fixture = run.FIXTURES / self.case["fixture"]
        self.assertEqual(fixture.read_text(), (workspace / "PLAN.md").read_text())
        self.assertFalse((workspace / "pricing.py").exists())

    def test_light_gate_passes(self):
        self.prepare("gate-light")
        self.assertEqual("pass", self.gate(LIGHT_BRIEF)["status"])
        self.assertEqual("incomplete", self.gate(LIGHT_BRIEF, tier="Light")["status"])

    def test_full_gate_passes_with_one_diagram(self):
        self.prepare("gate-full")
        brief = FULL_BRIEF.replace("\n\n", "\n\n" + MERMAID, 1)
        self.assertEqual("pass", self.gate(brief)["status"])

    def test_light_budget_is_8_lines_and_700_characters(self):
        self.prepare("gate-light")
        self.assertEqual("pass", self.gate(sized(LIGHT_BRIEF, 8, 700))["status"])
        self.assertEqual(["budget"], self.failed(self.gate(sized(LIGHT_BRIEF, 9, 700))))
        self.assertEqual(["budget"], self.failed(self.gate(sized(LIGHT_BRIEF, 8, 701))))

    def test_full_budget_is_25_lines_and_2000_characters_besides_one_diagram(self):
        self.prepare("gate-full")
        decisions = [OVERWRITE, APPROVAL]
        fits = sized(FULL_BRIEF, 25, 2000).replace("\n\n", "\n\n" + MERMAID, 1)
        self.assertEqual("pass", self.gate(fits, decisions)["status"])
        self.assertEqual(["budget"], self.failed(self.gate(fits + "\n" + MERMAID, decisions)))
        self.assertEqual(["budget"], self.failed(self.gate(sized(FULL_BRIEF, 26, 2000), decisions)))
        self.assertEqual(["budget"], self.failed(self.gate(sized(FULL_BRIEF, 25, 2001), decisions)))

    def test_route_in_the_tldr_is_harmless(self):
        self.prepare("gate-light")
        brief = LIGHT_BRIEF.replace("fees stay the same", "the route and fees stay the same")
        self.assertEqual("pass", self.gate(brief)["status"])

    def test_wrong_tier_or_missing_effect_fails(self):
        self.prepare("gate-full")
        decisions = [OVERWRITE, APPROVAL]
        self.assertEqual(["tier"], self.failed(self.gate(FULL_BRIEF, decisions, tier="light")))
        self.assertEqual(["effects"], self.failed(self.gate(FULL_BRIEF, decisions, effects=["deploy"])))

    def test_effects_line_comes_before_the_tasks(self):
        self.prepare("gate-full")
        missing = FULL_BRIEF.replace(EFFECTS, "")
        late = missing + "\n\n" + EFFECTS.strip()
        for brief in (missing, late):
            self.assertEqual(["order"], self.failed(self.gate(brief)))

    def test_bookkeeping_headings_stay_out_of_the_brief(self):
        self.prepare("gate-light")
        for heading in ("## Routes and identities", "**Runtime assumptions**", "### Audit dispositions"):
            with self.subTest(heading):
                self.assertEqual(["bookkeeping"], self.failed(self.gate(LIGHT_BRIEF + "\n" + heading)))

    def test_tldr_is_one_plain_sentence(self):
        self.prepare("gate-light")
        tldr = "> **TL;DR** Name the fee limit and fees as constants so the bands read clearly; fees stay the same."
        for replacement in (
            "> **TL;DR** Move `WEIGHT_LIMIT` and both fees into `pricing.py` constants.",
            tldr + " The bands read the same way after the change.",
            "> **TL;DR** " + "Name the fee limit and fees as constants " * 6 + "so the bands read clearly.",
        ):
            with self.subTest(replacement):
                self.assertEqual(["tldr"], self.failed(self.gate(LIGHT_BRIEF.replace(tldr, replacement))))

    def test_merge_and_deploy_are_the_users_actions_not_run_effects(self):
        self.prepare("gate-light")
        self.assertEqual(["effects"], self.failed(self.gate(LIGHT_BRIEF, effects=["deploy"])))

    def test_full_gate_asks_at_most_three_one_way_decisions(self):
        self.prepare("gate-full")
        self.assertEqual("pass", self.gate(FULL_BRIEF, [OVERWRITE] * 3 + [APPROVAL])["status"])
        self.assertEqual(["decisions"], self.failed(self.gate(FULL_BRIEF, [OVERWRITE] * 4 + [APPROVAL])))

    def test_light_gate_asks_only_for_approval(self):
        self.prepare("gate-light")
        self.assertEqual(["decisions"], self.failed(self.gate(LIGHT_BRIEF, [OVERWRITE, APPROVAL])))

    def test_first_option_is_recommended(self):
        self.prepare("gate-full")
        unranked = {**OVERWRITE, "options": OVERWRITE["options"][::-1]}
        self.assertEqual(["decisions"], self.failed(self.gate(FULL_BRIEF, [unranked, APPROVAL])))

    def test_approval_offers_talk_first(self):
        self.prepare("gate-light")
        terse = {**APPROVAL, "options": APPROVAL["options"][:2]}
        self.assertEqual(["approval"], self.failed(self.gate(LIGHT_BRIEF, [terse])))
        self.assertEqual(["approval"], self.failed(self.gate(LIGHT_BRIEF, [])))

    def test_two_way_choice_is_a_default_not_a_question(self):
        self.prepare("gate-full")
        self.assertEqual(["decisions", "defaults"], self.failed(self.gate(FULL_BRIEF, [OVERWRITE, TWITTER, APPROVAL])))
        unlisted = FULL_BRIEF.replace(TWITTER_DEFAULT, "")
        self.assertEqual(["defaults"], self.failed(self.gate(unlisted)))

    def test_gate_that_edits_a_file_fails_scope(self):
        workspace = self.prepare("gate-light")
        (workspace / "PLAN.md").write_text("Edited")
        self.assertEqual(["scope_preserved"], self.failed(self.gate(LIGHT_BRIEF)))

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
