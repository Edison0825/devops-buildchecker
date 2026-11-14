"""Independent contracts for the documented restart and version checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pipeline
import server


class Student241880408Contracts(unittest.TestCase):
    def request(self):
        return {'mode': 'e11-a', 'repo': str(pipeline.ROOT / 'data/sample'),
                'base': 'a' * 40, 'target': 'b' * 40}

    def state(self, status, key='student-restart'):
        request = self.request()
        return {'schema_version': 'e11e12-1', 'job_id': 'job-student241880408',
                'status': status, 'idempotency_key': key,
                'request_hash': hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()}

    def test_restart_marks_running_failed_and_preserves_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.state('RUNNING')
            pipeline.save(root / state['job_id'] / 'state.json', state)
            store = server.Store(root)
            self.addCleanup(store.pool.shutdown)
            recovered = store.jobs[state['job_id']]
            self.assertEqual(recovered['status'], 'FAILED')
            self.assertEqual(recovered['error']['code'], 'SERVER_RESTARTED')
            with patch.object(store.pool, 'submit') as schedule:
                duplicate = store.submit(self.request(), state['idempotency_key'])
                self.assertEqual(duplicate['job_id'], state['job_id'])
                self.assertEqual(duplicate['status'], 'FAILED')
                schedule.assert_not_called()
            persisted = json.loads((root / state['job_id'] / 'state.json').read_text())
            self.assertEqual(persisted, recovered)

    def test_restart_keeps_completed_task_and_existing_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = dict(self.state('SUCCEEDED'), trace_id='trace-student241880408')
            pipeline.save(root / state['job_id'] / 'state.json', state)
            evidence = root / state['job_id'] / 'evidence' / 'candidate.patch'
            evidence.parent.mkdir()
            evidence.write_bytes(b'preserved patch\n')
            store = server.Store(root)
            self.addCleanup(store.pool.shutdown)
            self.assertEqual(store.jobs[state['job_id']], state)
            self.assertEqual(evidence.read_bytes(), b'preserved patch\n')
            with patch.object(store.pool, 'submit') as schedule:
                self.assertEqual(store.submit(self.request(), state['idempotency_key']), state)
                schedule.assert_not_called()

    def test_worker_exception_is_persisted_and_new_key_allows_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = server.Store(root)
            self.addCleanup(store.pool.shutdown)
            with patch.object(store.pool, 'submit'):
                first = store.submit(self.request(), 'failing')
            with patch.object(server, 'execute', side_effect=RuntimeError('controlled failure')):
                store.work(first['job_id'], self.request())
            persisted = json.loads((root / first['job_id'] / 'state.json').read_text())
            self.assertEqual(persisted['status'], 'FAILED')
            self.assertEqual(persisted['error']['code'], 'WORKER_FAILED')
            with patch.object(store.pool, 'submit') as schedule:
                retry = store.submit(self.request(), 'retry-new-key')
                self.assertNotEqual(retry['job_id'], first['job_id'])
                self.assertEqual(retry['status'], 'QUEUED')
                schedule.assert_called_once()

    def test_changed_artifact_keeps_original_and_reports_hash_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.json'
            report.write_text('{"commit": "original"}\n')
            reference = pipeline.artifact(report, root, 'job-original')
            report.write_text('{"commit": "changed"}\n')
            before = report.read_bytes()
            with self.assertRaises(pipeline.Failure) as rejected:
                pipeline.load_artifact(report, reference['sha256'])
            self.assertEqual(rejected.exception.code, 'ARTIFACT_HASH_MISMATCH')
            self.assertEqual(report.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
