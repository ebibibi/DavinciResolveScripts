"""An edit job must report its real outcome and must not live inside the caller's service."""
import os
import signal
import stat
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "opus_free_edit" / "run.sh"
START = REPO / "opus_free_edit" / "start.sh"


def _wait_for_status(status: Path, expected: str, timeout: float) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if status.exists() and status.read_text().strip() == expected:
            return expected
        time.sleep(0.2)
    return status.read_text().strip() if status.exists() else "<missing>"


def test_terminated_job_reports_failed(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    job = tmp_path / "job"
    env = {**os.environ, "INBOX": str(inbox)}
    proc = subprocess.Popen(["bash", str(RUN), "latest", str(job)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_for_status(job / "STATUS", "waiting", 10) == "waiting"
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)  # bash runs the trap once its foreground `sleep 20` ends
    finally:
        proc.kill()
    assert (job / "STATUS").read_text().strip() == "failed"


def _fake_systemd_run(tmp_path: Path, exit_code: int = 0) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "args.txt"
    fake = bin_dir / "systemd-run"
    fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{args_file}"\nexit {exit_code}\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return bin_dir, args_file


def test_start_launches_a_separate_user_unit(tmp_path):
    bin_dir, args_file = _fake_systemd_run(tmp_path)
    job = tmp_path / "20261106-some topic"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "DECK_SLUG": "my-deck"}
    subprocess.run(["bash", str(START), "latest", str(job)], env=env, check=True, capture_output=True)
    args = args_file.read_text().splitlines()
    assert "--user" in args
    assert any(a.startswith("--unit=video-edit-20261106-some-topic") for a in args)
    assert "--setenv=DECK_SLUG=my-deck" in args
    assert args[-3:] == [str(RUN), "latest", str(job)]
    assert (job / "STATUS").read_text().strip() == "starting"


def test_start_reports_failed_when_the_unit_cannot_start(tmp_path):
    bin_dir, _ = _fake_systemd_run(tmp_path, exit_code=1)
    job = tmp_path / "job"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    result = subprocess.run(["bash", str(START), "latest", str(job)], env=env, capture_output=True)
    assert result.returncode != 0
    assert (job / "STATUS").read_text().strip() == "failed"
