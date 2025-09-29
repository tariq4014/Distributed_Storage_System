import argparse, threading
from common import TextSocket, log, get_local_ip

ROLE = "USER"

def listen(name: str, tsock: TextSocket):
    while True:
        line, peer = tsock.recv_line()
        log(f"{ROLE} {name}", "RX", f"from={peer} {line}")
