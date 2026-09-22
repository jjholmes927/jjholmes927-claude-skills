import argparse
import os
from pathlib import Path
import shlex
import subprocess
from urllib.parse import urlsplit


def local_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("The discovered target is not a local development URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("The development URL must not contain credentials, a query or a fragment")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid development port")
    return value.rstrip("/")


def resolve(root):
    helper = root / "bin/dev-info"
    if helper.exists():
        if not os.access(helper, os.X_OK):
            raise ValueError("bin/dev-info exists but is not executable; resolve the project environment first")
        result = subprocess.run([str(helper)], cwd=root, capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError("bin/dev-info failed; resolve the project environment instead of guessing a port")
        values = [line.removeprefix("APP_URL=").strip() for line in result.stdout.splitlines() if line.startswith("APP_URL=")]
        if len(values) != 1:
            raise ValueError("bin/dev-info did not return one APP_URL; consult the project's runtime guide")
        return local_url(values[0])
    for name in (".env", ".env.local"):
        source = root / name
        if not source.is_file():
            continue
        values = {}
        for line in source.read_text().splitlines():
            key, separator, raw = line.strip().removeprefix("export ").partition("=")
            key = key.strip()
            if not separator or key not in {"PORT", "DEV_WEB_PORT", "SERVICE_URL"}:
                continue
            tokens = shlex.split(raw, comments=True)
            if len(tokens) != 1 or (key in values and values[key] != tokens[0]):
                raise ValueError(f"Ambiguous {key} in {name}; consult the project's runtime guide")
            values[key] = tokens[0]
        port = values.get("PORT", values.get("DEV_WEB_PORT"))
        if port is not None:
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                raise ValueError(f"Invalid local port in {name}; dynamic values require project-specific resolution")
            return f"http://localhost:{int(port)}"
        if values.get("SERVICE_URL"):
            return local_url(values["SERVICE_URL"])
    raise ValueError("No local target found; use the project's runtime guide or an explicit verified URL")


def main():
    parser = argparse.ArgumentParser(description="Resolve this checkout's local URL without sourcing environment files")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        print(resolve(args.root.resolve()))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
