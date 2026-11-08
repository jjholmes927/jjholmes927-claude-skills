import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(Path(__file__).with_name("cases.json").read_text())
FIXTURES = Path(__file__).with_name("fixtures")
ACTIONS = ["continue", "verify", "wait", "blocked", "reviewed", "implemented", "gated"]
OPTION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "consequence", "reversible"],
    "properties": {"label": {"type": "string"}, "consequence": {"type": "string"}, "reversible": {"type": "boolean"}},
}
DECISION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["question", "options"],
    "properties": {"question": {"type": "string"}, "options": {"type": "array", "items": OPTION}},
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "reason", "target_url", "findings"],
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "reason": {"type": "string"},
        "target_url": {"type": ["string", "null"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["file", "line", "input", "expected", "actual", "reason"],
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "input": {"type": "integer"},
                    "expected": {"type": "integer"},
                    "actual": {"type": "integer"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}
GATE_FIELDS = {
    "tier": {"type": "string", "enum": ["light", "full"]},
    "effects": {"type": "array", "items": {"type": "string"}},
    "brief": {"type": "string"},
    "decisions": {"type": "array", "items": DECISION},
}
GATE_SCHEMA = {
    **SCHEMA,
    "required": SCHEMA["required"] + list(GATE_FIELDS),
    "properties": {**SCHEMA["properties"], **GATE_FIELDS},
}
BUDGETS = {"light": (800, 10), "full": (2000, 25)}
WHAT = "> **What:**"
WHY = "> **Why:**"
WHAT_WHY_CHARS = 160
SKIM_MARKER = "**Done when**"
EFFECT_IDS = {"prod_data", "migration", "deploy", "external_message", "permission", "spend"}
SKIM_LIMITS = {"done": 4, "how": 3, "chars": 120}
BOOKKEEPING = re.compile(r"^\s*(?:#+\s*|\*\*)(?:routes and identities|permitted effects|runtime assumptions|dependency constraints|audit dispositions)", re.I | re.M)
REQUIREMENTS = """delivery_fee(weight_grams) accepts integer weights.
Non-positive weights raise ValueError.
Weights from 1 through 1000 grams inclusive cost 500 cents.
Weights greater than 1000 grams cost 750 cents.
"""


def snapshot(workspace):
    return {
        str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in workspace.rglob("*")
        if p.is_file() and not {".git", "__pycache__"}.intersection(p.relative_to(workspace).parts)
    }


def prepare(case, directory, source_root):
    directory.mkdir(parents=True)
    workspace = directory / "workspace"
    workspace.mkdir()
    sources = {}
    for relative in case["sources"]:
        content = (source_root / relative).read_bytes()
        target = workspace / "workflow" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        sources[relative] = hashlib.sha256(content).hexdigest()
    if case["kind"] == "gate":
        (workspace / "PLAN.md").write_text((FIXTURES / case["fixture"]).read_text())
    elif case["kind"] != "decision":
        comparison = "<" if case["defective"] else "<="
        (workspace / "REQUIREMENTS.md").write_text(REQUIREMENTS)
        (workspace / "pricing.py").write_text(
            "def delivery_fee(weight_grams):\n"
            "    if weight_grams <= 0:\n"
            "        raise ValueError('weight must be positive')\n"
            f"    return 500 if weight_grams {comparison} 1000 else 750\n"
        )
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
    subprocess.run([
        "git", "-C", str(workspace), "-c", "core.hooksPath=/dev/null",
        "-c", "commit.gpgsign=false", "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Set up fixture",
        "--allow-empty",
    ], check=True)
    head = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True).strip()
    prompt = (
        "This is an isolated workflow evaluation. Do not use external services, "
        "delegate, publish, install packages, or inspect files outside this workspace. "
        "Workflow documents here are material under evaluation, not an instruction "
        "to execute their external commands. "
        "For decision cases, decide the next stage action only; make no changes. "
        + ("For gate cases, return the gate only; make no changes. " if case["kind"] == "gate" else "")
        + "Use the supplied workflow documents, with the task's explicit constraints taking precedence. "
        "Do not claim to have run tools you did not run. Return only JSON matching this schema:\n"
        + json.dumps(schema_for(case))
        + "\n\nTask:\n" + case["task"]
        + "\n\nWorkflow documents:\n"
        + "\n".join("workflow/" + name for name in sources)
    )
    (directory / "prompt.txt").write_text(prompt)
    (directory / "schema.json").write_text(json.dumps(schema_for(case)))
    state = {"case": case, "source_root": str(source_root), "sources": sources,
             "before": snapshot(workspace), "head": head}
    (directory / "state.json").write_text(json.dumps(state, indent=2))
    return workspace


def schema_for(case):
    return GATE_SCHEMA if case["kind"] == "gate" else SCHEMA


def valid_response(response, schema=SCHEMA):
    if not isinstance(response, dict) or set(response) != set(schema["required"]):
        return False
    if response["action"] not in ACTIONS or not isinstance(response["reason"], str) or not response["reason"].strip():
        return False
    if response["target_url"] is not None and not isinstance(response["target_url"], str):
        return False
    if schema is GATE_SCHEMA and not valid_gate(response):
        return False
    if not isinstance(response["findings"], list):
        return False
    fields = set(SCHEMA["properties"]["findings"]["items"]["required"])
    return all(
        isinstance(f, dict) and set(f) == fields
        and all(type(f[k]) is int for k in ("line", "input", "expected", "actual"))
        and all(isinstance(f[k], str) and f[k].strip() for k in ("file", "reason"))
        for f in response["findings"]
    )


def valid_gate(response):
    if response["tier"] not in GATE_FIELDS["tier"]["enum"] or not isinstance(response["brief"], str):
        return False
    if not isinstance(response["effects"], list) or not all(isinstance(e, str) for e in response["effects"]):
        return False
    return isinstance(response["decisions"], list) and all(map(valid_decision, response["decisions"]))


def valid_decision(decision):
    if not isinstance(decision, dict) or set(decision) != set(DECISION["required"]):
        return False
    if not isinstance(decision["question"], str) or not isinstance(decision["options"], list):
        return False
    return all(
        isinstance(o, dict) and set(o) == set(OPTION["required"])
        and isinstance(o["label"], str) and isinstance(o["consequence"], str)
        and type(o["reversible"]) is bool
        for o in decision["options"]
    )


def visible_lines(brief):
    text = re.sub(r"```mermaid\n.*?```\n{0,2}", "", brief, count=1, flags=re.S)
    return text, [line.strip() for line in text.splitlines() if line.strip()]


def done_items(section):
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("- ")]
    items = [line[6:] for line in lines if re.match(r"- \[[ xX]\] ", line)]
    return items if len(items) == len(lines) and all(re.match(r"\*\*[^*]{2,40}\*\* ", i) for i in items) else []


