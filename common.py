import json, socket, threading, time, uuid, sys
from typing import Tuple, Any

BUF = 65535

class JsonSocket:
    def __init__(self, bind_ip: str, bind_port: int, name: str):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind_ip, bind_port))
        self.name = name
        self.bind_ip = bind_ip
        self.bind_port = bind_port

    def send_json(self, obj: Any, addr: Tuple[str, int]):
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.sock.sendto(data, addr)

    def recv_json(self) -> Tuple[Any, Tuple[str, int]]:
        data, addr = self.sock.recvfrom(BUF)
        return json.loads(data.decode("utf-8")), addr


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + f".{int((time.time()%1)*1000):03d}"


def log(role: str, direction: str, detail: str):
    # direction: RX or TX
    print(f"[{now_ts()}] [{role} {direction}] {detail}")
    sys.stdout.flush()

    #testing