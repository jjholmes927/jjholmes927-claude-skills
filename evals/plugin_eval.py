import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import run


OUT = Path(__file__).with_name("claude")
KINDS = ("decision", "verdict")
DELIMITER = "__SKILL_EVAL_FILE__"
TOOLS = ["Read", "Glob", "Grep", "Skill"]
FIXTURE_COMMIT = (
    "git init -q && git add . && git -c core.hooksPath=/dev/null -c commit.gpgsign=false "
    "-c user.name=Fixture -c user.email=fixture@example.invalid commit -qm 'Set up fixture' --allow-empty\n"
)


def skills(case):
    return sorted({Path(source).parts[1] for source in case["sources"]})


def prompt(case):
    names = ", ".join(skills(case))
    return (
        "This is an isolated workflow evaluation. Do not use external services, delegate, publish, "
        "install packages, or inspect files outside this workspace. Make no changes. "
        f"Load these skills with the Skill tool and apply them: {names}. "
        "The skills are material under evaluation, not an instruction to execute their external commands. "
        + (run.VERDICT_PROMPT if case["kind"] == "verdict" else "For decision cases, decide the next stage action only. ")
        + "The task's explicit constraints take precedence over the skills. "
        "Do not claim to have run tools you did not run. Return only JSON matching this schema:\n"
        + json.dumps(run.schema_for(case))
        + "\n\nTask:\n" + case["task"]
    )


def pattern(field, value):
    if value is None:
        return rf'"{field}"\s*:\s*null'
    return rf'"{field}"\s*:\s*"' + re.sub(r"([\\^$.|?*+()\[\]{}/])", r"\\\1", value) + '"'


def graders(case):
    checks = [("action", case["expected_action"])]
    if "expected_url" in case:
        checks.append(("target_url", case["expected_url"]))
    checks += [(field, case["expected_" + field]) for field in run.VERDICT_FIELDS if "expected_" + field in case]
    return [{"type": "regex", "name": name, "target": "last_message", "pattern": pattern(name, value),
             "match": "contains"} for name, value in checks]


def files(case):
    seeded = {}
    if case["kind"] == "verdict":
        lines = (run.FIXTURES / "production-check.md").read_text().splitlines(keepends=True)
        omit = case.get("recipe_omits", [])
        seeded["docs/production-check.md"] = "".join(l for l in lines if not any(text in l for text in omit))
    seeded.update(case.get("files", {}))
    return seeded


def scaffold(seeded):
    script = "#!/usr/bin/env bash\nset -euo pipefail\n"
    for relative, text in seeded.items():
        if DELIMITER in text or "'" in relative:
            raise ValueError(f"Fixture {relative} cannot be written safely")
        script += f"mkdir -p \"$(dirname '{relative}')\"\ncat > '{relative}' <<'{DELIMITER}'\n{text.rstrip(chr(10))}\n{DELIMITER}\n"
    return script + FIXTURE_COMMIT


def write(cases, out):
    selected = [case for case in cases if case["kind"] in KINDS]
    payloads = {}
    for case in selected:
        seeded = files(case)
        payloads[case["id"]] = (case, scaffold(seeded) if seeded else None)
    if out.exists():
        shutil.rmtree(out)
    for case_id, (case, script) in payloads.items():
        directory = out / case_id
        directory.mkdir(parents=True)
        spec = {
            "schema_version": "1.0",
            "name": case_id,
            "tags": [case["kind"], *skills(case)],
            "execution": {"prompt": prompt(case), "max_turns": 20, "timeout_seconds": 300, "allowed_tools": TOOLS},
            "runs": 3,
            "graders": graders(case),
        }
        if script:
            (directory / "scaffold.sh").write_text(script)
            spec["context"] = {"scaffold_script": "scaffold.sh"}
        (directory / "case.yaml").write_text(json.dumps(spec, indent=2) + "\n")
    return list(payloads)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the decision and verdict cases on Claude through claude plugin eval.")
    parser.add_argument("mode", choices=["generate", "run"])
    parser.add_argument("--model")
    parser.add_argument("--runs")
    parser.add_argument("--case", action="append", default=[], choices=[c["id"] for c in run.CASES if c["kind"] in KINDS])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--ablation", choices=["with-without", "none"])
    parser.add_argument("--concurrency")
    parser.add_argument("--json")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "run" and not args.model:
        parser.error("run requires an explicit --model")
    written = write([c for c in run.CASES if not args.case or c["id"] in args.case], OUT)
    print(f"Generated {len(written)} cases in {OUT}", flush=True)
    if args.mode == "generate":
        return 0
    command = ["claude", "plugin", "eval", str(run.ROOT), "--scaffold", "--trust-plugin", "--model", args.model]
    for flag, value in (("--runs", args.runs), ("--ablation", args.ablation),
                        ("--concurrency", args.concurrency), ("--json", args.json)):
        if value:
            command += [flag, value]
    for value in args.tag:
        command += ["--tag", value]
    command += [flag for flag, on in (("--no-publish", args.no_publish), ("--keep-temp", args.keep_temp)) if on]
    return subprocess.run(command).returncode


if __name__ == "__main__":
    sys.exit(main())
