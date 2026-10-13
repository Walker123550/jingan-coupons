import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent / "private"


def shape(value, depth=0):
    if depth > 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return {"count": len(value), "first_shape": shape(value[0], depth+1) if value else None}
    return type(value).__name__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("flow_id")
    parser.add_argument("name")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.name):
        raise SystemExit("Invalid name")
    status = ROOT / "selection-status.json"
    status.unlink(missing_ok=True)
    (ROOT / "select.txt").write_text(args.flow_id)
    for _ in range(50):
        if status.exists():
            result = json.loads(status.read_text())
            if not result.get("exported") or result.get("id") != args.flow_id:
                raise SystemExit("Selected flow unavailable")
            folder = ROOT / "flows" / args.name
            folder.mkdir(parents=True, exist_ok=True)
            for name in ["request.json", "response.json"]:
                (ROOT / name).replace(folder / name)
            req = json.loads((folder / "request.json").read_text())
            res = json.loads((folder / "response.json").read_text())
            data = json.loads(res["body"])
            parts = urlsplit(req["url"])
            print(json.dumps({"name": args.name, "path": parts.path, "query_keys": [k for k,v in parse_qsl(parts.query)],
                              "header_names": [k for k,v in req["headers"]], "response_code": data.get("code") if isinstance(data, dict) else None, "shape": shape(data)}, ensure_ascii=False))
            return
        time.sleep(0.1)
    raise SystemExit("Export timed out")


if __name__ == "__main__":
    main()
