import json

from utils import benchmark_jobs as jobs
from pipeline.run_custom_benchmark import run, validate_findings, parse_response


def test_fenced_json_with_explanation():
    assert parse_response('```json\n{"findings": []}\n```\nKaynak okunamadı.') == {'findings': []}


def test_search_uses_only_tool_urls_on_official_domains():
    from utils.benchmark_discovery import parse_search_response
    response = {'content': [
        {'type': 'text', 'text': 'https://bank.test/invented'},
        {'type': 'server_tool_use', 'name': 'web_search', 'input': {'query': 'bank saas'}},
        {'type': 'web_search_tool_result', 'content': [
            {'type': 'web_search_result', 'url': 'https://bank.test/offer#details'},
            {'type': 'web_search_result', 'url': 'https://bank.test.evil.test/offer'},
            {'type': 'web_search_result', 'url': 'https://bank.test/offer'},
        ]},
        {'type': 'web_search_tool_result', 'content': {'error_code': 'max_uses_exceeded'}},
    ]}
    result = parse_search_response(response, ['bank.test'])
    assert result['urls'] == ['https://bank.test/offer']
    assert result['queries'] == ['bank saas']
    assert result['errors'] == ['max_uses_exceeded']


def test_cancellation_cannot_be_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv('BENCHMARK_DB_PATH', str(tmp_path / 'jobs.db'))
    job_id = jobs.create({'banks': ['QNB']}, 'test')
    jobs.update(job_id, 'Sırada', {}, [])
    jobs.cancel(job_id)
    jobs.update(job_id, 'İnceleme bekliyor', {}, [])
    assert jobs.get(job_id)['status'] == 'İptal edildi'


def test_evidence_is_required_per_cell():
    text = 'KOBİ müşterilerine üç ay ücretsiz kullanım sunulur.'
    payload = {'findings': [{'values': {
        'Fiyat': {'value': 'Ücretsiz', 'url': 'https://bank.test', 'quote': text},
        'Süre': {'value': '12 ay', 'url': 'https://bank.test', 'quote': 'Bu alıntı kaynakta bulunmuyor.'},
        'Limit': {'value': 'Limitsiz', 'url': 'https://other.test', 'quote': text},
    }}]}
    findings = validate_findings(payload, {'https://bank.test': text}, ['Fiyat', 'Süre', 'Limit'], 'QNB')
    assert list(findings[0]['values']) == ['Fiyat']


def test_worker_keeps_partial_results_when_one_bank_fails(tmp_path, monkeypatch):
    monkeypatch.setenv('BENCHMARK_DB_PATH', str(tmp_path / 'jobs.db'))
    from pipeline import run_custom_benchmark as worker
    from types import SimpleNamespace
    monkeypatch.setattr(worker, 'get_llm_config', lambda: SimpleNamespace(has_api_key=True, max_items_per_run=5))
    monkeypatch.setattr(worker, 'candidates', lambda bank, topic: ['https://bank.test'])
    quote = 'KOBİ müşterileri için üç ay ücretsiz kullanım.'
    monkeypatch.setattr(worker, 'fetch', lambda url: (url, quote, []))
    monkeypatch.setattr(worker, 'review_findings', lambda findings, brief: findings)
    replies = iter([json.dumps({'findings': [{'title': 'Paket', 'values': {'Fiyat': {'value': 'Ücretsiz', 'url': 'https://bank.test', 'quote': quote}}}]}), 'invalid JSON'])
    monkeypatch.setattr(worker, 'summarize_with_anthropic', lambda *args, **kwargs: next(replies))
    job_id = jobs.create({'banks': ['QNB', 'Akbank'], 'topic': 'AI / SaaS', 'criteria': ['Fiyat']}, 'Araştır')
    jobs.update(job_id, 'Sırada', {}, [])
    run(job_id)
    saved = jobs.get(job_id)
    assert len(saved['result']) == 1
    assert saved['progress']['completed'] == 2
    assert 'tamamlanamadı' in saved['progress']['banks']['Akbank']


def test_semantic_review_cannot_add_values(monkeypatch):
    from pipeline import run_custom_benchmark as worker
    findings = [{'bank': 'QNB', 'title': 'Paket', 'values': {'Fiyat': {'value': 'Ücretsiz'}, 'Süre': {'value': '6 ay'}}}]
    monkeypatch.setattr(worker, 'summarize_with_anthropic', lambda *a, **k: '{"findings":[{"index":0,"criteria":["Fiyat","Uydurma"]},{"index":8,"criteria":["Fiyat"]}]}')
    assert list(worker.review_findings(findings, 'AI')[0]['values']) == ['Fiyat']


def test_job_can_only_be_claimed_once(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.delenv('BENCHMARK_DATABASE_URL', raising=False)
    monkeypatch.setenv('BENCHMARK_DB_PATH', str(tmp_path / 'jobs.db'))
    job_id = jobs.create({'banks': ['QNB']}, 'test')
    jobs.update(job_id, 'Sırada', {}, [])
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda _: jobs.claim(job_id), range(4)))
    assert sum(token is not None for token in tokens) == 1


def test_expired_worker_cannot_write_results(tmp_path, monkeypatch):
    monkeypatch.delenv('BENCHMARK_DATABASE_URL', raising=False)
    monkeypatch.setenv('BENCHMARK_DB_PATH', str(tmp_path / 'jobs.db'))
    job_id = jobs.create({'banks': ['QNB']}, 'test')
    jobs.update(job_id, 'Sırada', {}, [])
    token = jobs.claim(job_id)
    assert jobs.heartbeat(job_id, token)
    with jobs.connect() as db:
        db.execute('UPDATE jobs SET lease_until=0 WHERE id=?', (job_id,))
    assert jobs.recover_interrupted() == 1
    jobs.update(job_id, 'İnceleme bekliyor', {}, [{'bad': 'late'}], token=token)
    assert jobs.get(job_id)['status'] == 'Kesildi'
    assert jobs.get(job_id)['result'] == []


def test_external_launch_only_enqueues(tmp_path, monkeypatch):
    monkeypatch.delenv('BENCHMARK_DATABASE_URL', raising=False)
    monkeypatch.setenv('BENCHMARK_DB_PATH', str(tmp_path / 'jobs.db'))
    monkeypatch.setenv('BENCHMARK_WORKER_MODE', 'external')
    def unexpected(*args, **kwargs):
        raise AssertionError('External mode must not launch a local subprocess')
    monkeypatch.setattr(jobs.subprocess, 'Popen', unexpected)
    job_id = jobs.create({'banks': ['QNB']}, 'test')
    jobs.launch(job_id)
    assert jobs.next_queued() == job_id
    assert jobs.get(job_id)['status'] == 'Sırada'
