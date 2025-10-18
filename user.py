# user.py
#!/usr/bin/env python3
import argparse, os
from typing import Tuple, Dict, Any, List
from common import TextSocket, log, get_local_ip, parse_kv, build_fail, chunk_bytes, decode_layout

ROLE = "USER"

def ask_mgr(m_sock: TextSocket, mgr: Tuple[str,int], msg: str) -> Tuple[str, Dict[str,str], str]:
    m_sock.send_line(msg, mgr)
    log(ROLE, "TX", f"to={mgr} {msg}")
    while True:
        line, peer = m_sock.recv_line()
        log(ROLE, "RX", f"from={peer} {line}")
        parts = line.split()
        if not parts:
            continue
        status = parts[0]
        if status not in ("OK", "FAIL"):
            continue

        if status == "FAIL":
            # normal FAIL: parse key=val tokens
            return "FAIL", parse_kv(parts[1:]), line

        # status == "OK"
        # Join everything after OK so commas in payload aren't lost
        rest = " ".join(parts[1:])

        # Expect "data=..."
        if rest.startswith("data="):
            data = rest[len("data="):]

            # Special case: LS returns data=list=<big string with commas>
            if data.startswith("list="):
                return "OK", {"list": data[len("list="):]}, line

            # Otherwise, comma-separated k=v pairs (COPY/READ/etc.)
            out = {}
            for p in data.split(","):
                if "=" in p:
                    k, v = p.split("=", 1)
                    out[k] = v
            return "OK", out, line

        # OK without data
        return "OK", {}, line


