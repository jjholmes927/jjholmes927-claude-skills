#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
import lint_advisories as lint


HERE = Path(__file__).resolve().parent
REPORT = Path(".e2e/lint-advisories.json")
DECISIONS = Path(".e2e/lint-decisions.jsonl")


def emit(event, report, **fields):
    context = {key: report[key] for key in ["repo", "head", "tree", "run_id", "harness", "workflow", "collector"]}
    context.update({key: report[key] for key in ["task_id", "session_id", "trace.trace_id", "trace.parent_id"] if report.get(key)})
    args = [f"{key}={value}" for key, value in {**context, **fields}.items()]
    try:
        result = subprocess.run(["bash", "-c", '. "$1"; shift; emit "$@"', "ledger", str(HERE / "ledger.sh"), event, *args], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    print("Advisory telemetry delivery incomplete; inspect the local ledger.", file=sys.stderr)


def collect(base, harness, workflow, task_id=None, session_id=None, extra=()):
    report = lint.scan(base, harness, extra)
    report.update(workflow=workflow, task_id=task_id, session_id=session_id)
    trace = re.fullmatch(r"[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}", os.environ.get("TRACEPARENT", ""))
    if trace:
        report.update({"trace.trace_id": trace[1], "trace.parent_id": trace[2]})
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    affected = [f for f in report["findings"] if f["affected"]]
    emit("quality_advisory_scan", report, finding_count=len(affected), scan_exit=lint.exit_status(report),
         incomplete_tools=",".join(tool for tool, state in report["tools"].items() if state["status"] != "complete"))
    for item in affected:
        emit("quality_advisory_flagged", report, finding_id=item["id"], tool=item["tool"], rule=item["rule"],
             path=item["path"], lint_severity=item["severity"])
    return report


def load():
    report = json.loads(REPORT.read_text())
    if report["version"] != 1:
        raise ValueError("Unsupported advisory report version; scan again")
    if report["collector"] != lint.collector_hash():
        raise ValueError("Advisory collector changed; scan again")
    return report


def decisions():
    return [json.loads(line) for line in DECISIONS.read_text().splitlines()] if DECISIONS.exists() else []


def verify_fix(previous, item):
    report = collect(previous["base"], previous["harness"], previous["workflow"], previous.get("task_id"), previous.get("session_id"), previous["files"])
    added = lint.git("diff", "--no-ext-diff", "--no-color", previous["tree"], report["tree"])
    if previous["policy"] != report["policy"] or re.search(r"^\+.*(?:rubocop:\s*(?:disable|todo)|eslint-disable|jscpd:ignore)", added, re.MULTILINE):
        raise ValueError("Lint policy or suppressions changed; record a justified keep instead of a verified fix")
    if lint.exit_status(report) or any(f["id"] == item["id"] for f in report["findings"]):
        raise ValueError("Fresh scan did not verify the fix")
    previous_ids = {f["id"] for f in previous["findings"]}
    if any(f["affected"] and f["id"] not in previous_ids and
           (f["tool"], f["rule"], f["path"]) == (item["tool"], item["rule"], item["path"])
           for f in report["findings"]):
        raise ValueError("A replacement finding remains in the affected file; no verified fix recorded")
    if Path(item["path"]).exists() and report["tools"].get(item["tool"], {}).get("status") != "complete":
        raise ValueError("The relevant tool did not complete the verification scan")
    return report


def decide(identifier, outcome, reason):
    if not reason.strip():
        raise ValueError("A review reason is required")
    report = load()
    item = next((f for f in report["findings"] if f["id"] == identifier and f["affected"]), None)
    if item is None:
        raise ValueError("Finding is not in the current review scope")
    original_run = report["run_id"]
    if outcome == "fixed":
        report = verify_fix(report, item)
    elif report["tree"] != lint.fingerprint() or report["policy"] != lint.policy_hash():
        raise ValueError("Code or lint policy changed; scan again before reviewing")
    key = hashlib.sha256(json.dumps([identifier, report["tree"], report["collector"], outcome]).encode()).hexdigest()[:24]
    if any(d["review_id"] == key for d in decisions()):
        print("Decision already recorded")
        return
    decision = {"review_id": key, "finding_id": identifier, "outcome": outcome, "reason": reason,
                "tree": report["tree"], "policy": report["policy"], "collector": report["collector"],
                "run_id": report["run_id"], "flagged_run_id": original_run}
    with DECISIONS.open("a") as stream:
        stream.write(json.dumps(decision) + "\n")
    emit("quality_advisory_reviewed", report, review_id=key, finding_id=identifier, flagged_run_id=original_run,
         tool=item["tool"], rule=item["rule"], outcome=outcome, verified_fix=int(outcome == "fixed"))
    print(f"Recorded {outcome}: {identifier}")


def check():
    report = load()
    if report["tree"] != lint.fingerprint() or report["policy"] != lint.policy_hash():
        emit("quality_advisory_gate", report, gate_status="stale")
        raise ValueError("Advisory evidence is stale; scan again")
    if lint.exit_status(report):
        emit("quality_advisory_gate", report, gate_status="incomplete" if lint.exit_status(report) == 2 else "blocking")
        raise ValueError("Lint errors or incomplete scans remain")
    reviewed = {d["finding_id"] for d in decisions() if d["tree"] == report["tree"] and d["policy"] == report["policy"]
                and d.get("collector") == report["collector"]}
    missing = [f["id"] for f in report["findings"] if f["affected"] and f["id"] not in reviewed]
    emit("quality_advisory_gate", report, gate_status="unreviewed" if missing else "ready", unreviewed_count=len(missing))
    if missing:
        raise ValueError("Unreviewed advisories: " + ", ".join(missing))
    print("All affected lint advisories have a current decision")


def main():
    parser = argparse.ArgumentParser(description="Collect and review advisory findings without hiding them")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan")
    scan.add_argument("base")
    scan.add_argument("--harness", choices=["claude", "codex", "cursor", "opencode", "unknown"], required=True)
    scan.add_argument("--workflow", choices=["e2e", "ship", "verification"], default="e2e")
    scan.add_argument("--task-id", default=os.environ.get("E2E_TASK_ID"))
    scan.add_argument("--session-id", default=os.environ.get("E2E_SESSION_ID"))
    review = commands.add_parser("decide")
    review.add_argument("finding_id")
    review.add_argument("outcome", choices=["fixed", "kept", "dismissed"])
    review.add_argument("reason")
    commands.add_parser("check")
    args = parser.parse_args()
    os.chdir(lint.git("rev-parse", "--show-toplevel"))
    if args.command == "scan":
        report = collect(args.base, args.harness, args.workflow, args.task_id, args.session_id)
        print(".e2e/lint-advisories.md")
        return lint.exit_status(report)
    if args.command == "decide":
        decide(args.finding_id, args.outcome, args.reason)
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Advisory review incomplete: {error}", file=sys.stderr)
        raise SystemExit(2)
