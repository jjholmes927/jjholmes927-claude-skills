import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import plugin_eval
import run


CACHE = Path(os.environ.get("SKILL_EVAL_CACHE", Path.home() / ".cache" / "skill-evals"))
DROP = 2


def skill_dirs(case):
    return {f"skills/{name}/" for name in plugin_eval.skills(case)}


def covering(cases, changed):
    return [c for c in cases if c["kind"] in plugin_eval.KINDS
            and any(path.startswith(d) for d in skill_dirs(c) for path in changed)]


def cache_key(case, root, model, runs):
    digest = hashlib.sha256()
    digest.update(json.dumps({"spec": plugin_eval.spec(case), "files": plugin_eval.files(case),
                              "model": model, "runs": runs}, sort_keys=True).encode())
    for folder in sorted(skill_dirs(case)):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def parse(report):
    counts = {}
    for case in report["cases"]:
        runs = case["arms"]["with"]
        if runs and not any(r.get("error") for r in runs):
            counts[case["name"]] = {"passed": sum(bool(r["passed"]) for r in runs), "runs": len(runs)}
    return counts


def run_version(root, cases, model, runs, concurrency):
    plugin_eval.write(cases, root / "evals" / "claude")
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run(plugin_eval.eval_command(root, model, runs, "none", concurrency, report, no_publish=True))
        return parse(json.loads(report.read_text())) if report.exists() else {}


def scores(cases, root, model, runs, concurrency, cache):
    keys = {c["id"]: cache_key(c, root, model, runs) for c in cases}
    found = {}
    for case_id, key in keys.items():
        path = cache / f"{key}.json"
        if path.exists():
            found[case_id] = json.loads(path.read_text())
    missing = [c for c in cases if c["id"] not in found]
    if missing:
        cache.mkdir(parents=True, exist_ok=True)
        for case_id, result in run_version(root, missing, model, runs, concurrency).items():
            (cache / f"{keys[case_id]}.json").write_text(json.dumps(result))
            found[case_id] = result
    return found


def compare(cases, base, head, model, runs, concurrency, cache):
    before = scores(cases, base, model, runs, concurrency, cache)
    after = scores(cases, head, model, runs, concurrency, cache)
    rows = []
    for case in cases:
        old, new = before.get(case["id"]), after.get(case["id"])
        rows.append({"case": case["id"], "before": old and old["passed"], "after": new and new["passed"],
                     "runs": runs, "drop": bool(old and new and old["passed"] - new["passed"] >= DROP)})
    return rows


def table(rows):
    cell = lambda value, runs: "error" if value is None else f"{value}/{runs}"
    lines = ["| Case | Before | After | |", "|---|---|---|---|"]
    lines += [f'| {r["case"]} | {cell(r["before"], r["runs"])} | {cell(r["after"], r["runs"])} | '
              f'{"drop" if r["drop"] else ""} |' for r in rows]
    drops = sum(r["drop"] for r in rows)
    errors = sum(r["before"] is None or r["after"] is None for r in rows)
    lines.append("")
    lines.append(f"{drops} drop{'s' if drops != 1 else ''} (a case losing {DROP} or more runs)"
                 + (f", {errors} case{'s' if errors != 1 else ''} without a score" if errors else "") + ".")
    return "\n".join(lines)


def changed_files(base, root):
    output = subprocess.check_output(["git", "-C", str(root), "diff", "--name-only", f"{base}...HEAD"], text=True)
    dirty = subprocess.check_output(["git", "-C", str(root), "diff", "--name-only", "HEAD"], text=True)
    return set((output + dirty).split())


@contextlib.contextmanager
def base_checkout(base, root):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "base"
        subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", "--detach", str(path), base], check=True)
        try:
            yield path
        finally:
            subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(path)], check=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare skill eval scores on Claude between a base ref and this checkout.")
    parser.add_argument("base")
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args(argv)
    cases = covering(run.CASES, changed_files(args.base, run.ROOT))
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
    if not cases:
        print("No case covers a changed skill.")
        return 0
    print(f"Comparing {len(cases)} cases on {args.model}, {args.runs} runs each.", flush=True)
    with base_checkout(args.base, run.ROOT) as base:
        rows = compare(cases, base, run.ROOT, args.model, args.runs, args.concurrency, CACHE)
    print(table(rows))
    return 1 if any(r["drop"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
