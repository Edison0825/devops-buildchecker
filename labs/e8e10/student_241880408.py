"""Reproducible A-track extensions assisted by AI; see the student's AI_USAGE.md."""
import csv
from pathlib import Path
from statistics import median

from lab import buildchecker, commit, fixture, save, scan


def finding_set(report):
    return {(item['type'], item['target'], item['dependency']) for item in report['findings']}


def run_extension(stage, out):
    out = Path(out)
    project = out / 'project'
    fixture(project)
    previous = scan(project)
    save(out / 'baseline.json', previous)

    if stage == 'e8':
        (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        commit(project, 'student 241880408 E8: indirect include')
        incremental = scan(project, previous)
        full = scan(project)
        assert full['actual'] == {
            'main.o': ['config.h', 'extra.h', 'main.c'], 'helper.o': ['helper.c']}
        assert finding_set(full) == {
            ('MISSING', 'main.o', 'config.h'), ('MISSING', 'main.o', 'extra.h'),
            ('REDUNDANT', 'main.o', 'unused.h')}
        assert incremental['reused'] == []
        assert set(incremental['refreshed']) == {'main.o', 'helper.o'}
        for key in ['actual', 'declared', 'findings']:
            assert incremental[key] == full[key], key
        save(out / 'incremental.json', incremental)
        save(out / 'full.json', full)
        buildchecker(project, out / 'buildchecker')
        save(out / 'gate.json', {'stage': stage, 'passed': True, 'independent_edges': True})
        print('STUDENT_E8_INDIRECT_INCLUDE_PASS', full['actual'])

    elif stage == 'e9':
        (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        commit(project, 'student 241880408 E9: add indirect include')
        before = scan(project, previous)
        save(out / 'before-removal.json', before)
        (project / 'config.h').write_text('#define VALUE 1\n')
        commit(project, 'student 241880408 E9: remove indirect include')
        after = scan(project, before)
        full = scan(project)
        assert after['actual'] == {
            'main.o': ['config.h', 'main.c'], 'helper.o': ['helper.c']}
        assert after['resolved'] == [['MISSING', 'main.o', 'extra.h']]
        assert after['added'] == []
        assert after['reused'] == []
        assert set(after['refreshed']) == {'main.o', 'helper.o'}
        assert finding_set(after) == {
            ('MISSING', 'main.o', 'config.h'), ('REDUNDANT', 'main.o', 'unused.h')}
        for key in ['actual', 'declared', 'findings']:
            assert after[key] == full[key], key
        save(out / 'after-removal.json', after)
        save(out / 'full.json', full)
        save(out / 'gate.json', {'stage': stage, 'passed': True, 'resolved': after['resolved']})
        print('STUDENT_E9_INCLUDE_REMOVAL_PASS', after['resolved'])

    elif stage == 'e10':
        (project / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        (project / 'extra.h').write_text('#include "leaf.h"\n')
        (project / 'leaf.h').write_text('#include "tip.h"\n')
        (project / 'tip.h').write_text('#define TIP 7\n')
        commit(project, 'student 241880408 E10: deep include chain')
        rows = []
        for repeat in range(1, 6):
            incremental = scan(project, previous)
            full = scan(project)
            assert incremental['actual'] == {
                'main.o': ['config.h', 'extra.h', 'leaf.h', 'main.c', 'tip.h'],
                'helper.o': ['helper.c']}
            assert finding_set(incremental) == {
                ('MISSING', 'main.o', 'config.h'), ('MISSING', 'main.o', 'extra.h'),
                ('MISSING', 'main.o', 'leaf.h'), ('MISSING', 'main.o', 'tip.h'),
                ('REDUNDANT', 'main.o', 'unused.h')}
            assert incremental['reused'] == []
            assert set(incremental['refreshed']) == {'main.o', 'helper.o'}
            equal = all(incremental[key] == full[key] for key in ['actual', 'declared', 'findings'])
            assert equal
            save(out / f'deep-chain-r{repeat}-incremental.json', incremental)
            save(out / f'deep-chain-r{repeat}-full.json', full)
            rows.append({'case': 'deep-chain', 'repeat': repeat, 'equal': equal,
                         'incremental_s': incremental['elapsed_s'], 'full_s': full['elapsed_s'],
                         'reused': len(incremental['reused']), 'refreshed': len(incremental['refreshed'])})
        with (out / 'results.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        inc = [row['incremental_s'] for row in rows]
        full_times = [row['full_s'] for row in rows]
        summary = {'case': 'deep-chain', 'n': 5, 'inc_median_s': median(inc),
                   'full_median_s': median(full_times), 'inc_min_s': min(inc), 'inc_max_s': max(inc),
                   'full_min_s': min(full_times), 'full_max_s': max(full_times),
                   'full_over_inc': median(full_times) / median(inc)}
        with (out / 'performance-summary.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary))
            writer.writeheader()
            writer.writerow(summary)
        buildchecker(project, out / 'buildchecker')
        save(out / 'gate.json', {'stage': stage, 'passed': True, 'rows': len(rows), 'independent_edges': True})
        print('STUDENT_E10_FIVE_REPEATS_PASS', summary)
    else:
        raise ValueError('Unsupported extension stage: ' + stage)
