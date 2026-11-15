"""Student 241880267: incremental reuse/refresh policy and stale-report contract.

E11-A autonomous task: explain which targets are refreshed and which are reused.
scan() keys its cache on every local preprocessor line, the source set, the recipes
and the flags, so the answer depends on what the commit touched:
  - function-body-only edit      -> every target is reused
  - added/removed '#' directive  -> every target is refreshed (conservative)
A report belongs to exactly one commit; patching a newer commit with it is STALE_REPORT.
"""
import tempfile
import unittest
from pathlib import Path

from lab import commit, fixture, patch, scan


class IncrementalPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / 'f'
        fixture(self.p)
        self.base = scan(self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_body_only_change_reuses_all_targets(self):
        (self.p / 'helper.c').write_text('int helper(void){return 1;}\n')
        commit(self.p, 'C1 helper body only')
        report = scan(self.p, self.base)
        self.assertEqual(report['refreshed'], [])
        self.assertEqual(sorted(report['reused']), ['helper.o', 'main.o'])
        self.assertNotEqual(report['commit'], self.base['commit'])

    def test_new_directive_refreshes_all_targets(self):
        main = self.p / 'main.c'
        main.write_text('#include "extra.h"\n' + main.read_text())
        commit(self.p, 'C1 main.c adds include')
        report = scan(self.p, self.base)
        self.assertEqual(report['reused'], [])
        self.assertEqual(sorted(report['refreshed']), ['helper.o', 'main.o'])
        self.assertIn(['MISSING', 'main.o', 'extra.h'], report['added'])

    def test_old_report_cannot_patch_newer_commit(self):
        (self.p / 'helper.c').write_text('int helper(void){return 1;}\n')
        commit(self.p, 'C1 helper body only')
        with self.assertRaises(ValueError) as ctx:
            patch(self.p, self.base)
        self.assertIn('STALE_REPORT', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
