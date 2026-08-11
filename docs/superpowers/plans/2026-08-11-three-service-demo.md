# 三服务联调 Demo 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仓库中实现 register / server / client 三个 FastAPI 服务，各自监听独立端口，完成"注册 → 发现 → 调用"链路，并由 GitHub CI 通过集成测试自动验证。

**Architecture:** 三个独立 FastAPI 应用分别用 uvicorn 监听 8001/8002/8003。server 在 lifespan startup 中向 register POST 注册自身；client 的 `/run` 先 GET register 发现 server 地址，再 POST server 发送数据。pytest 通过 `subprocess.Popen` 启动三个真实服务并打真实端口做端到端断言。

**Tech Stack:** Python 3.11、FastAPI、uvicorn、httpx、pytest。

## Global Constraints

- Python 版本：3.11。
- 依赖不锁版本：`fastapi`、`uvicorn[standard]`、`httpx`、`pytest`。
- 服务代码全部放在 `samples/` 目录下；`samples/` 必须是 Python 包（含 `__init__.py`），以便 `uvicorn samples.register:app` 导入字符串生效。
- 默认端口：register 8001、server 8002、client 8003，host 127.0.0.1，均可经环境变量覆盖。
- 所有跨服务 httpx 调用超时 3s。
- 三个服务均暴露 `GET /health` 返回 `{"status":"ok"}`。
- 不加代码注释（除非用户要求）。
- 提交信息风格：`feat:` / `test:` / `chore:` / `docs:` 前缀。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `samples/__init__.py` | 空文件，使 `samples` 成为包。 |
| `samples/common.py` | 从环境变量读取端口/host，导出 `REGISTER_URL`/`SERVER_URL`/`CLIENT_URL` 等常量。 |
| `samples/register.py` | register FastAPI app：内存 dict，`POST /register`、`GET /discover/{name}`、`GET /health`。 |
| `samples/server.py` | server FastAPI app：lifespan startup 调用 `register_self()` 向 register 注册；`POST /data`、`GET /health`。 |
| `samples/client.py` | client FastAPI app：`POST /run`（GET register 发现 + POST server 调用）、`GET /health`。 |
| `tests/test_register.py` | register 单元测试（TestClient）。 |
| `tests/test_server.py` | server 单元测试（TestClient + monkeypatch httpx.post）。 |
| `tests/test_client.py` | client 单元测试（TestClient + monkeypatch httpx.get/post）。 |
| `tests/conftest.py` | session 级 fixture：subprocess 启动三服务并轮询 health。 |
| `tests/test_integration.py` | 端到端集成测试，打真实端口。 |
| `requirements.txt` | 依赖清单。 |
| `.github/workflows/ci.yml` | GitHub Actions 工作流。 |

---

### Task 1: 项目脚手架与配置

**Files:**
- Create: `requirements.txt`
- Create: `samples/__init__.py`
- Create: `samples/common.py`

**Interfaces:**
- Consumes: 无
- Produces: `samples.common` 模块，导出 `HOST`、`REGISTER_PORT`、`SERVER_PORT`、`CLIENT_PORT`、`REGISTER_URL`、`SERVER_URL`、`CLIENT_URL`。后续所有任务从 `samples.common` import 这些常量。

- [ ] **Step 1: 创建 requirements.txt**

```
fastapi
uvicorn[standard]
httpx
pytest
```

- [ ] **Step 2: 创建 samples/__init__.py（空文件）**

文件内容为空。

- [ ] **Step 3: 创建 samples/common.py**

```python
import os

HOST = os.getenv("HOST", "127.0.0.1")
REGISTER_PORT = int(os.getenv("REGISTER_PORT", "8001"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8002"))
CLIENT_PORT = int(os.getenv("CLIENT_PORT", "8003"))

REGISTER_URL = f"http://{HOST}:{REGISTER_PORT}"
SERVER_URL = f"http://{HOST}:{SERVER_PORT}"
CLIENT_URL = f"http://{HOST}:{CLIENT_PORT}"
```

- [ ] **Step 4: 安装依赖并验证导入**

Run: `pip install -r requirements.txt`
Run: `python -c "from samples.common import REGISTER_URL, SERVER_URL, CLIENT_URL; print(REGISTER_URL, SERVER_URL, CLIENT_URL)"`
Expected: 输出 `http://127.0.0.1:8001 http://127.0.0.1:8002 http://127.0.0.1:8003`

