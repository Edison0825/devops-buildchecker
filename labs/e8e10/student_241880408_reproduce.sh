#!/usr/bin/env bash
# Reproduce the student's extensions without altering the reference-run pointers.
set -e
E8_PACK="$HOME/devops-materials/DevOps_E8_E10/03_实验包"
source "$E8_PACK/classroom_helpers.sh"
lab_ready
for STAGE in e8 e9 e10; do
  POINTER="work/last-$STAGE-A.path"
  SAVED_POINTER=$(cat "$POINTER" 2>/dev/null || true)
  lab_new_run "$STAGE" A
  printf '%s\n' "$OUT" > "work/last-$STAGE-A-extension.path"
  if [ -n "$SAVED_POINTER" ]; then
    printf '%s\n' "$SAVED_POINTER" > "$POINTER"
  fi
  lab_python "$OUT" "$STAGE" <<'PY'
from pathlib import Path
import sys
from student_241880408 import run_extension
run_extension(sys.argv[2], Path(sys.argv[1]))
PY
done
