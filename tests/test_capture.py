import asyncio
import base64
import json
from types import SimpleNamespace

from mitmproxy.http import Headers

import capture_addon


def test_metadata_hides_credentials_and_selected_request_is_exact(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_addon, "ROOT", tmp_path)
    addon = capture_addon.Capture()
    flow = SimpleNamespace(
        id="test-flow",
        request=SimpleNamespace(pretty_url="https://example.test/coupon/claim?token=SECRET", method="POST",
                                headers=Headers([(b"Authorization", b"Bearer SECRET")]), raw_content=b'{ "coupon": 3 }', timestamp_start=1700000000),
        response=SimpleNamespace(headers=Headers([(b"Content-Type", b"application/json")]), status_code=200,
                                 raw_content=b'{"code":"SOLD_OUT"}', get_text=lambda strict: '{"code":"SOLD_OUT"}'))
    addon.response(flow)
    index = (tmp_path / "index.json").read_text()
    assert "SECRET" not in index
    assert not (tmp_path / "request.json").exists()
    assert json.loads(index)[0]["candidate"] is True

    async def select():
        (tmp_path / "select.txt").write_text("test-flow")
        task = asyncio.create_task(addon.watch_selection())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    asyncio.run(select())
    exported = json.loads((tmp_path / "request.json").read_text())
    assert exported["url"].endswith("token=SECRET")
    assert base64.b64decode(exported["body_base64"]) == b'{ "coupon": 3 }'
    assert exported["headers"] == [["Authorization", "Bearer SECRET"]]
