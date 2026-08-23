"""Helpers for the `label` command: run the web server in the background, open a browser."""

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

LOG_PATH = Path.home() / ".local" / "share" / "singlish-transcriber" / "web.log"


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except FileNotFoundError:
        return False


def open_url(url: str) -> None:
    """Open a URL in the user's browser. Under WSL, `webbrowser.open` can't reach the
    Windows host's browser, so shell out to Windows' own opener instead."""
    if _is_wsl():
        subprocess.run(["explorer.exe", url], check=False)
    else:
        webbrowser.open(url)


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def ensure_server_running(host: str, port: int, db_path: str, timeout: float = 15.0) -> None:
    """Start the web server in the background if nothing is already listening on host:port.

    Note: this only checks that *something* is listening on the port, not which database it
    was started against - if you've manually started the server against a different --db, the
    port check won't catch the mismatch.
    """
    if _port_is_open(host, port):
        return

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["SINGLISH_TRANSCRIBER_DB"] = str(db_path)
    with open(LOG_PATH, "a") as log_file:
        subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "singlish_transcriber.web.app:app",
                "--host", host, "--port", str(port),
            ],
            env=env,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_is_open(host, port):
            return
        time.sleep(0.3)
    raise RuntimeError(
        f"web server did not come up on {host}:{port} within {timeout}s - check {LOG_PATH}"
    )
