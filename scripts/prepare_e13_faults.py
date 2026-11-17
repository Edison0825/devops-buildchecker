"""Prepare isolated E13 timeout and failure-isolation requests."""

import json
from pathlib import Path


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"preserving existing request: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    sample = Path("data/integration-sample")
    timeout = json.loads((sample / "e11-b.json").read_text(encoding="utf-8"))
    timeout["build_timeout"] = 0.01
    write_new(Path("data/e13-timeout-request.json"), timeout)

    failed = json.loads((sample / "e11-a.json").read_text(encoding="utf-8"))
    failed["base"] = "0" * 40
    write_new(Path("data/e13-c7-failed-request.json"), failed)


if __name__ == "__main__":
    main()
