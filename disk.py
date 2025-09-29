import argparse, threading
from common import TextSocket, log, get_local_ip

ROLE = "DISK"

def listen(name: str, tsock: TextSocket):
    while True:
        line, peer = tsock.recv_line()
        log(f"{ROLE} {name}", "RX", f"from={peer} {line}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("disk_name")
    ap.add_argument("manager_ip")
    ap.add_argument("manager_m_port", type=int)
    ap.add_argument("m_port", type=int)
    ap.add_argument("c_port", type=int)
    args = ap.parse_args()

    ip = get_local_ip()

    m_sock = TextSocket("0.0.0.0", args.m_port, f"disk-{args.disk_name}-m")
    c_sock = TextSocket("0.0.0.0", args.c_port, f"disk-{args.disk_name}-c")

    threading.Thread(target=listen, args=(args.disk_name, m_sock), daemon=True).start()
    threading.Thread(target=listen, args=(args.disk_name, c_sock), daemon=True).start()

    mgr = (args.manager_ip, args.manager_m_port)

    print("Commands: register-disk | deregister-disk | quit")
    while True:
        try:
            line = input(f"[{args.disk_name}] enter command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); line = "quit"
        if not line:
            continue

        if line == "quit":
            break

        if line == "register-disk":
            msg = f"REGISTER-DISK disk={args.disk_name} ip={ip} m={args.m_port} c={args.c_port}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.disk_name}", "TX", f"to={mgr} {msg}")
            continue

        if line == "deregister-disk":
            msg = f"DEREGISTER-DISK disk={args.disk_name}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.disk_name}", "TX", f"to={mgr} {msg}")
            continue

        print("unknown command")

if __name__ == "__main__":
    main()