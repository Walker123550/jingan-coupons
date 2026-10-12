"""Start/stop the project-owned mitmdump process in WSL."""
import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status", "guard"])
    parser.add_argument("--upstream")
    parser.add_argument("--capture-id")
    parser.add_argument("--duration", type=int, default=600)
    args = parser.parse_args()
    PRIVATE.mkdir(exist_ok=True)
    if args.action == "guard":
        if not args.capture_id or not 5 <= args.duration <= 7200:
            raise SystemExit("Invalid guard configuration")
        with open(PRIVATE / "guard.log", "ab") as logfile:
            proc = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "capture_guard.py"),
                                     args.capture_id, str(args.duration)], cwd=ROOT, stdin=subprocess.DEVNULL,
                                    stdout=logfile, stderr=logfile, start_new_session=True)
        print(json.dumps({"guard_pid": proc.pid, "duration": args.duration}))
        return
    pid_file = PRIVATE / "proxy.pid"
    pid = int(pid_file.read_text()) if pid_file.exists() else None
    owned = False
    if pid:
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
            owned = str(ROOT / "capture_addon.py").encode() in cmdline and b"mitmdump" in cmdline
        except FileNotFoundError:
            pass
    if args.action == "stop":
        if owned:
            os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        print(json.dumps({"stopped": True}))
        return
    if args.action == "status":
        print(json.dumps({"running": owned, "pid": pid if owned else None}))
        return
    if owned:
        raise SystemExit("Project capture process already running")
    cmd = [str(ROOT / ".venv/bin/mitmdump"), "--quiet", "--listen-host", "127.0.0.1", "--listen-port", "18080",
           "--set", f"confdir={PRIVATE / 'mitm'}", "--set", "block_global=true", "--set", "stream_large_bodies=512k",
           "-s", str(ROOT / "capture_addon.py")]
    if args.upstream:
        cmd += ["--mode", f"upstream:http://{args.upstream}"]
    os.umask(0o077)
    with open(PRIVATE / "proxy.log", "ab") as logfile:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=logfile, stderr=logfile, start_new_session=True)
    pid_file.write_text(str(proc.pid))
    for _ in range(60):
        if proc.poll() is not None:
            raise SystemExit("Capture process failed; inspect local private/proxy.log")
        if (PRIVATE / "mitm/mitmproxy-ca-cert.cer").exists() and (PRIVATE / "index.json").exists():
            try:
                with socket.create_connection(("127.0.0.1", 18080), timeout=0.25):
                    print(json.dumps({"running": True, "pid": proc.pid, "port": 18080}))
                    return
            except OSError:
                pass
        time.sleep(0.25)
    os.kill(proc.pid, signal.SIGTERM)
    raise SystemExit("Capture process did not initialize")


if __name__ == "__main__":
    main()
