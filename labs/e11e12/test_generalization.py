"""Generalization tests: explicit compile rules with project-chosen target names.

These tests cover the E11-E12 adaptation: scan/patch/validate used to assume
main.o/helper.o/app/config.h; they now derive the analyzed target set from the
Makefile's explicit compile rules, so an unchanged real C/Make project can be
plugged in. The teaching fixture must keep producing exactly main.o/helper.o.
"""
import tempfile
import unittest
from pathlib import Path

from lab import commit, compile_pairs, fixture, patch, run, scan, validate


class GeneralizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _project(self, makefile, sources):
        p = self.root / 'p'
        p.mkdir()
        for name, text in sources.items():
            (p / name).write_text(text)
        (p / 'Makefile').write_text(makefile)
        run(['git', 'init', '-b', 'main'], p)
        run(['git', 'config', 'user.name', 'GeneralizationTest'], p)
        run(['git', 'config', 'user.email', 'test@localhost'], p)
        commit(p, 'C0 test project')
        return p

    def test_fixture_pairs_unchanged(self):
        p = self.root / 'f'
        fixture(p)
        self.assertEqual(compile_pairs(p), [('main.o', 'main.c'), ('helper.o', 'helper.c')])

    def test_arbitrary_object_names(self):
        p = self._project(
            'CFLAGS = -O0\nprogram: core.o\n\tgcc core.o -o program\n'
            'core.o: core.c\n\tgcc $(CFLAGS) -c core.c -o core.o\n',
            {'core.c': '#include <stdio.h>\n#include "local.h"\nint main(void){printf("%d\\n",VALUE);return 0;}\n',
             'local.h': '#define VALUE 2\n'})
        report = scan(p)
        self.assertEqual(sorted(report['actual']), ['core.o'])
        self.assertEqual(report['actual']['core.o'], ['core.c', 'local.h'])
        self.assertEqual(report['declared']['core.o'], ['core.c'])
        self.assertIn(('MISSING', 'core.o', 'local.h'),
                      [(f['type'], f['target'], f['dependency']) for f in report['findings']])
        diff, _edits = patch(p, report)
        self.assertIn('core.o: core.c local.h', diff)

    def test_direct_link_rule_supported(self):
        p = self._project('prog: prog.c\n\tgcc prog.c -o prog\n',
                          {'prog.c': '#include <stdio.h>\nint main(void){printf("0\\n");return 0;}\n'})
        self.assertEqual(compile_pairs(p), [('prog', 'prog.c')])
        report = scan(p)
        self.assertEqual(list(report['actual']), ['prog'])
        self.assertEqual(report['actual']['prog'], ['prog.c'])

    def test_pattern_rule_still_unsupported(self):
        p = self._project('CFLAGS = -O0\n%.o: %.c\n\tgcc $(CFLAGS) -c $< -o $@\n',
                          {'a.c': 'int main(void){return 0;}\n'})
        with self.assertRaises(ValueError) as ctx:
            compile_pairs(p)
        self.assertIn('UNSUPPORTED_RULE', str(ctx.exception))

    def test_validate_supports_custom_project_shape(self):
        p = self._project(
            'CFLAGS = -O0\ntool: main.o\n\tgcc main.o -o tool\n'
            'main.o: main.c\n\tgcc $(CFLAGS) -c main.c -o main.o\n',
            {'main.c': '#include <stdio.h>\n#include "value.h"\nint main(void){printf("%d\\n",VALUE);return 0;}\n',
             'value.h': '#define VALUE 1\n'})
        report = scan(p)
        self.assertEqual([(f['type'], f['target'], f['dependency']) for f in report['findings']],
                         [('MISSING', 'main.o', 'value.h')])
        diff, _edits = patch(p, report)
        patchfile = self.root / 'candidate.patch'
        patchfile.write_text(diff)
        verdict = validate(p, patchfile, self.root / 'evidence', link_target='tool',
                           expected_output='1', header='value.h',
                           header_after='#define VALUE 2\n', header_expected='2')
        self.assertTrue(verdict['accepted'], verdict)
        self.assertEqual(set(verdict['checks']),
                         {'patch_applies', 'build', 'test', 'header_change', 'no_missing'})

    def test_validate_header_edits_apply_targeted_replacement(self):
        # Real headers are too large to overwrite wholesale; a targeted replacement
        # must still trigger the "header changed" rebuild assertion.
        p = self._project(
            'CFLAGS = -O0\ntool: main.o\n\tgcc main.o -o tool\n'
            'main.o: main.c\n\tgcc $(CFLAGS) -c main.c -o main.o\n',
            {'main.c': '#include <stdio.h>\n#include "value.h"\nint main(void){printf("%d\\n",VALUE);return 0;}\n',
             'value.h': '/* project header */\n#define OTHER 0\n#define VALUE 1\n'})
        report = scan(p)
        diff, _edits = patch(p, report)
        patchfile = self.root / 'candidate.patch'
        patchfile.write_text(diff)
        verdict = validate(p, patchfile, self.root / 'evidence2', link_target='tool',
                           expected_output='1', header='value.h',
                           header_edits=[['#define VALUE 1', '#define VALUE 2']],
                           header_expected='2')
        self.assertTrue(verdict['accepted'], verdict)
        self.assertIn('/* project header */', (p / 'value.h').read_text())


if __name__ == '__main__':
    unittest.main()