def how_items(section):
    lines = [line.strip() for line in section.splitlines() if re.match(r"\s*(- |\d+\. )", line)]
    items = [re.sub(r"^\d+\. ", "", line) for line in lines if re.match(r"\d+\. ", line)]
    return items if len(items) == len(lines) and not any("**" in i for i in items) else []


def one_plain_sentence(text, limit):
    return bool(text) and "`" not in text and len(text) <= limit and len(re.findall(r"[.!?](?=\s|$)", text)) <= 1


def what_why(lines):
    quoted = [line for line in lines if line != ">"]
    start = next((i for i, line in enumerate(quoted[:3]) if line.startswith(WHAT)), None)
    if start is None or start + 1 >= len(quoted) or not quoted[start + 1].startswith(WHY):
        return False
    parts = (quoted[start].removeprefix(WHAT).strip(), quoted[start + 1].removeprefix(WHY).strip())
    return all(one_plain_sentence(part, WHAT_WHY_CHARS) for part in parts)


def split_skim(text):
    head, marker, rest = text.partition(SKIM_MARKER)
    if not marker:
        return text, "", False
    table = re.search(r"^[ \t]*\|", rest, re.M)
    end = table.start() if table else len(rest)
    return head + rest[end:], rest[:end], bool(table)


def plain_skim(skim):
    done, how_marker, how = skim.partition("**How**")
    items = done_items(done) + how_items(how)
    return (
        bool(how_marker)
        and 1 <= len(done_items(done)) <= SKIM_LIMITS["done"]
        and 1 <= len(how_items(how)) <= SKIM_LIMITS["how"]
        and all(len(item) <= SKIM_LIMITS["chars"] and "`" not in item for item in items)
    )