- [ ] **Step 5: 提交**

```bash
git add requirements.txt samples/__init__.py samples/common.py
git commit -m "chore: scaffold project structure and config"
```

---

### Task 2: register 服务（TDD）

**Files:**
- Create: `samples/register.py`
- Test: `tests/test_register.py`

**Interfaces:**
- Consumes: `samples.common`（仅 host/port，register 自身不调用其他服务）
- Produces: `samples.register.app`（FastAPI 实例），供 uvicorn 与 TestClient 使用。API 契约：
  - `POST /register` body `{"name": str, "address": str}` → `200 {"ok": true}`
  - `GET /discover/{name}` → `200 {"name": str, "address": str}`；未找到 `404 {"error": "not found"}`
  - `GET /health` → `200 {"status": "ok"}`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_register.py`：

```python
from fastapi.testclient import TestClient
from samples.register import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_register_and_discover():
    r = client.post("/register", json={"name": "server", "address": "http://127.0.0.1:8002"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    r = client.get("/discover/server")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "server"
    assert body["address"] == "http://127.0.0.1:8002"


def test_discover_not_found():
    r = client.get("/discover/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "not found"}


def test_register_overwrites():
    client.post("/register", json={"name": "server", "address": "http://old"})
    client.post("/register", json={"name": "server", "address": "http://new"})
    r = client.get("/discover/server")
    assert r.json()["address"] == "http://new"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_register.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'samples.register'`）

- [ ] **Step 3: 实现 register 服务**

创建 `samples/register.py`：

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from samples.common import HOST, REGISTER_PORT

app = FastAPI()

_REGISTRY: dict[str, str] = {}


class RegisterReq(BaseModel):
    name: str
    address: str


@app.post("/register")
def register(req: RegisterReq):
    _REGISTRY[req.name] = req.address
    return {"ok": True}


@app.get("/discover/{name}")
def discover(name: str):
    addr = _REGISTRY.get(name)
    if addr is None:
        raise HTTPException(status_code=404, detail="not found")
    return {"name": name, "address": addr}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=REGISTER_PORT)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_register.py -v`
Expected: PASS（4 个测试全绿）

- [ ] **Step 5: 提交**

```bash
git add samples/register.py tests/test_register.py
git commit -m "feat: add register service with in-memory registry"
```

---

### Task 3: server 服务（TDD）

**Files:**
- Create: `samples/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `samples.common.REGISTRY_URL`、`SERVER_URL`；调用 register 的 `POST /register`。
- Produces: `samples.server.app`（FastAPI 实例）、`samples.server.register_self(register_url, name, address, max_retries=5, initial_backoff=0.2)`。API 契约：
  - `POST /data` body `{"msg": str}` → `200 {"ack": "received: <msg>"}`
  - `GET /health` → `200 {"status": "ok"}`
- 行为：lifespan startup 调用 `register_self(REGISTER_URL, "server", SERVER_URL)`；若重试耗尽则记录警告并继续启动（不抛异常），保证 `/health` 与 `/data` 仍可用。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_server.py`：

```python
import httpx
from fastapi.testclient import TestClient

from samples.server import app, register_self


def test_register_self_success(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))

        class R:
            status_code = 200
        return R()

    monkeypatch.setattr("samples.server.httpx.post", fake_post)
    register_self("http://127.0.0.1:8001", "server", "http://127.0.0.1:8002",
                  max_retries=3, initial_backoff=0.01)
    assert len(calls) == 1
    assert calls[0][0] == "http://127.0.0.1:8001/register"
    assert calls[0][1] == {"name": "server", "address": "http://127.0.0.1:8002"}


def test_register_self_retries_on_failure(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(1)
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("samples.server.httpx.post", fake_post)
    register_self("http://127.0.0.1:8001", "server", "http://127.0.0.1:8002",
                  max_retries=3, initial_backoff=0.01)
    assert len(calls) == 3


def test_data_and_health(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        class R:
            status_code = 200
        return R()

    monkeypatch.setattr("samples.server.httpx.post", fake_post)
    with TestClient(app) as client:
        r = client.post("/data", json={"msg": "hello"})
        assert r.status_code == 200
        assert r.json() == {"ack": "received: hello"}

        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_server.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'samples.server'`）

- [ ] **Step 3: 实现 server 服务**

创建 `samples/server.py`：

```python
import time
import logging

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager

from samples.common import HOST, SERVER_PORT, REGISTER_URL, SERVER_URL

logger = logging.getLogger("server")


def register_self(register_url, name, address, max_retries=5, initial_backoff=0.2):
    url = f"{register_url}/register"
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            r = httpx.post(url, json={"name": name, "address": address}, timeout=3)
            if r.status_code == 200:
                logger.info("registered %s at %s", name, address)
                return
        except Exception as e:
            logger.warning("register attempt %d failed: %s", attempt + 1, e)
        time.sleep(backoff)
        backoff *= 2
    logger.warning("registration exhausted after %d attempts", max_retries)


class DataReq(BaseModel):
    msg: str


@asynccontextmanager
async def lifespan(app):
    register_self(REGISTER_URL, "server", SERVER_URL)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/data")
def data(req: DataReq):
    return {"ack": f"received: {req.msg}"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=SERVER_PORT)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_server.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 5: 提交**

```bash
git add samples/server.py tests/test_server.py
git commit -m "feat: add server service with startup registration"
```

---

### Task 4: client 服务（TDD）

**Files:**
- Create: `samples/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `samples.common.REGISTER_URL`；运行时 GET register `/discover/server`、POST `{discovered_address}/data`。
- Produces: `samples.client.app`（FastAPI 实例）。API 契约：
  - `POST /run` body `{"msg": str}`（msg 可选，默认 `"hello"`）→ `200 {"discovered": {"name": str, "address": str}, "server_response": {"ack": str}}`；失败 `500 {"error": str, "stage": "discover" | "call_server"}`
  - `GET /health` → `200 {"status": "ok"}`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_client.py`：

```python
from fastapi.testclient import TestClient

from samples.client import app


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_run_success(monkeypatch):
    def fake_get(url, timeout=None):
        class R:
            status_code = 200
            def json(self):
                return {"name": "server", "address": "http://127.0.0.1:9999"}
        return R()

    def fake_post(url, json=None, timeout=None):
        class R:
            status_code = 200
            def json(self):
                return {"ack": "received: hi"}
        return R()

    monkeypatch.setattr("samples.client.httpx.get", fake_get)
    monkeypatch.setattr("samples.client.httpx.post", fake_post)

    with TestClient(app) as client:
        r = client.post("/run", json={"msg": "hi"})
        assert r.status_code == 200
        body = r.json()
        assert body["discovered"]["address"] == "http://127.0.0.1:9999"
        assert body["server_response"]["ack"] == "received: hi"


def test_run_discover_failure(monkeypatch):
    def fake_get(url, timeout=None):
        class R:
            status_code = 404
            def json(self):
                return {"error": "not found"}
        return R()

    monkeypatch.setattr("samples.client.httpx.get", fake_get)

    with TestClient(app) as client:
        r = client.post("/run", json={"msg": "hi"})
        assert r.status_code == 500
        body = r.json()
        assert body["stage"] == "discover"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_client.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'samples.client'`）

- [ ] **Step 3: 实现 client 服务**

创建 `samples/client.py`：

```python
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from samples.common import HOST, CLIENT_PORT, REGISTER_URL

app = FastAPI()


class RunReq(BaseModel):
    msg: str = "hello"


@app.post("/run")
def run(req: RunReq):
    try:
        r = httpx.get(f"{REGISTER_URL}/discover/server", timeout=3)
        if r.status_code != 200:
            return {"error": r.text, "stage": "discover"}
        discovered = r.json()
    except Exception as e:
        return {"error": str(e), "stage": "discover"}

    try:
        r = httpx.post(f"{discovered['address']}/data", json={"msg": req.msg}, timeout=3)
        if r.status_code != 200:
            return {"error": r.text, "stage": "call_server"}
        server_response = r.json()
    except Exception as e:
        return {"error": str(e), "stage": "call_server"}

    return {"discovered": discovered, "server_response": server_response}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=CLIENT_PORT)
```

注意：`/run` 失败时返回 dict（HTTP 200）而非 500？修正——测试断言 500。需用 `HTTPException` 或 Response。修正实现：失败时抛 `HTTPException(500, ...)`。下面 Step 3 替换为正确版本。

修正后的 `samples/client.py`（以此为准）：

```python
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from samples.common import HOST, CLIENT_PORT, REGISTER_URL

app = FastAPI()


class RunReq(BaseModel):
    msg: str = "hello"


@app.post("/run")
def run(req: RunReq):
    try:
        r = httpx.get(f"{REGISTER_URL}/discover/server", timeout=3)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail={"error": r.text, "stage": "discover"})
        discovered = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "stage": "discover"})

    try:
        r = httpx.post(f"{discovered['address']}/data", json={"msg": req.msg}, timeout=3)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail={"error": r.text, "stage": "call_server"})
        server_response = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "stage": "call_server"})

    return {"discovered": discovered, "server_response": server_response}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=CLIENT_PORT)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_client.py -v`
Expected: PASS（3 个测试全绿）

- [ ] **Step 5: 提交**

```bash
git add samples/client.py tests/test_client.py
git commit -m "feat: add client service with discover-and-call flow"
```

---

### Task 5: 集成测试 fixture（conftest.py）

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: `samples.common` 的端口/host 常量。
- Produces: session 级 autouse fixture `services`，在所有测试前启动三个真实 uvicorn 子进程并等待 health 就绪，测试结束后清理。集成测试无需手动起服务。

- [ ] **Step 1: 创建 conftest.py**

创建 `tests/conftest.py`：

```python
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
```

- [ ] **Step 2: 冒烟验证（临时测试）**

创建临时文件 `tests/test_smoke.py`：

```python
import httpx
from samples.common import REGISTER_URL, SERVER_URL, CLIENT_URL


