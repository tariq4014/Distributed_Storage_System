import argparse, threading, random
from typing import Dict, Any, Tuple, List
from common import TextSocket, log, striping_valid, parse_kv, build_ok, build_fail, new_msg_id, encode_layout

users: Dict[str, Dict[str, Any]] = {}
disks: Dict[str, Dict[str, Any]] = {}
dsses: Dict[str, Dict[str, Any]] = {}
disk_addrs: Dict[str, Tuple[str, int]] = {}      
files: Dict[str, Dict[str, Dict[str, Any]]] = {}  
in_progress: Dict[str, Dict[str, Any]] = {}       

MANAGER_ROLE = "MANAGER"

def handle_line(tsock: TextSocket, line: str, peer: Tuple[str, int]):
    if not line:
        return
    parts = line.split()
    cmd = parts[0].upper() 
    kv = parse_kv(parts[1:])     
    log(MANAGER_ROLE, "RX", f"from={peer} cmd={cmd} kv={kv}")

    def reply(text: str):
        tsock.send_line(text, peer)
        log(MANAGER_ROLE, "TX", f"to={peer} {text}")

    if cmd == "REGISTER-USER":
        name = kv.get("user")
        if not name:
            return reply(build_fail("missing_user"))
        if name in users:
            return reply(build_fail("user_exists"))
        users[name] = {"ip": kv.get("ip"), "m": int(kv.get("m", 0)), "c": int(kv.get("c", 0))}
        return reply(build_ok(user=name))

    if cmd == "REGISTER-DISK":
        d = kv.get("disk")
        if not d:
            return reply(build_fail("missing_disk"))
        if d in disks:
            return reply(build_fail("disk_exists"))
        ip = kv.get("ip"); m = int(kv.get("m", 0)); c = int(kv.get("c", 0))
        disks[d] = {"ip": ip, "m": m, "c": c, "state": "Free", "dss": None}
        disk_addrs[d] = (ip, c)
        return reply(build_ok(disk=d))

    if cmd == "CONFIGURE-DSS":
        dss = kv.get("dss")
        try:
            n = int(kv.get("n", "0"))
            su = int(kv.get("su", "0"))
        except ValueError:
            return reply(build_fail("bad_n_or_su"))
        if not dss:
            return reply(build_fail("missing_dss"))
        if dss in dsses:
            return reply(build_fail("dss_exists"))
        if n < 3:
            return reply(build_fail("n_lt_3"))
        if not striping_valid(su):
            return reply(build_fail("invalid_striping_unit"))
        free = [d for d, meta in disks.items() if meta["state"] == "Free"]
        if len(free) < n:
            return reply(build_fail("insufficient_Free_disks"))
        chosen = sorted(random.sample(free, n))
        for d in chosen:
            disks[d]["state"] = "InDSS"
            disks[d]["dss"] = dss
        dsses[dss] = {"n": n, "su": su, "disks": chosen}
        return reply(build_ok(dss=dss, n=n, su=su, disks="[" + ",".join(chosen) + "]"))

    if cmd == "DEREGISTER-USER":
        name = kv.get("user")
        if name not in users:
            return reply(build_fail("user_not_found"))
        del users[name]
        return reply(build_ok(user=name))

    if cmd == "DEREGISTER-DISK":
        d = kv.get("disk")
        meta = disks.get(d)
        if not meta:
            return reply(build_fail("disk_not_found"))
        if meta["state"] != "Free":
            return reply(build_fail("disk_in_DSS"))
        del disks[d]
        return reply(build_ok(disk=d))

    return reply(build_fail("unknown_command"))

def list_summary() -> str:
    lines: List[str] = []
    for dss, info in dsses.items():
        arr = ",".join(info["disks"])
        lines.append(f"{dss}: n={info['n']} ({arr}) su={info['su']}")
        for fname, meta in files.get(dss, {}).items():
            lines.append(f"  {fname} size={meta['size']} owner={meta['owner']}")
    return "\\n".join(lines) if lines else "(empty)"

def listener(tsock: TextSocket):
    while True:
        try:
            line, peer = tsock.recv_line()
            handle_line(tsock, line, peer)
        except Exception as e:
            log(MANAGER_ROLE, "ERROR", f"listener error: {e!r}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("m_port", type=int)
    args = ap.parse_args()

    tsock = TextSocket("0.0.0.0", args.m_port, "manager-m")
    log(MANAGER_ROLE, "INFO", f"listening on 0.0.0.0:{args.m_port}")

    t = threading.Thread(target=listener, args=(tsock,), daemon=True)
    t.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        log(MANAGER_ROLE, "INFO", "shutting down")

if __name__ == "__main__":
    main()