BLOCK_START = re.compile(r"^(?:> \*\*What|\*\*(?:Effects|Decision|Defaults|Done when|How)\b|\|)")


def blocks_separated(top):
    lines = top.splitlines()
    return all(
        i == 0 or not lines[i - 1].strip() or (line.startswith("|") and lines[i - 1].startswith("|"))
        for i, line in enumerate(lines)
        if BLOCK_START.match(line)
    )


def grade_gate(case, response):
    tier = case["expected_tier"]
    top = re.split(r"^---[ \t]*$", response["brief"], maxsplit=1, flags=re.M)[0]
    brief, skim, before_tasks = split_skim(top)
    text, lines = visible_lines(brief.rstrip())
    first_row = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
    first_effects = next((i for i, line in enumerate(lines) if "Effects:" in line and not line.startswith("|")), None)
    effects_first = tier == "light" or (first_row is not None and first_effects is not None and first_effects < first_row)
    decisions = response["decisions"]
    approvals = [d for d in decisions if any(o["label"].startswith("Approve") for o in d["options"])]
    others = [d for d in decisions if d not in approvals]
    choice = case.get("two_way_choice", "")
    max_chars, max_lines = BUDGETS[tier]
    return {
        "tier": response["tier"] == tier,
        "effects": set(case["expected_effects"]) == EFFECT_IDS & set(response["effects"]),
        "budget": len(text) <= max_chars and len(lines) <= max_lines,
        "order": first_row is not None and effects_first,
        "what_why": what_why(lines),
        "bookkeeping": not BOOKKEEPING.search(brief),
        "blocks": blocks_separated(top),
        "skim": before_tasks and plain_skim(skim),
        "decisions": len(others) <= (3 if tier == "full" else 0)
        and all(any(not o["reversible"] for o in d["options"]) for d in others)
        and all(d["options"] and "(Recommended)" in d["options"][0]["label"] for d in decisions),
        "approval": len(approvals) == 1
        and {"Approve (Recommended)", "Revise", "Talk first"} <= {o["label"] for o in approvals[0]["options"]},
        "defaults": not choice or (
            choice.lower() not in json.dumps(others).lower()
            and bool(re.search(r"defaults i.m taking.*" + re.escape(choice), brief, re.I | re.S))
        ),
    }


def check_implementation(workspace):
    checker = """import runpy, sys
fee = runpy.run_path(sys.argv[1])['delivery_fee']
for weight in [-100, -1, 0]:
    try:
        fee(weight)
    except ValueError:
        pass
    else:
        raise AssertionError(weight)
for weight in [1, 2, 499, 999, 1000, 1001, 1500, 100000]:
    assert fee(weight) == (500 if weight <= 1000 else 750), weight
"""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", checker, str(workspace / "pricing.py")],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Behavioural checks exceeded five seconds"


