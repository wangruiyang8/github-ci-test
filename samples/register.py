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
