import os

HOST = os.getenv("HOST", "127.0.0.1")
REGISTER_PORT = int(os.getenv("REGISTER_PORT", "8001"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8002"))
CLIENT_PORT = int(os.getenv("CLIENT_PORT", "8003"))

REGISTER_URL = f"http://{HOST}:{REGISTER_PORT}"
SERVER_URL = f"http://{HOST}:{SERVER_PORT}"
CLIENT_URL = f"http://{HOST}:{CLIENT_PORT}"
