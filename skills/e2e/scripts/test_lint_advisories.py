import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPT = Path(__file__).with_name("lint_advisories.py")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        self.run_git("init", "-q", "-b", "main")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.run_git("config", "user.name", "Fixture")
        self.run_git("remote", "add", "origin", "https://ignored:secret@github.com/owner/project.git")
        self.write(".rubocop.yml", "AllCops: {}\n")
        self.write("eslint.config.mjs", "export default []\n")
        self.write("package.json", '{}\n')
        self.write("pnpm-lock.yaml", "")
        self.write("sample.rb", "class Example\n  def call\n    old\n  end\n\n  def untouched\n    same\n  end\nend\n")
        self.write("sample.ts", "function call() {\n  return 1\n}\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "base")
        self.run_git("switch", "-qc", "feature")
        self.write("sample.rb", (self.repo / "sample.rb").read_text().replace("old", "updated"))
        self.write("sample.ts", (self.repo / "sample.ts").read_text().replace("return 1", "return 2"))
        self.tool("bundle", {"files": [{"path": "sample.rb", "offenses": [
            {"cop_name": "Metrics/MethodLength", "severity": "refactor", "message": "Long method", "location": {"start_line": 2, "last_line": 4}},
            {"cop_name": "Metrics/MethodLength", "severity": "refactor", "message": "Old method", "location": {"start_line": 6, "last_line": 8}}
        ]}]})
        self.tool("pnpm", [{"filePath": str(self.repo / "sample.ts"), "messages": [
            {"ruleId": "max-lines-per-function", "severity": 1, "line": 1, "endLine": 3, "message": "Long function"}
        ]}])

    def run_git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, text=True).strip()

    def write(self, path, content):
        (self.repo / path).write_text(content)

    def tool(self, name, payload, code=0, clones=None):
        (self.root / f"{name}.json").write_text(json.dumps(payload))
        (self.root / "clones.json").write_text(json.dumps(clones))
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(f"""\
            import pathlib
            import sys
            args = sys.argv
            if 'jscpd' in args:
                target = pathlib.Path(args[args.index('--output') + 1], 'jscpd-report.json')
                target.write_text(pathlib.Path({str(self.root / 'clones.json')!r}).read_text())
                sys.exit(1)
            flag = '--out' if '--out' in args else '--output-file'
            target = pathlib.Path(args[args.index(flag) + 1])
            target.write_text(pathlib.Path({str(self.root / (name + '.json'))!r}).read_text())
            sys.exit({code})
        """))
        path.chmod(0o755)

    def scan(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "main", "--harness", "codex"], cwd=self.repo, env=self.env, capture_output=True, text=True)
        report = json.loads((self.repo / ".e2e/lint-advisories.json").read_text())
        return result.returncode, report


class AdvisoryTests(Fixture):
    def test_body_edits_are_reviewed_but_an_untouched_method_is_not(self):
        code, report = self.scan()
        self.assertEqual(0, code)
        self.assertEqual("github.com/owner/project", report["repo"])
        self.assertEqual("codex", report["harness"])
        self.assertEqual([True, False, True], [item["affected"] for item in report["findings"]])
        self.assertEqual(report["tree"], report["tree_after"])
        self.assertNotIn("secret", json.dumps(report))

    def test_reruns_have_new_run_ids_but_stable_finding_ids(self):
        _, first = self.scan()
        _, second = self.scan()
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual([f["id"] for f in first["findings"]], [f["id"] for f in second["findings"]])

    def test_a_blocking_offense_preserves_a_nonzero_exit(self):
        self.tool("bundle", {"files": []}, code=1)
        code, report = self.scan()
        self.assertEqual(1, code)
        self.assertEqual("complete", report["tools"]["rubocop"]["status"])

    def test_bad_output_is_incomplete_instead_of_clean(self):
        (self.root / "bundle.json").write_text("not json")
        code, report = self.scan()
        self.assertEqual(2, code)
        self.assertEqual("incomplete", report["tools"]["rubocop"]["status"])

    def test_tool_failure_is_incomplete(self):
        self.tool("bundle", {"files": []}, code=2)
        self.assertEqual(2, self.scan()[0])

    def test_bad_package_configuration_is_recorded_as_incomplete(self):
        self.write("package.json", "not json")
        code, report = self.scan()
        self.assertEqual(2, code)
        self.assertEqual("incomplete", report["tools"]["configuration"]["status"])

    def test_file_length_applies_to_edits_before_the_reported_excess(self):
        self.tool("pnpm", [{"filePath": str(self.repo / "sample.ts"), "messages": [
            {"ruleId": "max-lines", "severity": 1, "line": 3, "endLine": 3, "message": "Long file"}
        ]}])
        report = self.scan()[1]
        self.assertTrue(next(f for f in report["findings"] if f["rule"] == "max-lines")["affected"])
        identifier = next(f["id"] for f in report["findings"] if f["rule"] == "max-lines")
        self.write("sample.ts", "'use strict'\n" + (self.repo / "sample.ts").read_text())
        self.assertEqual(identifier, next(f["id"] for f in self.scan()[1]["findings"] if f["rule"] == "max-lines"))

    def test_same_named_methods_have_distinct_ids(self):
        self.write("sample.rb", (self.repo / "sample.rb").read_text().replace("def untouched", "def call"))
        items = [f for f in self.scan()[1]["findings"] if f["tool"] == "rubocop"]
        self.assertEqual(2, len({f["id"] for f in items}))

    def test_same_rule_reports_on_one_line_keep_distinct_columns(self):
        self.tool("pnpm", [{"filePath": str(self.repo / "sample.ts"), "messages": [
            {"ruleId": "no-unused-vars", "severity": 1, "line": 2, "column": column, "endLine": 2, "message": "Unused variable"}
            for column in [3, 12]
        ]}])
        items = [f for f in self.scan()[1]["findings"] if f["tool"] == "eslint"]
        self.assertEqual(2, len(items))
        self.assertEqual(2, len({f["id"] for f in items}))

    def test_repeated_reports_preserve_occurrences_without_duplicate_decisions(self):
        message = {"ruleId": "max-lines-per-function", "severity": 1, "line": 1, "column": 1, "endLine": 3, "message": "Long function"}
        self.tool("pnpm", [{"filePath": str(self.repo / "sample.ts"), "messages": [message, message]}])
        item = next(f for f in self.scan()[1]["findings"] if f["tool"] == "eslint")
        self.assertEqual(2, item["occurrences"])

    def test_duplication_checks_both_sides_and_stays_advisory_above_threshold(self):
        self.write(".jscpd.json", "{}")
        payload = {"duplicates": [{"firstFile": {"name": "sample.rb", "start": 2, "end": 4},
                                   "secondFile": {"name": "sample.rb", "start": 6, "end": 8}}]}
        self.tool("pnpm", [], clones=payload)
        code, report = self.scan()
        self.assertEqual(0, code)
        self.assertEqual(1, report["tools"]["jscpd"]["exit"])
        clones = [f for f in report["findings"] if f["tool"] == "jscpd"]
        self.assertEqual(1, len(clones))
        self.assertTrue(clones[0]["affected"])


if __name__ == "__main__":
    unittest.main()
