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
