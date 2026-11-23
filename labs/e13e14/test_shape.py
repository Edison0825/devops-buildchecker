"""Regression tests for the two E13 defects (student 241880536).

D1: a repaired report transferred between A and B was accepted by path only.
D2: the incremental service projected link targets (`app`, `sds-test`) onto the
    object scan, raising `Baseline BuildChecker/GCC graph mismatch`.
"""
import tempfile
import unittest
from pathlib import Path

from shape import object_targets, verify_report_hash


class ReportTransferTests(unittest.TestCase):
    def test_unchanged_report_returns_its_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'fixed-md.json'
            report.write_text('{"kind": "fixed-md"}\n')
            digest = verify_report_hash(report, None)
            self.assertEqual(len(digest), 64)
            self.assertEqual(verify_report_hash(report, digest), digest)

    def test_report_changed_in_transit_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'fixed-md.json'
            report.write_text('{"kind": "fixed-md"}\n')
            digest = verify_report_hash(report, None)
            report.write_text('{"kind": "fixed-md", "extra": 1}\n')
            with self.assertRaises(ValueError) as caught:
                verify_report_hash(report, digest)
            self.assertIn('ARTIFACT_HASH_MISMATCH', str(caught.exception))


class ProjectionTests(unittest.TestCase):
    graph = [
        {'target': 'app', 'dependency': 'main.o'},
        {'target': 'app', 'dependency': 'helper.o'},
        {'target': 'main.o', 'dependency': 'main.c'},
        {'target': 'main.o', 'dependency': 'config.h'},
        {'target': 'helper.o', 'dependency': 'helper.c'},
    ]

    def test_link_target_is_not_treated_as_an_object(self):
        actual = {'main.o': ['config.h', 'main.c'], 'helper.o': ['helper.c']}
        self.assertEqual(object_targets(actual, self.graph), ['helper.o', 'main.o'])

    def test_real_project_shaped_graph_keeps_its_single_object(self):
        graph = [{'target': 'sds-test', 'dependency': 'sds.c'},
                 {'target': 'sds-test', 'dependency': 'sds.h'}]
        self.assertEqual(object_targets({'sds-test': ['sds.c', 'sds.h']}, graph), ['sds-test'])

    def test_graph_without_object_overlap_is_rejected(self):
        graph = [{'target': 'app', 'dependency': 'main.o'}]
        with self.assertRaises(ValueError) as caught:
            object_targets({'main.o': ['main.c']}, graph)
        self.assertIn('no matching object targets', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
