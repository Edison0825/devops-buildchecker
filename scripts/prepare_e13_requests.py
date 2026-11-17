"""Generate E13 requests from the two latest commits of each fixture repo."""

import json
import subprocess
from pathlib import Path


CASES = ("H1-jsmn", "H2-inih", "H3-tiny-aes")


def main() -> None:
    root = Path("data/e13-upstream-student")
    for name in CASES:
        folder = root / name
        commits = subprocess.check_output(
            ["git", "-C", str(folder / "repo"), "rev-list", "--max-count=2", "HEAD"],
            text=True,
        ).splitlines()
        if len(commits) != 2:
            raise SystemExit(f"{name}: expected two commits, found {len(commits)}")
        target, base = commits
        request = {
            "mode": "e12",
            "repo": "/course/" + (folder / "repo").as_posix(),
            "base": base,
            "target": target,
            "candidate": "/course/" + (folder / "candidate.Dockerfile").as_posix(),
            "expected_output": "1",
            "build_timeout": 600,
        }
        output = folder / "request-e12.json"
        if output.exists():
            raise SystemExit(f"preserving existing request: {output}")
        output.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        print(name, "base=", base, "target=", target, "request=", output)


if __name__ == "__main__":
    main()
