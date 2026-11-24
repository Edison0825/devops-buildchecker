"""Regress parameter loss at the four-service HTTP boundary, independent of Docker."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import orchestrate


def service_module():
    lab = types.ModuleType('lab')
    lab.scan, lab.patch, lab.validate = Mock(), Mock(), Mock()
    draft = types.ModuleType('draft')
    autobuild = types.ModuleType('draft.autobuild')
    autobuild.auto_build = Mock()
    checker = types.ModuleType('buildchecker')
    fullcheck = types.ModuleType('buildchecker.fullcheck')
    fullcheck.full_check = Mock()
    modules = {'lab': lab, 'draft': draft, 'draft.autobuild': autobuild,
               'buildchecker': checker, 'buildchecker.fullcheck': fullcheck}
    spec = importlib.util.spec_from_file_location('profile_service_under_test', PACKAGE / 'service.py')
    module = importlib.util.module_from_spec(spec)
    old_path = sys.path[:]
    try:
        with patch.dict(sys.modules, modules), patch.dict(os.environ, E14_ROLE='buildchecker'):
            spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_path
    return module


class ProjectProfileTests(unittest.TestCase):
    def setUp(self):
        temp_root = PACKAGE.parents[1] / 'work' / 'e13e14-test-tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.service = service_module()
        self.service.ROOT = self.root
        self.project = self.root / 'work/project'
        self.project.mkdir(parents=True)
        self.data = {'project': str(self.project), 'out': str(self.root / 'work/result'),
                     'job_id': 'job-profile', 'trace_id': 'trace-profile', 'target_commit': 'a' * 40,
                     'build_command': 'make sds-test', 'clean_command': 'make clean',
                     'link_target': 'sds-test', 'expected_output': '46 passed', 'header': 'sds.h',
                     'header_expected': '46 passed', 'header_edits': [['OLD', 'NEW']]}

    def test_buildchecker_uses_actual_build_commands(self):
        self.service.full_check.return_value = {'status': 'SUCCEEDED'}
        self.service.run(self.data)
        self.assertEqual(self.service.full_check.call_args.kwargs,
                         {'build_command': 'make sds-test', 'clean_command': 'make clean'})

    def test_buildchecker_preserves_teaching_defaults(self):
        self.service.full_check.return_value = {'status': 'SUCCEEDED'}
        self.service.run({k: self.data[k] for k in ['project', 'out']})
        self.assertEqual(self.service.full_check.call_args.kwargs,
                         {'build_command': 'make app', 'clean_command': 'make clean'})

    def test_echecker_projects_actual_targets_and_compares_their_findings(self):
        self.service.ROLE = 'echecker'
        findings = [{'type': 'MISSING', 'target': 'sds-test', 'dependency': 'sdslog.h'}]
        self.service.scan.side_effect = [
            {'actual': {'sds-test': ['sds.c']}},
            {'actual': {'sds-test': ['sds.c', 'sdslog.h']}, 'commit': 'a' * 40, 'findings': findings},
        ]
        graph = self.root / 'work/graph.json'
        graph.write_text(json.dumps([{'target': 'sds-test', 'dependency': 'sds.c'}]))
        reference = self.root / 'work/findings.json'
        reference.write_text(json.dumps({'status': 'SUCCEEDED', 'findings': findings}))
        self.data.update(base=str(self.project), baseline_graph=str(graph), target_findings=str(reference))
        result = self.service.run(self.data)
        self.assertEqual(result['findings'], findings)
        self.assertEqual(self.service.scan.call_args.args[1]['actual'], {'sds-test': ['sds.c']})

    def test_echecker_does_not_hide_custom_target_mismatch(self):
        self.service.ROLE = 'echecker'
        self.service.scan.side_effect = [{'actual': {'sds-test': ['sds.c']}},
            {'actual': {'sds-test': ['sds.c']}, 'commit': 'a' * 40, 'findings': []}]
        graph = self.root / 'work/graph.json'
        graph.write_text(json.dumps([{'target': 'sds-test', 'dependency': 'sds.c'}]))
        reference = self.root / 'work/findings.json'
        reference.write_text(json.dumps({'status': 'SUCCEEDED', 'findings': [
            {'type': 'MISSING', 'target': 'sds-test', 'dependency': 'sdslog.h'}]}))
        self.data.update(base=str(self.project), baseline_graph=str(graph), target_findings=str(reference))
        with self.assertRaisesRegex(ValueError, 'Incremental/full findings mismatch'):
            self.service.run(self.data)

    def test_mdfixer_keeps_project_validation_assertions(self):
        self.service.ROLE = 'mdfixer'
        envelope = {'schema_version': 'e11e12-1', 'kind': 'incremental-check', 'status': 'SUCCEEDED',
                    'commit': 'a' * 40, 'job_id': self.data['job_id'], 'trace_id': self.data['trace_id'],
                    'data': {'findings': []}}
        report = self.root / 'work/report.json'
        report.write_text(json.dumps(envelope))
        self.data.update(report=str(report), report_sha256=self.service.sha(report))
        self.service.patch.return_value = ('test patch', [])
        self.service.validate.return_value = {'accepted': True}
        self.service.run(self.data)
        kwargs = self.service.validate.call_args.kwargs
        for key in ['link_target', 'expected_output', 'header', 'header_expected', 'header_edits']:
            self.assertEqual(kwargs[key], self.data[key])

    def test_snapshot_accepts_custom_c_source_and_make_target(self):
        repo = self.root / 'source'
        repo.mkdir()
        (repo / 'sds.c').write_text('int main(void) { return 0; }\n')
        (repo / 'Makefile').write_text('sds-test: sds.c\n\t$(CC) -o $@ $<\n')
        for args in [['init'], ['add', '.'], ['-c', 'user.name=241880408', '-c',
                'user.email=241880408@smail.nju.edu.cn', 'commit', '-m', 'local profile fixture']]:
            subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
        target = self.root / 'snapshot'
        self.assertEqual(orchestrate.snapshot(repo, sha, target, self.root / 'logs'), sha)
        self.assertTrue((target / 'sds.c').is_file())

    def test_orchestrator_forwards_options_to_each_role(self):
        out = self.root / 'work/orchestration'
        request = dict(self.data, repo='/course/data/real-project', candidate='/course/data/candidate',
                       base='b' * 40, target='a' * 40)
        calls = []

        def call(role, payload, evidence):
            calls.append((role, payload))
            return {'status': 'SUCCEEDED', 'report': '/course/work/report.json', 'sha256': 'c' * 64,
                    'result': {'findings': []}}

        with patch.object(orchestrate, 'ROOT', self.root), patch.object(orchestrate, 'call', side_effect=call), \
             patch.object(orchestrate, 'snapshot', side_effect=['b' * 40, 'a' * 40]):
            result = orchestrate.execute(request, out)
        self.assertEqual(result['status'], 'SUCCEEDED', result)
        self.assertEqual({role for role, _ in calls}, {'draft', 'buildchecker', 'echecker', 'mdfixer'})
        for _, payload in calls:
            for key in ['build_command', 'clean_command', 'link_target', 'header', 'header_edits']:
                self.assertEqual(payload[key], request[key])


if __name__ == '__main__':
    unittest.main()
