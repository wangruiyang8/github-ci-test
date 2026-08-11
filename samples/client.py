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
