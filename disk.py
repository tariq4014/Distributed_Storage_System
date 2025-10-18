# disk.py
#!/usr/bin/env python3
import argparse, threading
from typing import Dict, Tuple
from common import TextSocket, log, get_local_ip, parse_kv, build_ok, build_fail

ROLE = "DISK"

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
    mgr = (args.manager_ip, args.manager_m_port)

    # simple in-memory storage
    data_store: Dict[Tuple[str,int], bytes] = {}   # (file, stripe)->bytes
    failed = {"state": False}

    def listen_m():
        while True:
            line, peer = m_sock.recv_line()
            log(f"{ROLE} {args.disk_name}", "RX", f"from={peer} {line}")

    def listen_c():
        while True:
            line, peer = c_sock.recv_line()
            parts = line.split()
            cmd = parts[0].upper()
            kv = parse_kv(parts[1:])
            if failed["state"] and cmd not in ("RECOVER-FROM-FAIL",):
                c_sock.send_line(build_fail("disk_failed"), peer); continue

            if cmd == "STORE-STRIPE":
                # payload after first blank line OR after \n (we keep it simple: everything after header end)
                if "\n" in line:
                    header, payload = line.split("\n", 1)
                    stripe = int(kv["stripe"]); file = kv["file"]
                    data_store[(file, stripe)] = payload.encode("utf-8", "ignore")
                    c_sock.send_line(build_ok(), peer)
                else:
                    c_sock.send_line(build_fail("missing_payload"), peer)
                continue

            if cmd == "READ-STRIPE":
                file = kv["file"]; stripe = int(kv["stripe"])
                b = data_store.get((file, stripe))
                if b is None:
                    c_sock.send_line(build_fail("no_such_stripe"), peer)
                else:
                    c_sock.send_line(f"OK bytes={len(b)}\n"+b.decode("utf-8","ignore"), peer)
                continue

            if cmd == "DELETE-FILE":
                file = kv["file"]
                for k in [k for k in data_store.keys() if k[0]==file]:
                    del data_store[k]
                c_sock.send_line(build_ok(), peer)
                continue

            if cmd == "SIMULATE-FAIL":
                failed["state"] = True
                c_sock.send_line(build_ok(), peer)
                continue

            if cmd == "RECOVER-FROM-FAIL":
                failed["state"] = False
                c_sock.send_line(build_ok(), peer)
                continue

            c_sock.send_line(build_fail("unknown_command"), peer)

    threading.Thread(target=listen_m, daemon=True).start()
    threading.Thread(target=listen_c, daemon=True).start()

    print("Commands: register-disk | deregister-disk | quit")
    while True:
        try:
            line = input(f"[{args.disk_name}] enter command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); line = "quit"
        if not line: continue
        parts = line.split(); cmd = parts[0].lower()

        if cmd == "quit": break

        if cmd == "register-disk":
            msg = f"REGISTER-DISK disk={args.disk_name} ip={ip} m={args.m_port} c={args.c_port}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.disk_name}", "TX", f"to={mgr} {msg}")
            continue

        if cmd == "deregister-disk":
            msg = f"DEREGISTER-DISK disk={args.disk_name}"
            m_sock.send_line(msg, mgr)
            log(f"{ROLE} {args.disk_name}", "TX", f"to={mgr} {msg}")
            continue

        print("unknown command")

if __name__ == "__main__":
    main()