def test_all_healthy():
    for url in (REGISTER_URL, SERVER_URL, CLIENT_URL):
        r = httpx.get(f"{url}/health", timeout=2)
        assert r.status_code == 200
```

- [ ] **Step 3: 运行冒烟测试**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS（三服务被 fixture 启动，health 全 200）

- [ ] **Step 4: 删除冒烟测试并提交**

删除 `tests/test_smoke.py`。

```bash
git add tests/conftest.py
git commit -m "test: add session fixture launching three real services"
```

---

### Task 6: 端到端集成测试

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: `tests/conftest.py` 的 `services` fixture（autouse，自动生效）；`samples.common` 的 URL 常量。
- Produces: 三个集成测试，验证 spec 第 5 节数据流的三段链路。

- [ ] **Step 1: 写集成测试**

创建 `tests/test_integration.py`：

```python
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
```

- [ ] **Step 2: 运行全部测试**

Run: `pytest -v`
Expected: PASS（单元测试 + 集成测试全绿；fixture 自动起三服务）

- [ ] **Step 3: 提交**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests for three-service flow"
```

---

### Task 7: GitHub Actions CI 工作流

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `requirements.txt`、`pytest`。
- Produces: CI 在 push/PR 时自动跑全部测试。

- [ ] **Step 1: 创建工作流文件**

