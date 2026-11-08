import json, tempfile, unittest
from pathlib import Path
from lab import fixture,scan,patch,commit

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def test_independent_known_edges(self):
        r=scan(self.p)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in r['findings']},{('MISSING','config.h'),('REDUNDANT','unused.h')})

    def test_unchanged_reuses_both_targets(self):
        r=scan(self.p,scan(self.p));self.assertEqual(r['reused'],['main.o','helper.o']);self.assertEqual(r['refreshed'],[])

    def test_include_added_invalidates_cache(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "extra.h"\n'+(self.p/'main.c').read_text());commit(self.p,'new include')
        r=scan(self.p,old)
        self.assertIn(['MISSING','main.o','extra.h'],r['added']);self.assertEqual(len(r['refreshed']),2)

    def test_patch_preserves_redundant_dependency(self):
        r=scan(self.p);diff,plan=patch(self.p,r)
        self.assertIn('+main.o: main.c unused.h config.h',diff)
        self.assertNotIn('-\tgcc',diff)
        self.assertNotIn('config.h',(self.p/'Makefile').read_text())

    def test_old_report_rejected(self):
        r=scan(self.p);r['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'STALE_REPORT'):patch(self.p,r)

    def test_unsafe_dependency_rejected(self):
        r=scan(self.p);r['findings']=[{'type':'MISSING','target':'main.o','dependency':'../outside.h'}]
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):patch(self.p,r)

    def test_unsupported_configuration_rejected(self):
        (self.p/'Makefile').write_text((self.p/'Makefile').read_text().replace('-O0','-include unknown.h'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FLAGS'):scan(self.p)

    def test_nested_include_invalidates_whole_graph(self):
        # 间接头文件：main.c -> config.h -> nested.h；直接文件 main.c 未改，旧图仍必须失效
        old=scan(self.p)
        (self.p/'nested.h').write_text('#define NESTED 1\n')
        (self.p/'config.h').write_text('#include "nested.h"\n'+(self.p/'config.h').read_text());commit(self.p,'nested include')
        r=scan(self.p,old)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c','nested.h'])
        self.assertEqual(r['refreshed'],['main.o','helper.o'])
        self.assertEqual(r['reused'],[])
        self.assertIn(['MISSING','main.o','nested.h'],r['added'])
        self.assertEqual(len(r['findings']),3)

class Student241880408E8(unittest.TestCase):
    def test_indirect_header_adds_independently_expected_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            old = scan(project)
            (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
            commit(project, 'student 241880408: indirect include')
            full = scan(project)
            self.assertEqual(full['actual'], {
                'main.o': ['config.h', 'extra.h', 'main.c'],
                'helper.o': ['helper.c'],
            })
            self.assertEqual(
                {(f['type'], f['target'], f['dependency']) for f in full['findings']},
                {('MISSING', 'main.o', 'config.h'),
                 ('MISSING', 'main.o', 'extra.h'),
                 ('REDUNDANT', 'main.o', 'unused.h')})
            incremental = scan(project, old)
            for key in ['actual', 'declared', 'findings']:
                self.assertEqual(incremental[key], full[key])
            self.assertEqual(incremental['reused'], [])
            self.assertEqual(set(incremental['refreshed']), {'main.o', 'helper.o'})

    def test_declaration_only_change_resolves_both_kinds(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            old = scan(project)
            makefile = project / 'Makefile'
            makefile.write_text(makefile.read_text().replace('main.c unused.h', 'main.c config.h'))
            commit(project, 'student 241880408: fix MD and remove RD')
            result = scan(project, old)
            self.assertEqual(result['actual'], old['actual'])
            self.assertEqual(result['findings'], [])
            self.assertEqual(result['added'], [])
            self.assertEqual(result['resolved'], [
                ['MISSING', 'main.o', 'config.h'],
                ['REDUNDANT', 'main.o', 'unused.h'],
            ])
            self.assertEqual(result['reused'], ['main.o', 'helper.o'])
            self.assertEqual(result['refreshed'], [])


class Student241880408E9(unittest.TestCase):
    def test_removing_indirect_include_resolves_only_removed_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
            commit(project, 'student 241880408: header reads extra')
            old = scan(project)
            (project / 'config.h').write_text('#define VALUE 1\n')
            commit(project, 'student 241880408: remove indirect include')
            result = scan(project, old)
            self.assertEqual(result['actual']['main.o'], ['config.h', 'main.c'])
            self.assertEqual(result['resolved'], [['MISSING', 'main.o', 'extra.h']])
            self.assertEqual(result['added'], [])
            self.assertEqual(result['reused'], [])
            self.assertEqual(set(result['refreshed']), {'main.o', 'helper.o'})
            self.assertEqual(
                {(f['type'], f['target'], f['dependency']) for f in result['findings']},
                {('MISSING', 'main.o', 'config.h'), ('REDUNDANT', 'main.o', 'unused.h')})
            full = scan(project)
            for key in ['actual', 'declared', 'findings']:
                self.assertEqual(result[key], full[key])


class Student241880408E10(unittest.TestCase):
    def test_deep_include_chain_matches_literal_graph_and_full_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            old = scan(project)
            (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
            (project / 'extra.h').write_text('#include "leaf.h"\n')
            (project / 'leaf.h').write_text('#include "tip.h"\n')
            (project / 'tip.h').write_text('#define TIP 7\n')
            commit(project, 'student 241880408: deep include chain')
            incremental = scan(project, old)
            full = scan(project)
            self.assertEqual(incremental['actual'], {
                'main.o': ['config.h', 'extra.h', 'leaf.h', 'main.c', 'tip.h'],
                'helper.o': ['helper.c'],
            })
            self.assertEqual(
                {(f['type'], f['target'], f['dependency']) for f in incremental['findings']},
                {('MISSING', 'main.o', 'config.h'), ('MISSING', 'main.o', 'extra.h'),
                 ('MISSING', 'main.o', 'leaf.h'), ('MISSING', 'main.o', 'tip.h'),
                 ('REDUNDANT', 'main.o', 'unused.h')})
            for key in ['actual', 'declared', 'findings']:
                self.assertEqual(incremental[key], full[key])
            self.assertEqual(incremental['reused'], [])
            self.assertEqual(set(incremental['refreshed']), {'main.o', 'helper.o'})


if __name__=='__main__':unittest.main()
