"""Real loopback API acceptance; this is a one-person self-test, not B-group sign-off."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    root = Path.cwd()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit('Use a fresh output directory')
    out.mkdir(parents=True)
    request = json.loads(args.request.read_text())
    base_url = f'http://127.0.0.1:{args.port}'
    sid = subprocess.check_output(['git', 'config', '--local', 'user.name'], text=True).strip()
    service = None
    service_log = None
    service_container = None
    generation = 0

    def call(method, path, data=None, expected=200):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(base_url + path, data=body, method=method,
                      headers={'Content-Type': 'application/json'} if body is not None else {})
        try:
            with urlopen(req, timeout=30) as response:
                code, content, headers = response.status, response.read(), dict(response.headers)
        except HTTPError as exc:
            code, content, headers = exc.code, exc.read(), dict(exc.headers)
        with (out / 'http-log.jsonl').open('a') as log:
            log.write(json.dumps({'time': time.time(), 'method': method, 'path': path,
                                  'request': data, 'status': code,
                                  'body': content.decode(errors='replace'), 'headers': headers}) + '\n')
        assert code == expected, (path, code, content[:500])
        return content, headers

    def get_json(path):
        return json.loads(call('GET', path)[0])

    def submit(key, payload):
        return json.loads(call('POST', '/v1/jobs', {'idempotency_key': key, 'input': payload}, 202)[0])

    def await_job(job):
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            state = get_json('/v1/jobs/' + job)
            if state['status'] in ['SUCCEEDED', 'FAILED', 'TIMED_OUT']:
                return state
            time.sleep(2)
        raise TimeoutError('API task did not finish within 900 seconds')

    def start_service():
        nonlocal service, service_log, service_container, generation
        generation += 1
        service_log = (out / f'server-{generation}.log').open('w')
        service = subprocess.Popen(['python3', 'run_e11e12.py', 'serve', '--port', str(args.port)],
                                   cwd=root, stdout=service_log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                with urlopen(base_url + '/health', timeout=2) as response:
                    assert json.load(response)['status'] == 'ok'
                break
            except (URLError, ConnectionError):
                assert service.poll() is None, 'Service exited during startup'
                time.sleep(0.5)
        else:
            raise TimeoutError('Service startup failed')
        ids = subprocess.check_output(['docker', 'ps', '-q', '--filter', f'publish={args.port}',
                                       '--filter', f'ancestor=course-e11e12:{sid}'], text=True).split()
        assert len(ids) == 1, ids
        service_container = ids[0]
        print('API_SERVICE_STARTED', generation, service_container, flush=True)

    def stop_service():
        nonlocal service, service_log, service_container
        if service_container:
            result = subprocess.run(['docker', 'stop', '--time', '2', service_container],
                                    capture_output=True, text=True, timeout=20)
            (out / f'server-{generation}-stop.json').write_text(json.dumps({
                'container': service_container, 'exit_code': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr}, indent=2) + '\n')
            assert result.returncode == 0, result.stderr
            service_container = None
        if service:
            service.wait(timeout=20)
            service = None
        if service_log:
            service_log.close()
            service_log = None

    try:
        start_service()
        assert get_json('/health')['schema_version'] == 'e11e12-1'
        key = 'e12-student241880408-' + str(time.time_ns())
        first = submit(key, request)
        duplicate = submit(key, request)
        assert first['job_id'] == duplicate['job_id']
        conflict = dict(request, target=request['base'])
        content, _ = call('POST', '/v1/jobs', {'idempotency_key': key, 'input': conflict}, 409)
        assert json.loads(content)['error'] == 'IDEMPOTENCY_CONFLICT'
        call('POST', '/v1/jobs', {'idempotency_key': 'invalid', 'input': {}}, 400)
        call('GET', '/v1/jobs/does-not-exist', expected=404)
        job = first['job_id']
        state = await_job(job)
        assert state['status'] == 'SUCCEEDED', state
        result = get_json('/v1/jobs/' + job + '/artifacts')
        assert result['job_id'] == job and result['trace_id'] == state['trace_id']
        assert [stage['name'] for stage in result['stages']] == [
            'draft', 'full-check', 'incremental-check', 'repair', 'recheck']
        patch_bytes, headers = call('GET', '/v1/jobs/' + job + '/files/candidate.patch')
        digest = hashlib.sha256(patch_bytes).hexdigest()
        assert headers['X-Content-SHA256'] == digest
        record = next(artifact for artifact in result['artifacts']
                      if artifact['uri'] == f'artifact://{job}/candidate.patch')
        assert record['sha256'] == digest
        (out / 'candidate.patch').write_bytes(patch_bytes)
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        call('GET', '/v1/jobs/' + job + '/files/%2e%2e/state.json', expected=404)
        call('GET', '/v1/jobs/' + job + '/files/base-project/.git/config', expected=404)

        pending = [submit(key + '-restart-' + str(i), request) for i in range(3)]
        before_restart = [get_json('/v1/jobs/' + item['job_id']) for item in pending]
        assert any(item['status'] in ['QUEUED', 'RUNNING'] for item in before_restart)
        stop_service()
        start_service()
        assert get_json('/v1/jobs/' + job)['status'] == 'SUCCEEDED'
        assert submit(key, request)['job_id'] == job
        assert call('GET', '/v1/jobs/' + job + '/files/candidate.patch')[0] == patch_bytes
        recovered = [get_json('/v1/jobs/' + item['job_id']) for item in pending]
        restarted = [item for item in recovered if item.get('error', {}).get('code') == 'SERVER_RESTARTED']
        assert restarted, recovered
        failed = restarted[0]
        assert submit(failed['idempotency_key'], request)['job_id'] == failed['job_id']
        retry_request = dict(request, mode='e11-a')
        retry = submit(key + '-new-key-retry', retry_request)
        assert await_job(retry['job_id'])['status'] == 'SUCCEEDED'
        summary = {'passed': True, 'scope': 'single-student server loopback self-test; B-group joint acceptance pending',
                   'url': base_url, 'job_id': job, 'trace_id': state['trace_id'],
                   'input_sha256': hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
                   'patch_sha256': digest, 'duplicate_same_job': True, 'conflict_http_status': 409,
                   'path_boundaries_http_status': 404, 'completed_job_survived_restart': True,
                   'before_restart': before_restart, 'recovered_jobs': recovered,
                   'retry_job_id': retry['job_id'], 'service_generations': generation}
        (out / 'acceptance.json').write_text(json.dumps(summary, indent=2) + '\n')
        print('API_ACCEPTANCE_PASS', json.dumps(summary), flush=True)
    finally:
        stop_service()


if __name__ == '__main__':
    main()
