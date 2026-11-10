"""Prepare extra sample commits; these remain course-generated data."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'labs/e8e10'))
from lab import commit


def main():
    original = ROOT / 'data/integration-sample'
    destination = ROOT / 'data/student-241880408'
    if destination.exists():
        raise SystemExit('Preserve existing extension data; do not prepare twice')
    destination.mkdir(parents=True)
    source = json.loads((original / 'e11-a.json').read_text())
    project = destination / 'repo'
    subprocess.run(['git', 'clone', '--no-hardlinks', str(original / 'repo'), str(project)], check=True)
    subprocess.run(['git', 'checkout', '--detach', source['target']], cwd=project, check=True)
    helper = project / 'helper.c'
    helper.write_text('int helper(void){return 0+0;}\n')
    body = commit(project, 'student 241880408: equivalent helper expression')
    body_request = dict(source, repo=str(project), base=source['target'], target=body)
    (destination / 'e11-a-body.json').write_text(json.dumps(body_request, indent=2) + '\n')
    (project / 'extra.h').write_text('#include "leaf.h"\n#define EXTRA 0\n')
    (project / 'leaf.h').write_text('#define LEAF 7\n')
    header = commit(project, 'student 241880408: indirect local header')
    header_request = dict(source, repo=str(project), base=body, target=header)
    (destination / 'e11-a-header.json').write_text(json.dumps(header_request, indent=2) + '\n')
    fixed = json.loads((original / 'fixed-md.json').read_text())
    fixed['commit'] = source['base']
    fixed['data']['commit'] = source['base']
    stale = destination / 'stale-fixed-md.json'
    stale.write_text(json.dumps(fixed, indent=2) + '\n')
    stale_request = json.loads((original / 'e11-b.json').read_text())
    stale_request['fixed_report'] = str(stale)
    (destination / 'stale-request.json').write_text(json.dumps(stale_request, indent=2) + '\n')
    (destination / 'dataset.json').write_text(json.dumps({
        'source': 'course-generated sample with student extension; not a real-project acceptance',
        'upstream_base': source['base'], 'upstream_target': source['target'],
        'body_commit': body, 'header_commit': header,
        'expectations': {
            'body': {'reused': ['main.o', 'helper.o'], 'refreshed': []},
            'header': {'reused': [], 'refreshed': ['main.o', 'helper.o'],
                       'added': [['MISSING', 'main.o', 'leaf.h']]},
            'stale': {'status': 'FAILED', 'error_code': 'STALE_REPORT',
                      'patch_created': False}},
        'real_project': {'status': 'PENDING_GROUP_INPUT'}}, indent=2) + '\n')
    print('STUDENT_EXTENSION_INPUTS_READY', body, header)


if __name__ == '__main__':
    main()