def ask_disk(c_sock: TextSocket, addr: Tuple[str,int], msg: str) -> Tuple[str, Dict[str,str], str]:
    c_sock.send_line(msg, addr)
    log("USER->DISK", "TX", f"to={addr} {msg.splitlines()[0]}")
    line, peer = c_sock.recv_line()
    log("DISK->USER", "RX", f"from={peer} {line.splitlines()[0]}")
    parts = line.split()
    if not parts:
        return "FAIL", {"reason":"empty_response"}, line
    if parts[0] == "OK":
        kv = {}
        if len(parts) > 1:
            kv = parse_kv([x for x in parts[1:] if x.startswith("bytes=")])
        return "OK", kv, line
    else:
        return "FAIL", parse_kv(parts[1:]), line

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
    mgr = (args.manager_ip, args.manager_m_port)

    print("Commands:")
    print("  register-user")
    print("  configure-dss <name> <n> <su>")
    print("  ls")
    print("  copy <path> <owner>")
    print("  read <dss> <file> <out_path>")
    print("  disk-failure <dss>  (simulate + recover)")
    print("  decommission-dss <dss>")
    print("  deregister-user")
    print("  quit")

    while True:
        try:
            line = input(f"[{args.user_name}] enter command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); line = "quit"
        if not line: continue
        parts = line.split(); cmd = parts[0].lower()

        if cmd == "quit":
            break

        if cmd == "register-user":
            msg = f"REGISTER-USER user={args.user_name} ip={ip} m={args.m_port} c={args.c_port}"
            status, kv, raw = ask_mgr(m_sock, mgr, msg)
            if status != "OK": print(raw)
            continue
        if cmd == "configure-dss":
            if len(parts) != 4:
                print("usage: configure-dss <name> <n> <su>"); continue
            dss, n, su = parts[1], parts[2], parts[3]
            status, kv, raw = ask_mgr(m_sock, mgr, f"CONFIGURE-DSS dss={dss} n={n} su={su}")
            print(raw)
            continue


        if cmd == "ls":
            status, kv, raw = ask_mgr(m_sock, mgr, "LS")
            if status == "OK":
                print("\n--- LS ---")
                print(kv.get("list","(none)").replace("\\n","\n"))
                print("-----------\n")
            else:
                print(raw)
            continue

        if cmd == "copy":
            if len(parts) != 3:
                print("usage: copy <path> <owner>"); continue
            path, owner = parts[1], parts[2]
            if not os.path.exists(path):
                print("no such file"); continue
            data = open(path, "rb").read()

            # phase 1: get layout
            status, kv, raw = ask_mgr(m_sock, mgr, f"COPY file={os.path.basename(path)} size={len(data)} owner={owner}")
            if status != "OK":
                print(raw); continue
            dss = kv["dss"]; n = int(kv["n"]); su = int(kv["su"])
            layout = decode_layout(kv["layout"])
            stripes = chunk_bytes(data, su)

            # send STORE-STRIPE sequentially
            for i, chunk in enumerate(stripes):
                dn, ipd, cp = layout[i % n]
                payload = chunk.decode("utf-8", "ignore")
                msg = f"STORE-STRIPE file={os.path.basename(path)} stripe={i} total={len(stripes)} dss={dss} owner={owner}\n{payload}"
                status2, kv2, raw2 = ask_disk(c_sock, (ipd, cp), msg)
                if status2 != "OK":
                    print("disk error:", raw2); break

            # notify manager
            ask_mgr(m_sock, mgr, f"COPY-COMPLETE file={os.path.basename(path)} dss={dss} owner={owner} size={len(data)} stripes={len(stripes)}")
            print(f"copied {path} to DSS={dss} ({len(stripes)} stripes)")

            continue

        if cmd == "read":
            if len(parts) != 4:
                print("usage: read <dss> <file> <out_path>"); continue
            dss, fname, outp = parts[1], parts[2], parts[3]
            status, kv, raw = ask_mgr(m_sock, mgr, f"READ file={fname} dss={dss} owner={args.user_name}")
            if status != "OK":
                print(raw); continue
            n = int(kv["n"]); su = int(kv["su"]); layout = decode_layout(kv["layout"])
            stripes = int(kv.get("stripes","0")) or n  # crude fallback
            chunks: List[bytes] = []
            for i in range(stripes):
                dn, ipd, cp = layout[i % n]
                status2, kv2, raw2 = ask_disk(c_sock, (ipd, cp), f"READ-STRIPE file={fname} stripe={i}")
                if status2 != "OK":
                    print("disk read error:", raw2); break
                # payload follows after newline
                if "\n" in raw2:
                    _, payload = raw2.split("\n", 1)
                    chunks.append(payload.encode("utf-8","ignore"))
            open(outp, "wb").write(b"".join(chunks))
            ask_mgr(m_sock, mgr, f"READ-COMPLETE file={fname} dss={dss} owner={args.user_name}")
            print(f"read {fname} -> {outp}")
            continue

        if cmd == "disk-failure":
            if len(parts) != 2:
                print("usage: disk-failure <dss>"); continue
            dss = parts[1]
            status, kv, raw = ask_mgr(m_sock, mgr, f"DISK-FAILURE dss={dss}")
            if status != "OK": print(raw); continue
            layout = decode_layout(kv["layout"]); n = int(kv["n"])
            # Pick the first disk to fail & recover (demo)
            dn, ipd, cp = layout[0]
            ask_disk(c_sock, (ipd, cp), "SIMULATE-FAIL")
            # immediate recover
            ask_disk(c_sock, (ipd, cp), "RECOVER-FROM-FAIL")
            ask_mgr(m_sock, mgr, f"RECOVERY-COMPLETE dss={dss}")
            print(f"simulated failure+recovery on {dn}")
            continue

        if cmd == "decommission-dss":
            if len(parts) != 2:
                print("usage: decommission-dss <dss>"); continue
            dss = parts[1]
            # best-effort: just tell manager to drop metadata
            status, kv, raw = ask_mgr(m_sock, mgr, f"DECOMMISSION-DSS dss={dss}")
            print(raw)
            continue

        if cmd == "deregister-user":
            status, kv, raw = ask_mgr(m_sock, mgr, f"DEREGISTER-USER user={args.user_name}")
            print(raw)
            continue

        print("unknown command")

if __name__ == "__main__":
    main()
