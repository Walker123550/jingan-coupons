import subprocess
import sys
from pathlib import Path

from process_lock import SingleInstanceLock


def test_two_processes_cannot_both_acquire_and_release_allows_next(tmp_path):
    path=tmp_path/'lock with spaces.bin'
    lock=SingleInstanceLock(path).acquire()
    code='from pathlib import Path;import sys;from process_lock import SingleInstanceLock,LockBusy;\ntry:\n l=SingleInstanceLock(Path(sys.argv[1])).acquire();l.close()\nexcept LockBusy:\n sys.exit(2)'
    try:
        first=subprocess.run([sys.executable,'-c',code,str(path)],cwd=Path(__file__).resolve().parents[1],capture_output=True)
        assert first.returncode==2,first.stderr
    finally:lock.close()
    second=subprocess.run([sys.executable,'-c',code,str(path)],cwd=Path(__file__).resolve().parents[1],capture_output=True)
    assert second.returncode==0,second.stderr
