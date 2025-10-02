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

    print("Commands: register-user | configure-dss <name> <n> <su> | deregister-user | quit")
    while True:
        try:
            line = input(f"[{args.user_name}] enter command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); line = "quit"
        if not line:
            continue
        parts = line.split()
        line = parts[0].lower()

        if line == "quit":
            break

        if line == "register-user":
            msg = f"REGISTER-USER user={args.user_name} ip={ip} m={args.m_port} c={args.c_port}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.user_name}", "TX", f"to={mgr} {msg}")
            continue

        if line == "configure-dss":
            parts = line.split()
            if len(parts) != 4:
                print("usage: configure-dss <dss-name> <n> <su>")
                continue
            dss, n, su = parts[1], parts[2], parts[3]
            msg = f"CONFIGURE-DSS user={args.user_name} dss={dss} n={n} su={su}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.user_name}", "TX", f"to={mgr} {msg}")
            continue

        if line == "deregister-user":
            msg = f"DEREGISTER-USER user={args.user_name}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.user_name}", "TX", f"to={mgr} {msg}")
            continue

        print("unknown command")

if __name__ == "__main__":
    main()
