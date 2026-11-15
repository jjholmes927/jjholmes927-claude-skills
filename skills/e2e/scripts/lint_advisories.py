#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from urllib.parse import urlsplit


def git(*args, **kwargs):
    return subprocess.check_output(["git", *args], text=True, **kwargs).strip()


def fingerprint():
    with tempfile.TemporaryDirectory() as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        git("read-tree", "HEAD", env=env)
        git("add", "-A", ".", env=env)
        return git("write-tree", env=env)


def collector_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def repository():
    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    value = remote.stdout.strip()
    if "://" in value:
        parsed = urlsplit(value)
        return ((parsed.hostname or "local") + parsed.path).removesuffix(".git")
    if re.match(r"[^/]+@[^:]+:", value):
        return value.split("@", 1)[1].replace(":", "/", 1).removesuffix(".git")
    return "local/" + Path.cwd().name


def policy_hash():
    paths = {"Gemfile", "Gemfile.lock", "package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock",
             "eslint-suppressions.json", ".jscpd.json", ".gitignore", ".eslintignore"}
    paths.update(p for p in git("ls-files", "-co", "--exclude-standard", "-z").split("\0")
                 if re.match(r"(?:.*/)?(?:\.rubocop.*\.yml|eslint\.config\..*|\.eslintrc.*)$", p))
    return hashlib.sha256(b"".join(p.encode() + Path(p).read_bytes() for p in sorted(paths) if Path(p).is_file())).hexdigest()


def changed(base):
    files = git("diff", "--name-only", "--diff-filter=ACMRT", "-z", base).split("\0")
    files += git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    ranges = {}
    for path in files:
        if not path or not Path(path).is_file():
            continue
        for line in git("diff", "--no-ext-diff", "--no-color", "-U0", base, "--", path).splitlines():
            match = re.match(r"@@ .* \+(\d+)(?:,(\d+))? @@", line)
            if match:
                start, count = int(match[1]), int(match[2] or 1)
                ranges.setdefault(path, []).append((max(start, 1), max(start + count - 1, start, 1)))
        if path and Path(path).is_file() and path not in ranges:
            ranges[path] = [(1, len(Path(path).read_text(errors="replace").splitlines()) or 1)]
    return sorted({p for p in files if p and Path(p).is_file()}), ranges


def finding(repo, tool, rule, path, start, end, severity, message, ranges):
    path = str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    lines = Path(path).read_text(errors="replace").splitlines()
    if tool == "eslint" and rule == "max-lines":
        start, end = 1, max(len(lines), 1)
    anchor = lines[start - 1].strip() if 0 < start <= len(lines) else "file"
    occurrence = sum(line.strip() == anchor for line in lines[:start])
    key = json.dumps([repo, tool, rule, path, anchor, occurrence])
    return {"id": hashlib.sha256(key.encode()).hexdigest()[:24], "tool": tool, "rule": rule,
            "path": path, "start": start, "end": end, "severity": severity, "message": message,
            "affected": any(left <= end and right >= start for left, right in ranges.get(path, []))}


def invoke(tool, command, report_path, parse, report):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode not in (0, 1):
            raise ValueError(f"command exited {result.returncode}")
        data = json.loads(report_path.read_text())
        items = parse(data)
        report["tools"][tool] = {"status": "complete", "exit": result.returncode}
        report["findings"].extend(items)
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.TimeoutExpired) as error:
        report["tools"][tool] = {"status": "incomplete", "error": f"{type(error).__name__}: {error}"}


