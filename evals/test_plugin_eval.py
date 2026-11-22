import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import plugin_eval
import run


def by_id(case_id):
    return next(c for c in run.CASES if c["id"] == case_id)


def regex(grader):
    return re.compile(grader["pattern"])


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "claude"
        self.written = plugin_eval.write(run.CASES, self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def case(self, case_id):
        return json.loads((self.out / case_id / "case.yaml").read_text())

    def test_only_exact_answer_kinds_are_converted(self):
        expected = sorted(c["id"] for c in run.CASES if c["kind"] in ("decision", "verdict"))
        self.assertEqual(expected, sorted(self.written))
        self.assertEqual(expected, sorted(p.name for p in self.out.iterdir()))

    def test_case_loads_the_real_skill_and_carries_the_task(self):
        source = by_id("clean-committed-branch")
        case = self.case("clean-committed-branch")
        self.assertEqual("1.0", case["schema_version"])
        self.assertEqual("clean-committed-branch", case["name"])
        self.assertIn("apply them: ship.", case["execution"]["prompt"])
        self.assertIn(source["task"], case["execution"]["prompt"])
        self.assertIn("Skill", case["execution"]["allowed_tools"])
        self.assertNotIn("Bash", case["execution"]["allowed_tools"])
        self.assertIn("ship", case["tags"])
        self.assertIn("decision", case["tags"])

    def test_action_grader_matches_only_the_expected_action(self):
        grader = next(g for g in self.case("clean-committed-branch")["graders"] if g["name"] == "action")
        self.assertEqual("last_message", grader["target"])
        self.assertTrue(regex(grader).search('```json\n{"action": "continue", "reason": "x"}\n```'))
        self.assertFalse(regex(grader).search('{"action": "verify", "reason": "continue"}'))

    def test_expected_url_becomes_a_target_grader(self):
        grader = next(g for g in self.case("worktree-server")["graders"] if g["name"] == "target_url")
        self.assertTrue(regex(grader).search('{"target_url": "http://localhost:4371"}'))
        self.assertFalse(regex(grader).search('{"target_url": "http://localhost:3000"}'))

    def test_verdict_case_grades_every_expected_field(self):
        source = by_id("error-spike-opens-revert-not-merged")
        expected = {"action"} | {f for f in run.VERDICT_FIELDS if "expected_" + f in source}
        case = self.case("error-spike-opens-revert-not-merged")
        self.assertEqual(expected, {g["name"] for g in case["graders"]})
        revert = next(g for g in case["graders"] if g["name"] == "revert")
        self.assertTrue(regex(revert).search(f'"revert": "{source["expected_revert"]}"'))
        self.assertFalse(regex(revert).search('"revert": "nonsense"'))
        self.assertIn(run.VERDICT_PROMPT, case["execution"]["prompt"])

    def test_scaffold_seeds_the_recipe_without_omitted_lines(self):
        workspace = Path(self.tmp.name) / "ws"
        workspace.mkdir()
        case_dir = self.out / "no-agent-identity-falls-back-to-ticket"
        self.assertEqual("scaffold.sh", self.case(case_dir.name)["context"]["scaffold_script"])
        subprocess.run(["bash", str(case_dir / "scaffold.sh")], cwd=workspace, check=True)
        recipe = (workspace / "docs/production-check.md").read_text()
        self.assertNotIn("**Agent identity:**", recipe)
        self.assertIn("Deploy signal", recipe)
        self.assertTrue((workspace / ".git").is_dir())

    def test_scaffold_seeds_case_files(self):
        files = {".e2e/handoff.md": "Verified at abc123\n", "notes.txt": "it's fine\n"}
        case = {**by_id("clean-committed-branch"), "id": "with-files", "files": files}
        out = Path(self.tmp.name) / "files"
        plugin_eval.write([case], out)
        workspace = Path(self.tmp.name) / "ws"
        workspace.mkdir()
        subprocess.run(["bash", str(out / "with-files" / "scaffold.sh")], cwd=workspace, check=True)
        for relative, text in files.items():
            self.assertEqual(text, (workspace / relative).read_text())

    def test_cases_without_files_have_no_scaffold(self):
        self.assertNotIn("scaffold_script", self.case("clean-committed-branch").get("context", {}))
        self.assertFalse((self.out / "clean-committed-branch" / "scaffold.sh").exists())

    def test_rewrite_removes_stale_cases(self):
        (self.out / "deleted-case").mkdir()
        plugin_eval.write(run.CASES, self.out)
        self.assertFalse((self.out / "deleted-case").exists())

    def test_file_text_cannot_break_out_of_the_scaffold(self):
        case = {**by_id("clean-committed-branch"), "files": {"x.md": f"a\n{plugin_eval.DELIMITER}\nrm -rf /\n"}}
        with self.assertRaises(ValueError):
            plugin_eval.write([case], Path(self.tmp.name) / "bad")


class RunTests(unittest.TestCase):
    def test_run_generates_then_calls_plugin_eval_on_this_checkout(self):
        with patch.object(plugin_eval, "write", return_value=["a"]) as write, \
                patch.object(plugin_eval.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as call:
            code = plugin_eval.main(["run", "--model", "opus", "--runs", "1", "--ablation", "none", "--json", "out.json"])
        self.assertEqual(0, code)
        write.assert_called_once_with(run.CASES, plugin_eval.OUT)
        command = call.call_args.args[0]
        self.assertEqual(["claude", "plugin", "eval", str(run.ROOT)], command[:4])
        for flag in (["--model", "opus"], ["--runs", "1"], ["--ablation", "none"], ["--json", "out.json"]):
            self.assertIn(flag, [command[i:i + 2] for i in range(len(command))])
        self.assertIn("--scaffold", command)
        self.assertIn("--trust-plugin", command)

    def test_run_generates_only_the_chosen_cases(self):
        with patch.object(plugin_eval, "write", return_value=["a"]) as write, \
                patch.object(plugin_eval.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as call:
            plugin_eval.main(["run", "--model", "opus", "--case", "prod-check-pass", "--case", "clean-committed-branch"])
        self.assertEqual(["clean-committed-branch", "prod-check-pass"], sorted(c["id"] for c in write.call_args.args[0]))
        self.assertNotIn("--case", call.call_args.args[0])

    def test_run_requires_a_model(self):
        with self.assertRaises(SystemExit):
            plugin_eval.main(["run"])


if __name__ == "__main__":
    unittest.main()
