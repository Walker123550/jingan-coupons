"""Single-account scheduled HTTP request. Dry run is the default."""
import argparse
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parent
DROP_HEADERS = {"host", "content-length", "connection", "proxy-connection", "proxy-authorization", "transfer-encoding", "accept-encoding"}


def load_request(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    parts = urlsplit(data["url"])
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Invalid HTTP URL")
    headers = data["headers"]
    if isinstance(headers, dict):
        headers = list(headers.items())
    headers = [(k, v) for k, v in headers if k.lower() not in DROP_HEADERS]
    body = base64.b64decode(data.get("body_base64", ""), validate=True)
    return data["method"].upper(), data["url"], headers, body


def target_time(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        result = result.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return result


def wait_until(target):
    remaining = target.timestamp() - time.time()
    if remaining < -1:
        raise ValueError("Scheduled time has passed; refusing a late submission")
    if remaining > 0:
        deadline = time.monotonic() + remaining
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(left, 0.1 if left < 1 else 1))


def classify(response, rules):
    if response.status_code == 429:
        return "rate_limited"
    if response.status_code in {401, 403}:
        return "authentication_or_access_required"
    if not 200 <= response.status_code < 300:
        return "http_error"
    try:
        data = response.json()
    except ValueError:
        return "unknown"
    for rule in rules:
        value = data
        try:
            for part in rule["path"]:
                value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if value == rule["equals"]:
            return rule["state"]
    return "unknown"


def execute(client, request, rules):
    method, url, headers, body = request
    try:
        response = client.request(method, url, headers=headers, content=body)
    except httpx.HTTPError:
        return {"state": "transport_error_result_unknown", "retry": False}
    result = {"state": classify(response, rules), "http_status": response.status_code, "retry": False}
    if response.status_code == 429:
        result["retry_after"] = response.headers.get("retry-after")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", default=str(ROOT / "private/request.json"))
    parser.add_argument("--rules", default=str(ROOT / "rules.json"))
    parser.add_argument("--at", help="ISO time; defaults to Asia/Shanghai when offset omitted")
    parser.add_argument("--send", action="store_true", help="Actually submit exactly one request")
    parser.add_argument("--proxy", help="Optional explicit HTTP proxy; environment proxies are otherwise ignored")
    args = parser.parse_args()
    try:
        request = load_request(args.request)
        settings = json.loads(Path(args.rules).read_text(encoding="utf-8"))
        target = target_time(args.at) if args.at else None
        if target and target.timestamp() < time.time() - 1:
            raise ValueError("Scheduled time has passed")
        if args.send and not settings.get("verified_request"):
            raise ValueError("Actual API and response rules have not been verified yet")
        parts = urlsplit(request[1])
        print(json.dumps({"mode": "send" if args.send else "dry_run", "method": request[0], "host": parts.hostname,
                          "body_bytes": len(request[3]), "at": target.isoformat() if target else None}, ensure_ascii=False))
        if not args.send:
            return 0
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0), follow_redirects=False,
                          trust_env=False, proxy=args.proxy) as client:
            if target:
                wait_until(target)
            result = execute(client, request, settings.get("rules", []))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["state"] == "success" else 2
    except (ValueError, KeyError, OSError) as exc:
        # Never print URL, body, token, or exception text containing credentials.
        print(json.dumps({"error": type(exc).__name__, "hint": "Check local request/rules/time configuration"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
