"""Small helpers shared by the E14 services and unit tests (student 241880536).

Two defects found while running E13 are isolated here so they can be tested
without starting the four containers:

1. A repaired report handed from A to B was trusted by path only, so bytes
   changed in transit were still accepted. `verify_report_hash` makes the
   transfer hash mandatory when the caller supplies one.
2. The incremental service projected every target of the BuildChecker graph,
   including link targets such as `app`/`sds-test`, onto the GCC scan and then
   compared the two maps. On the teaching fixture that raised
   `Baseline BuildChecker/GCC graph mismatch`; `object_targets` keeps only the
   object targets the scan actually produced.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def verify_report_hash(path, expected):
    """Return the sha256 of `path`, rejecting a report whose bytes changed."""
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if expected and actual != expected:
        raise ValueError('ARTIFACT_HASH_MISMATCH: fixed report changed during transfer')
    return actual


def object_targets(actual_targets, graph):
    """Object targets present in both the GCC scan and the BuildChecker graph."""
    graph_targets = {edge['target'] for edge in graph}
    targets = [name for name in sorted(actual_targets) if name in graph_targets]
    if not targets:
        raise ValueError('Baseline graph has no matching object targets')
    return targets
