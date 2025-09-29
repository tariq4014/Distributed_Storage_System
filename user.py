import argparse, threading
from common import TextSocket, log, get_local_ip

ROLE = "USER"

def listen(name: str, tsock: TextSocket):
    while True:
        line, peer = tsock.recv_line()
        log(f"{ROLE} {name}", "RX", f"from={peer} {line}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("user_name")
    ap.add_argument("manager_ip")
    ap.add_argument("manager_m_port", type=int)
    ap.add_argument("m_port", type=int)
    ap.add_argument("c_port", type=int)
    args = ap.parse_args()

    ip = get_local_ip()

    m_sock = TextSocket("0.0.0.0", args.m_port, f"user-{args.user_name}-m")
    c_sock = TextSocket("0.0.0.0", args.c_port, f"user-{args.user_name}-c")

    threading.Thread(target=listen, args=(args.user_name, m_sock), daemon=True).start()
    threading.Thread(target=listen, args=(args.user_name, c_sock), daemon=True).start()

    mgr = (args.manager_ip, args.manager_m_port)


if __name__ == "__main__":
    main()