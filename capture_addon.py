"""Capture JSON API metadata; keep credentials in memory until a flow is selected."""
import asyncio
import base64
import json
import os
import re
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent / "private"
HINT = re.compile(r"coupon|voucher|jing.?an|claim|receive|benefit|公益|消费券|领取|配送", re.I)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.chmod(temp, 0o600)
    temp.replace(path)


class Capture:
    def __init__(self):
        self.flows = OrderedDict()
        self.task = None

    def running(self):
        ROOT.mkdir(exist_ok=True)
        save_json(ROOT / "index.json", [])
        self.task = asyncio.create_task(self.watch_selection())

    def done(self):
        if self.task:
            self.task.cancel()

    def response(self, flow):
        response = flow.response
        if not response or "json" not in response.headers.get("content-type", "").lower():
            return
        if len(response.raw_content or b"") > 512_000 or len(flow.request.raw_content or b"") > 128_000:
            return
        parts = urlsplit(flow.request.pretty_url)
        path = re.sub(r"(?<=/)[0-9a-fA-F-]{20,}(?=/|$)", "<id>", parts.path)
        content = response.get_text(strict=False) or ""
        try:
            parsed = json.loads(content)
            fields = list(parsed)[:25] if isinstance(parsed, dict) else ["<array>"]
        except (ValueError, TypeError):
            fields = []
        metadata = {
            "id": flow.id, "time": time.strftime("%H:%M:%S"),
            "method": flow.request.method, "host": parts.hostname, "path": path,
            "http_status": response.status_code, "fields": fields,
            "candidate": bool(HINT.search((parts.hostname or "") + parts.path + content[:100_000])),
        }
        request = {
            "captured_at_unix": flow.request.timestamp_start,
            "method": flow.request.method, "url": flow.request.pretty_url,
            "headers": list(flow.request.headers.items(multi=True)),
            "body_base64": base64.b64encode(flow.request.raw_content or b"").decode(),
        }
        self.flows[flow.id] = (metadata, request, content)
        while len(self.flows) > 300:
            self.flows.popitem(last=False)
        save_json(ROOT / "index.json", [x[0] for x in self.flows.values()])

    async def watch_selection(self):
        selection = ROOT / "select.txt"
        while True:
            if selection.exists():
                flow_id = selection.read_text(encoding="utf-8").strip()
                selection.unlink()
                if flow_id in self.flows:
                    meta, request, response = self.flows[flow_id]
                    save_json(ROOT / "request.json", request)
                    save_json(ROOT / "response.json", {"http_status": meta["http_status"], "body": response})
                    save_json(ROOT / "selection-status.json", {"exported": True, "id": flow_id})
                else:
                    save_json(ROOT / "selection-status.json", {"exported": False, "error": "flow expired or missing"})
            await asyncio.sleep(0.5)


addons = [Capture()]
