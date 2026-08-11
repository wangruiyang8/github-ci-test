import httpx

from samples.common import REGISTER_URL, SERVER_URL, CLIENT_URL


def _log(method, url, status, resp_body, req_body=None):
    print(f"\n>>> {method} {url}")
    if req_body is not None:
        print(f"    request body : {req_body}")
    print(f"    status       : {status}")
    print(f"    response body: {resp_body}")


def test_health():
    print("\n=== test_health: 三服务各自 /health ===")
    for name, url in (("register", REGISTER_URL), ("server", SERVER_URL), ("client", CLIENT_URL)):
        r = httpx.get(f"{url}/health", timeout=2)
        _log("GET", f"{url}/health", r.status_code, r.json())
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_server_registered():
    print("\n=== test_server_registered: server 启动时已向 register POST 注册，现从 register GET 验证 ===")
    r = httpx.get(f"{REGISTER_URL}/discover/server", timeout=2)
    _log("GET", f"{REGISTER_URL}/discover/server", r.status_code, r.json())
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "server"
    assert body["address"] == SERVER_URL


def test_client_run():
    print("\n=== test_client_run: client /run -> GET register 发现 -> POST server 调用 ===")
    req_body = {"msg": "hello"}
    r = httpx.post(f"{CLIENT_URL}/run", json=req_body, timeout=5)
    _log("POST", f"{CLIENT_URL}/run", r.status_code, r.json(), req_body)
    assert r.status_code == 200
    body = r.json()
    assert body["discovered"]["name"] == "server"
    assert body["discovered"]["address"] == SERVER_URL
    assert body["server_response"]["ack"] == "received: hello"
