import sys
import time
import subprocess

import httpx
import pytest

from samples.common import HOST, REGISTER_PORT, SERVER_PORT, CLIENT_PORT


def _wait_health(url, timeout=20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/health", timeout=1)
            if r.status_code == 200:
                return
        except Exception as e:
            last = e
        time.sleep(0.2)
    raise RuntimeError(f"{url} not healthy within {timeout}s: {last}")


@pytest.fixture(scope="session", autouse=True)
def services():
    specs = [
        ("samples.register:app", REGISTER_PORT),
        ("samples.server:app", SERVER_PORT),
        ("samples.client:app", CLIENT_PORT),
    ]
    procs = []
    try:
        for module, port in specs:
            url = f"http://{HOST}:{port}"
            p = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", module, "--host", HOST, "--port", str(port)]
            )
            procs.append(p)
            _wait_health(url)
        yield
    finally:
        for p in reversed(procs):
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
                p.wait()