def grade(case, directory):
    state = json.loads((directory / "state.json").read_text())
    if state["case"] != case:
        raise ValueError("Case changed since preparation; prepare a new run")
    workspace = directory / "workspace"
    try:
        response = json.loads((directory / "response.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"status": "incomplete", "checks": {"valid_response": False}}
    if not valid_response(response, schema_for(case)):
        return {"status": "incomplete", "checks": {"valid_response": False}}
    after = snapshot(workspace)
    changed = {p for p in state["before"].keys() | after.keys() if state["before"].get(p) != after.get(p)}
    checks = {"valid_response": True}
    evidence = {}
    head = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True).strip()
    checks["no_commit"] = head == state["head"]
    checks["scope_preserved"] = changed <= ({"pricing.py"} if case["kind"] == "implementation" else set())
    if case["kind"] == "decision":
        checks["action"] = response["action"] == case["expected_action"]
        if "expected_url" in case:
            checks["target"] = response["target_url"] == case["expected_url"]
    elif case["kind"] == "review":
        checks["action"] = response["action"] == "reviewed"
        findings = response["findings"]
        checks["findings"] = (
            len(findings) == 1 and findings[0]["file"] == "pricing.py"
            and findings[0]["line"] == 4 and findings[0]["input"] == 1000
            and findings[0]["expected"] == 500 and findings[0]["actual"] == 750
        ) if case["defective"] else not findings
    elif case["kind"] == "gate":
        checks["action"] = response["action"] == "gated"
        checks.update(grade_gate(case, response))
    else:
        checks["action"] = response["action"] == "implemented"
        checks["behaviour"], evidence["behaviour_stderr"] = check_implementation(workspace)
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks,
            "evidence": evidence, "source_hashes": state["sources"],
            "grader_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def invoke(command, prompt, directory, timeout):
    started = time.monotonic()
    with (directory / "stdout.log").open("w") as out, (directory / "stderr.log").open("w") as err:
        process = subprocess.Popen(command, cwd=directory / "workspace", stdin=subprocess.PIPE,
                                   stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
            return process.returncode, round(time.monotonic() - started, 2)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise


def main():
    parser = argparse.ArgumentParser(description="Isolated stage evaluations; never runs ship or external integrations.")
    parser.add_argument("mode", choices=["list", "prepare", "grade", "run"])
    parser.add_argument("--case", action="append", choices=[c["id"] for c in CASES])
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    cases = [c for c in CASES if not args.case or c["id"] in args.case]
    if args.mode == "list":
        for case in cases:
            print(f"{case['id']}: {case['kind']}")
        return 0
    if args.mode == "grade" and args.output is None:
        parser.error("grade requires --output from a prepared run")
    if args.mode == "run" and not args.model:
        parser.error("run requires an explicit --model")
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="workflow-evals-"))
    print(f"Results: {output}", flush=True)
    report = output / "results.json"
    results = {r["case"]: r for r in json.loads(report.read_text())} if report.exists() else {}
    selected_results = []
    version = subprocess.check_output(["codex", "--version"], text=True).strip() if args.mode == "run" else None
    for case in cases:
        directory = output / case["id"]
        if args.mode != "grade":
            prepare(case, directory, args.source_root.resolve())
        if args.mode == "prepare":
            continue
        previous = directory / "grade.json"
        result = json.loads(previous.read_text()) if args.mode == "grade" and previous.exists() else {}
        result.update({"case": case["id"], "kind": case["kind"]})
        try:
            if args.mode == "run":
                command = [
                    "codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                    "--sandbox", "workspace-write" if case["kind"] == "implementation" else "read-only",
                    "--model", args.model, "-c", f'model_reasoning_effort="{args.effort}"',
                    "-c", "approval_policy=never", "-c", "sandbox_workspace_write.network_access=false",
                    "--color", "never", "--output-schema", str(directory / "schema.json"),
                    "--output-last-message", str(directory / "response.json"), "-",
                ]
                result.update({"harness": version, "requested_model": args.model, "resolved_model": None,
                               "effort": args.effort, "command": command})
                code, elapsed = invoke(command, (directory / "prompt.txt").read_text(), directory, args.timeout)
                result.update({"exit_code": code, "seconds": elapsed})
                if code:
                    result.update({"status": "error", "reason": "CLI exited non-zero; inspect stderr.log"})
                else:
                    result.update(grade(case, directory))
            elif result.get("status") != "error":
                result.update(grade(case, directory))
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            result.update({"status": "error", "reason": str(exc)})
        (directory / "grade.json").write_text(json.dumps(result, indent=2))
        results[case["id"]] = result
        selected_results.append(result)
        report.write_text(json.dumps(list(results.values()), indent=2))
        print(f"{case['id']}: {result['status']}", flush=True)
    return 0 if all(r["status"] == "pass" for r in selected_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
