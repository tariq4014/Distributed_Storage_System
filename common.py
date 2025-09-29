import socket, time, sys, uuid
from typing import Tuple, Dict

BUF = 65535

class TextSocket:
    def __init__(self, bind_ip: str, bind_port: int, name: str):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind_ip, bind_port))
        self.name = name
        self.bind_ip = bind_ip
        self.bind_port = bind_port

    def send_line(self, line: str, addr: Tuple[str, int]):
        self.sock.sendto(line.encode("utf-8"), addr)

    def recv_line(self) -> Tuple[str, Tuple[str, int]]:
        data, addr = self.sock.recvfrom(BUF)
        return data.decode("utf-8").strip(), addr


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + f".{int((time.time()%1)*1000):03d}"

def log(role: str, direction: str, detail: str):
    print(f"[{now_ts()}] [{role} {direction}] {detail}")
    sys.stdout.flush()

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def striping_valid(x: int) -> bool:
    return 128 <= x <= 1048576 and is_power_of_two(x)

def parse_kv(parts) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in parts:
        if '=' in p:
            k, v = p.split('=', 1)
            out[k] = v
    return out

def build_ok(**kv) -> str:
    if kv:
        data = ",".join(f"{k}={v}" for k, v in kv.items())
        return f"OK data={data}"
    return "OK"

def build_fail(reason: str) -> str:
    return f"FAIL reason={reason.replace(' ', '_')}"

def new_msg_id() -> str:
    return uuid.uuid4().hex[:12]

