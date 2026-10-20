import json

import httpx
import pytest

import jingan


def candidate(tmp_path, headers=None):
    path = tmp_path / 'candidate.json'
    path.write_text(json.dumps({
        'url': jingan.BASE + '/v1/user/info',
        'headers': headers or {'Token': 'SYNTHETIC_NEW', 'WeChatAppId': '5'},
    }), encoding='utf-8-sig')
    return path


@pytest.mark.parametrize('code,state', [(50001, 'login_required'), (50008, 'login_required'),
                                      (50014, 'login_required'), (40000, 'business_rejected')])
def test_api_errors_preserve_code_without_misdiagnosing_business_rejections(code, state, capsys):
    client = jingan.JinganClient({'Token': 'SYNTHETIC'}, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={'code': code, 'message': 'PRIVATE_DETAIL'})))
    try:
        with pytest.raises(jingan.ApiRejected) as error:
            client.profile()
        jingan.report_error(error.value)
    finally:
        client.close()
    output = capsys.readouterr().err
    assert json.loads(output)['state'] == state
    assert json.loads(output)['code'] == code
    assert 'PRIVATE_DETAIL' not in output and 'SYNTHETIC' not in output


@pytest.mark.parametrize('response', [
    {'code': 50001},
    {'code': 20000, 'data': []},
    {'code': 20000, 'data': {'user_type_time': -1}},
])
def test_rejected_candidate_never_replaces_old_session(tmp_path, monkeypatch, response):
    monkeypatch.setattr(jingan, 'ROOT', tmp_path)
    (tmp_path / 'private').mkdir()
    existing = tmp_path / 'private/session.json'
    existing.write_text('EXISTING_SESSION', encoding='utf-8')
    original = jingan.JinganClient
    monkeypatch.setattr(jingan, 'JinganClient', lambda headers, proxy=None: original(
        headers, transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response))))
    with pytest.raises(ValueError):
        jingan.import_session(candidate(tmp_path))
    assert existing.read_text() == 'EXISTING_SESSION'
    assert not list((tmp_path / 'private').glob('session-*.tmp'))


def test_valid_candidate_import_is_atomic_and_does_not_send_a_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(jingan, 'ROOT', tmp_path)
    requests = []
    def handler(req):
        requests.append(req)
        return httpx.Response(200, json={'code': 20000, 'data': {'user_type_time': 0}})
    original = jingan.JinganClient
    monkeypatch.setattr(jingan, 'JinganClient', lambda headers, proxy=None: original(
        headers, transport=httpx.MockTransport(handler)))
    jingan.import_session(candidate(tmp_path, {'Token': 'SYNTHETIC_NEW', 'Unrelated': 'DROP_ME'}))
    saved = json.loads((tmp_path / 'private/session.json').read_text())
    assert saved['validated_at']
    assert dict(saved['headers']) == {'Token': 'SYNTHETIC_NEW'}
    assert len(requests) == 1 and requests[0].method == 'GET'
    assert requests[0].url.path == '/api/v1/user/info'
    assert not list((tmp_path / 'private').glob('session-*.tmp'))


def test_active_claim_prevents_session_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr(jingan, 'ROOT', tmp_path)
    original = jingan.JinganClient
    monkeypatch.setattr(jingan, 'JinganClient', lambda headers, proxy=None: original(
        headers, transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
            'code': 20000, 'data': {'user_type_time': 0}}))))
    existing = tmp_path / 'private/session.json'
    existing.parent.mkdir()
    existing.write_text('OLD', encoding='utf-8')
    lock = jingan.SingleInstanceLock(tmp_path / 'private/claim.lock').acquire()
    try:
        with pytest.raises(jingan.LockBusy):
            jingan.import_session(candidate(tmp_path))
    finally:
        lock.close()
    assert existing.read_text() == 'OLD'
