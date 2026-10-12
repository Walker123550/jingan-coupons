import base64
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from claim import classify, execute, load_request, target_time, wait_until


def test_http_200_is_not_claim_success():
    assert classify(httpx.Response(200, json={"code": "SOLD_OUT"}), []) == "unknown"
    rules = [{"path": ["code"], "equals": "OK", "state": "success"}]
    assert classify(httpx.Response(200, json={"code": "SOLD_OUT"}), rules) == "unknown"
    assert classify(httpx.Response(200, json={"code": "OK"}), rules) == "success"


def test_request_body_and_duplicate_headers_preserved(tmp_path):
    path = tmp_path / "request.json"
    raw = b'{ "coupon": 123 }'
    path.write_text(json.dumps({"url": "https://example.test/claim", "method": "POST", "body_base64": base64.b64encode(raw).decode(),
                               "headers": [["Host", "wrong"], ["Cookie", "a=1"], ["Cookie", "b=2"], ["Content-Length", "999"]]}))
    method, url, headers, body = load_request(path)
    assert body == raw
    assert headers == [("Cookie", "a=1"), ("Cookie", "b=2")]


@pytest.mark.parametrize("status", [429, 401, 403, 500, 302])
def test_one_request_no_automatic_retry_or_redirect(status):
    seen = []
    def handler(req):
        seen.append(req)
        return httpx.Response(status, headers={"Retry-After": "30", "Location": "https://example.test/other"})
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        result = execute(client, ("POST", "https://example.test/claim", [], b""), [])
    assert len(seen) == 1
    assert result["retry"] is False
    if status == 429:
        assert result["state"] == "rate_limited"
        assert result["retry_after"] == "30"


def test_timeout_is_ambiguous_and_not_retried():
    seen = []
    def handler(req):
        seen.append(req)
        raise httpx.ReadTimeout("private token must not be printed")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = execute(client, ("POST", "https://example.test/claim", [], b""), [])
    assert len(seen) == 1
    assert result == {"state": "transport_error_result_unknown", "retry": False}


def test_china_time_and_past_schedule():
    assert target_time("2026-10-13T08:00:00").utcoffset() == timedelta(hours=8)
    with pytest.raises(ValueError):
        wait_until(datetime.now(timezone.utc) - timedelta(seconds=5))
