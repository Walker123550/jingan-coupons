"""Verify live HTTPS proxy and JSON capture with a local synthetic server."""
import json
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = b'{"code":"TEST_ONLY","coupon":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    context = ssl.create_default_context(cafile=str(ROOT / "private/mitm/mitmproxy-ca-cert.pem"))
    with httpx.Client(proxy="http://127.0.0.1:18080", verify=context, trust_env=False,
                      follow_redirects=True, timeout=20) as client:
        response = client.get("https://mitmproxy.org/")
        assert response.status_code == 200
    print("HTTPS proxy: certificate verified, final HTTP 200")
    server = ThreadingHTTPServer(("127.0.0.1", 18083), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(proxy="http://127.0.0.1:18080", trust_env=False, timeout=10) as client:
            response = client.post("http://127.0.0.1:18083/coupon/test", json={"test": True},
                                   headers={"Authorization": "Bearer SYNTHETIC_TEST"})
            assert response.json()["code"] == "TEST_ONLY"
        time.sleep(0.5)
        index = json.loads((ROOT / "private/index.json").read_text())
        assert "SYNTHETIC_TEST" not in json.dumps(index)
        assert not any(x['host']=='127.0.0.1' and x['path']=='/coupon/test' for x in index)
        print("Capture scope: unrelated synthetic traffic is not retained")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
