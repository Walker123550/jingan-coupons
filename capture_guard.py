"""Persistent WSL guard; invoke Windows restore for this exact capture session."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    capture_id, duration = sys.argv[1], int(sys.argv[2])
    deadline = time.monotonic() + duration
    state_file = ROOT / "private/windows-state.json"
    while time.monotonic() < deadline:
        try:
            state = json.loads(state_file.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return
        if state.get("captureId") != capture_id:
            return
        time.sleep(min(1, max(0.01, deadline - time.monotonic())))
    script_path = subprocess.check_output(["wslpath", "-w", str(ROOT / "Restore-Capture.ps1")], text=True).strip()
    subprocess.run(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile",
                    "-ExecutionPolicy", "Bypass", "-File", script_path, "-CaptureId", capture_id], check=True)


if __name__ == "__main__":
    main()