def scan(base, harness, extra=()):
    root = Path(git("rev-parse", "--show-toplevel"))
    os.chdir(root)
    output = root / ".e2e"
    output.mkdir(exist_ok=True)
    exclude = Path(git("rev-parse", "--git-path", "info/exclude"))
    text = exclude.read_text() if exclude.exists() else ""
    if ".e2e/" not in text.splitlines():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(text + "\n.e2e/\n")
    base = git("merge-base", base, "HEAD")
    files, ranges = changed(base)
    files = sorted(set(files) | {p for p in extra if Path(p).is_file()})
    report = {"version": 1, "collector": collector_hash(), "run_id": str(uuid.uuid4()), "repo": repository(), "base": base,
              "head": git("rev-parse", "HEAD"), "tree": fingerprint(), "policy": policy_hash(),
              "harness": harness, "tools": {}, "files": files, "findings": []}
    ruby = [p for p in files if Path(p).suffix in {".rb", ".rake"}]
    javascript = [p for p in files if Path(p).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}]
    package = json.loads(Path("package.json").read_text()) if Path("package.json").exists() else {}
    runner = ["pnpm", "exec"] if Path("pnpm-lock.yaml").exists() else ["yarn", "exec"] if Path("yarn.lock").exists() else ["npm", "exec", "--no", "--"]
    def item(tool, rule, path, start, end, severity, message):
        return finding(report["repo"], tool, rule, path, int(start), int(end), severity, message, ranges)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        if ruby and Path(".rubocop.yml").exists():
            def rubocop(data):
                return [item("rubocop", offense["cop_name"], file["path"], offense["location"]["start_line"],
                             offense["location"]["last_line"], offense["severity"], offense["message"])
                        for file in data["files"] for offense in file["offenses"]]
            invoke("rubocop", ["bundle", "exec", "rubocop", "--no-server", "--format", "json", "--out", str(target / "ruby.json"), *ruby], target / "ruby.json", rubocop, report)
        if javascript and (list(Path(".").glob("eslint.config.*")) or list(Path(".").glob(".eslintrc*")) or "eslintConfig" in package):
            def eslint(data):
                if any(message.get("fatal") and not message.get("line") for file in data for message in file["messages"]):
                    raise ValueError("ESLint failed without a source range")
                return [item("eslint", message.get("ruleId") or "parse-error", file["filePath"], message["line"],
                             message.get("endLine") or message["line"], "warning" if message["severity"] == 1 else "error", message["message"])
                        for file in data for message in file["messages"] if message["severity"] > 0 and message.get("line")]
            invoke("eslint", [*runner, "eslint", "--format", "json", "--output-file", str(target / "js.json"), *javascript], target / "js.json", eslint, report)
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if (ruby or javascript) and (Path(".jscpd.json").exists() or "jscpd" in dependencies):
            def clones(data):
                items = []
                for clone in data["duplicates"]:
                    sides = [clone["firstFile"], clone["secondFile"]]
                    pair = sorted(side["name"] for side in sides)
                    values = []
                    for side in sides:
                        message = "Duplicate between " + " and ".join(pair)
                        value = item("jscpd", "duplication", side["name"], side["start"], side["end"], "advisory", message)
                        values.append(value)
                    value = next((v for v in values if v["affected"]), None)
                    if value:
                        key = json.dumps([report["repo"], "jscpd", sorted(v["id"] for v in values)])
                        value.update(id=hashlib.sha256(key.encode()).hexdigest()[:24], related=sides)
                        items.append(value)
                return items
            invoke("jscpd", [*runner, "jscpd", "--reporters", "json", "--output", str(target)], target / "jscpd-report.json", clones, report)
    report["findings"] = list({value["id"]: value for value in report["findings"]}.values())
    report["tree_after"] = fingerprint()
    if report["tree_after"] != report["tree"]:
        report["tools"]["worktree"] = {"status": "incomplete", "error": "Files changed during the scan"}
    (output / "lint-advisories.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Lint advisories", "", f"Run `{report['run_id']}` · tree `{report['tree']}`", ""]
    lines += [f"- {tool}: {state['status']}" for tool, state in report["tools"].items()]
    lines += [f"- `{value['id']}` {value['tool']}/{value['rule']} `{value['path']}:{value['start']}-{value['end']}`: {value['message']}" for value in report["findings"] if value["affected"]]
    (output / "lint-advisories.md").write_text("\n".join(lines) + "\n")
    return report


def exit_status(report):
    if any(state["status"] != "complete" for state in report["tools"].values()):
        return 2
    return int(any(state.get("exit") == 1 for tool, state in report["tools"].items() if tool != "jscpd"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect configured lint findings for changed code")
    parser.add_argument("base")
    parser.add_argument("--harness", choices=["claude", "codex", "cursor", "opencode", "unknown"], default="unknown")
    args = parser.parse_args()
    result = scan(args.base, args.harness)
    print(".e2e/lint-advisories.md")
    raise SystemExit(exit_status(result))
