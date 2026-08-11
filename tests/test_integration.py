import httpx

from samples.common import REGISTER_URL, SERVER_URL, CLIENT_URL


def test_health():
    for url in (REGISTER_URL, SERVER_URL, CLIENT_URL):
        r = httpx.get(f"{url}/health", timeout=2)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_server_registered():
    r = httpx.get(f"{REGISTER_URL}/discover/server", timeout=2)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "server"
    assert body["address"] == SERVER_URL


def test_client_run():
    r = httpx.post(f"{CLIENT_URL}/run", json={"msg": "hello"}, timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["discovered"]["name"] == "server"
    assert body["discovered"]["address"] == SERVER_URL
    assert body["server_response"]["ack"] == "received: hello"