创建 `.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest -v
```

- [ ] **Step 2: 本地验证工作流语法（可选）**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: 无异常输出。

- [ ] **Step 3: 提交**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow running pytest"
```

---

### Task 8: 端到端最终验证

**Files:** 无（仅验证）

- [ ] **Step 1: 全量测试**

Run: `pytest -v`
Expected: 所有测试通过（register 4 + server 3 + client 3 + 集成 3 = 13 个）。

- [ ] **Step 2: 确认 git 状态干净**

Run: `git status`
Expected: nothing to commit, working tree clean。

- [ ] **Step 3: 推送以触发 CI**

```bash
git push -u origin main
```

随后在 GitHub 仓库 Actions 页面确认 CI 运行通过。

---

## Self-Review 已完成

- **Spec 覆盖**：架构（Task 1-4）、数据流三段链路（Task 6 三个测试分别覆盖 server→register、client→register、client→server）、错误处理（register_self 重试 Task 3、client 结构化错误 Task 4）、测试策略（单元 + 集成 Task 2-6）、CI（Task 7）、项目结构（samples/ 布局 Task 1）均有对应任务。
- **占位符扫描**：无 TBD/TODO，每个步骤含具体代码。
- **类型一致性**：`register_self` 签名在 Task 3 定义与测试一致；`/run` 返回结构在 Task 4 契约与 Task 6 断言一致；端口常量来源统一为 `samples.common`。
