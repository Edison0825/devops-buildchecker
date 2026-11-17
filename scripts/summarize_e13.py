"""Print compact summaries for the three E13 project runs."""

import json
from pathlib import Path


for name in ("H1-jsmn", "H2-inih", "H3-tiny-aes"):
    path = Path("work") / f"e13-{name}-01" / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    print(
        name,
        json.dumps(
            {
                key: result.get(key)
                for key in ("status", "job_id", "trace_id", "target_commit", "error")
            },
            ensure_ascii=False,
        ),
    )
    print("stages=", [stage.get("name") for stage in result.get("stages", [])])


for name in ("e13-c4-01", "e13-c7-failed", "e13-c7-success"):
    path = Path("work") / name / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    print(
        name,
        json.dumps(
            {
                key: result.get(key)
                for key in ("status", "job_id", "trace_id", "error")
            },
            ensure_ascii=False,
        ),
    )
    if name == "e13-c4-01":
        draft = json.loads((path.parent / "draft-build/result.json").read_text(encoding="utf-8"))
        print("draft=", json.dumps({key: draft.get(key) for key in ("status", "error")}, ensure_ascii=False))
