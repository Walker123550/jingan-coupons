import json
from datetime import datetime

import httpx
import pytest

import jingan


def test_late_launch_does_not_silently_target_tomorrow():
    now = datetime(2026, 10, 13, 11, 0, 38, tzinfo=jingan.CN)
    next_release = datetime(2026, 10, 14, 11, tzinfo=jingan.CN)
    with pytest.raises(ValueError, match='not today'):
        jingan.validate_schedule(next_release, now, True, False)
    jingan.validate_schedule(next_release, now, True, True)
    jingan.validate_schedule(next_release, now, False, False)


def test_launch_ten_minutes_early_accepts_today():
    jingan.validate_schedule(datetime(2026,10,13,11,tzinfo=jingan.CN),
                              datetime(2026,10,13,10,50,tzinfo=jingan.CN),True,False)


def test_claim_log_has_timing_and_result_without_credentials(tmp_path, monkeypatch):
    logger = jingan.RunLog(tmp_path)
    monkeypatch.setattr(jingan, 'RUN_LOG', logger)
    token = 'PRIVATE_TEST_TOKEN'
    location = '31.123456,121.654321'
    client = jingan.JinganClient({'Token':token},transport=httpx.MockTransport(lambda req:
        httpx.Response(200,json={'code':40000,'message':'sold out','data':None})))
    try:
        result = client.submit(4,location,'0123456789abcdef')
        jingan.audit('claim_result',**result)
    finally:
        client.close()
    text = logger.path.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert [r['event'] for r in rows] == ['claim_submitted','claim_received','claim_result']
    assert rows[-1]['code'] == 40000
    assert all('time' in row for row in rows)
    assert token not in text and location not in text and '0123456789abcdef' not in text


def test_unexpected_exception_text_is_not_logged(tmp_path, monkeypatch):
    logger = jingan.RunLog(tmp_path)
    monkeypatch.setattr(jingan,'RUN_LOG',logger)
    jingan.report_error(ValueError('PRIVATE_TEST_SECRET'))
    assert 'PRIVATE_TEST_SECRET' not in logger.path.read_text()


def test_doctor_or_dry_run_does_not_hide_actual_claim_log(tmp_path):
    real=jingan.RunLog(tmp_path)
    real.record('run_started',command='claim',send=True)
    newer=jingan.RunLog(tmp_path)
    newer.record('run_started',command='doctor',send=False)
    assert jingan.latest_run_log(tmp_path)==real.path
