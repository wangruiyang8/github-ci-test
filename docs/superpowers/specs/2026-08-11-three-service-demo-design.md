# 三服务联调 Demo 设计

- **日期**: 2026-08-11
- **状态**: 已批准
- **目的**: 在新建仓库中提供一个可被 GitHub CI 验证部署的 demo，三个服务在环境中分别监听独立端口并完成"注册 → 发现 → 调用"的端到端流程。

## 1. 目标与非目标

### 目标
- 三个独立服务（register / server / client）各自在真实端口上监听。
- server 启动时向 register POST 自己的地址（服务注册）。
- client 向 register GET 发现 server 地址（服务发现）。
- client 向 server POST 发送数据（业务调用）。
- GitHub CI 通过集成测试自动验证上述三段链路联调成功。

### 非目标
- 不做 Docker 容器化与镜像推送。
- 不做持久化存储（register 用内存 dict）。
- 不做鉴权 / TLS / 生产级容错。

## 2. 技术栈

- Python 3.11
- FastAPI + uvicorn（三个服务各自独立进程）
- httpx（跨服务 HTTP 调用）
- pytest + subprocess.Popen（集成测试启动三服务并断言）

## 3. 架构与组件

三个独立 FastAPI 应用，各自用 uvicorn 监听真实端口：

| 服务 | 默认端口 | 职责 |
|---|---|---|
| **register** | 8001 | 服务发现 registry。内存 dict 存 `{name: address}`。暴露 `POST /register`、`GET /discover/{name}`、`GET /health`。 |
| **server** | 8002 | 启动时向 register POST 自己地址（带重试）；暴露 `POST /data`（接收 payload 返回 ack）、`GET /health`。 |
| **client** | 8003 | 暴露 `POST /run`：先 GET register 发现 server，再 POST server，返回合并结果；`GET /health`。 |

端口与各服务 URL 通过环境变量配置（默认 `localhost:8001/8002/8003`），方便 CI 与本地调整。

## 4. 项目结构

```
github-ci-test/
  samples/
    common.py        # 端口/URL 配置常量
    register.py      # register FastAPI app
    server.py        # server FastAPI app
    client.py        # client FastAPI app
  tests/
    conftest.py      # session 级 fixture，subprocess 启动三服务
    test_integration.py
  requirements.txt   # fastapi, uvicorn, httpx, pytest
  .github/workflows/ci.yml
```

## 5. 数据流

1. register 启动 → `/health` 返回 200。
2. server 启动 → 在 FastAPI lifespan startup 事件中 `POST /register` body `{name:"server", address:"http://localhost:8002"}`（带重试，等 register 就绪）→ `/health` 返回 200。注册逻辑内嵌于 server 进程，无需外部脚本触发。
3. client 启动 → `/health` 返回 200（不主动调用，等被触发）。
4. 测试触发 `POST client/run`：
   - client `GET register/discover/server` → 拿到 server 地址。
   - client `POST {server_address}/data` body `{msg:"hello"}` → server 回 `{ack:"..."}`。
   - client 返回 `{discovered, server_response}`。

## 6. API 契约

### register
- `POST /register` — body `{name: str, address: str}` → `200 {ok: true}`，存入内存 dict。
- `GET /discover/{name}` → `200 {name, address}`，未找到返回 `404 {error: "not found"}`。
- `GET /health` → `200 {status:"ok"}`。

### server
- `POST /data` — body `{msg: str}` → `200 {ack: "received: <msg>"}`。
- `GET /health` → `200 {status:"ok"}`。

### client
- `POST /run` — body `{msg: str}`（可选，默认 `"hello"`）→ `200 {discovered: {name, address}, server_response: {ack}}`；失败时 `500 {error, stage}`。
- `GET /health` → `200 {status:"ok"}`。

## 7. 错误处理

- server 启动注册带指数退避重试（最多 5 次，间隔从 0.2s 起倍增），容忍 register 未就绪。
- 所有跨服务 httpx 调用设 3s 超时。
- client `/run` 失败时返回结构化错误 `{error, stage}`，`stage` 取值 `discover` / `call_server`，便于测试断言失败位置。
- 三个服务都有 `/health`，测试靠轮询 health 就绪而非固定 sleep。

## 8. 测试策略

### `tests/conftest.py`
- session 级 fixture `services`：用 `subprocess.Popen` 启动三个 uvicorn 进程（`python -m uvicorn samples.register:app --port 8001` 等）。
- 启动后轮询各服务 `/health`（最多 ~10s），全部就绪后 yield。
- 测试结束 terminate 三个进程并回收端口。

### `tests/test_integration.py`（sync httpx 打真实端口）
- `test_health`：三个服务 `/health` 都返回 200。
- `test_server_registered`：`GET register/discover/server` → 断言返回的 address 为 server 地址（验证 server→register POST 注册链路）。
- `test_client_run`：`POST client/run` → 断言 `discovered.address` 为 server 地址且 `server_response.ack` 含传入 msg（验证 client→register GET + client→server POST 链路）。

## 9. CI

`.github/workflows/ci.yml`：
- 触发：`push` 与 `pull_request` 到任意分支。
- runs-on: `ubuntu-latest`。
- 步骤：checkout → setup Python 3.11 → `pip install -r requirements.txt` → `pytest -v`。
- 集成测试本身负责起三服务，无需 CI 额外编排。
- 失败时 pytest 退出码非 0，CI 标红。

## 10. 依赖

`requirements.txt`：
```
fastapi
uvicorn[standard]
httpx
pytest
```
不锁定具体版本（demo 性质），CI 中 pip 拉最新兼容版。

## 11. 风险与权衡

- **端口冲突**：CI runner 上 8001/8002/8003 通常空闲；本地若占用需改环境变量。可接受。
- **进程清理**：subprocess 启动的 uvicorn 若 fixture teardown 不彻底可能残留。用 `proc.terminate()` + `proc.wait(timeout=5)`，超时再 `kill()`。
- **内存 registry 无持久化**：符合 demo 目标，重启即丢。可接受。
- **不锁版本**：CI 可能因上游 breaking change 失败。demo 性质可接受，必要时再锁。
