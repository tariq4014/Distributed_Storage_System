import argparse, random, threading
from typing import Dict, Any
from common import JsonSocket, log, striping_valid

users: Dict[str, Dict[str, Any]] = {}
disks: Dict[str, Dict[str, Any]] = {}
dsses: Dict[str, Dict[str, Any]] = {}

MANAGER_ROLE = "MANAGER"


def handle_message(jsock: JsonSocket, msg: Dict[str, Any], peer):
    mtype = msg.get("type")
    src = msg.get("from", {})
    payload = msg.get("payload", {})
    msg_id = msg.get("msg_id")

    log(MANAGER_ROLE, "RX", f"from={src} type={mtype} payload={payload}")

    def reply(status: str, reason: str = "", data: Dict[str, Any] = None):
        resp = {
            "in_reply_to": msg_id,
            "status": status,
            "reason": reason,
            "data": data or {},
        }
        jsock.send_json(resp, peer)
        log(MANAGER_ROLE, "TX", f"to={peer} status={status} reason={reason} data={resp['data']}")

    if not mtype:
        return reply("FAILURE", "missing type")

    if mtype == "register-user":
        name = payload.get("user_name") or src.get("name")
        if not name:
            return reply("FAILURE", "missing user_name")
        if name in users:
            return reply("FAILURE", "user already registered")
        users[name] = {
            "ip": src.get("ip"),
            "m_port": src.get("m_port"),
            "c_port": src.get("c_port"),
        }
        return reply("SUCCESS", data={"user_name": name})

    if mtype == "register-disk":
        dname = payload.get("disk_name") or src.get("name")
        if not dname:
            return reply("FAILURE", "missing disk_name")
        if dname in disks:
            return reply("FAILURE", "disk already registered")
        disks[dname] = {
            "ip": src.get("ip"),
            "m_port": src.get("m_port"),
            "c_port": src.get("c_port"),
            "state": "Free",
            "dss_name": None,
        }
        return reply("SUCCESS", data={"disk_name": dname})

    if mtype == "configure-dss":
        dss_name = payload.get("dss_name")
        n = int(payload.get("n", 0))
        su = int(payload.get("striping_unit", 0))
        if not dss_name:
            return reply("FAILURE", "missing dss_name")
        if dss_name in dsses:
            return reply("FAILURE", "dss_name already exists")
        if n < 3:
            return reply("FAILURE", "n must be >= 3")
        if not striping_valid(su):
            return reply("FAILURE", "striping_unit must be power of two in [128, 1048576]")
        free_disks = [d for d, meta in disks.items() if meta["state"] == "Free"]
        if len(free_disks) < n:
            return reply("FAILURE", "insufficient Free disks")
        chosen = random.sample(free_disks, n)

        chosen.sort()
        for d in chosen:
            disks[d]["state"] = "InDSS"
            disks[d]["dss_name"] = dss_name
        dsses[dss_name] = {
            "n": n,
            "striping_unit": su,
            "disks_ordered": chosen,
        }
        return reply("SUCCESS", data={"dss_name": dss_name, "n": n, "striping_unit": su, "disks": chosen})

    if mtype == "deregister-user":
        name = payload.get("user_name") or src.get("name")
        if name not in users:
            return reply("FAILURE", "user not found")
        del users[name]
        return reply("SUCCESS", data={"user_name": name})

    if mtype == "deregister-disk":
        dname = payload.get("disk_name") or src.get("name")
        meta = disks.get(dname)
        if not meta:
            return reply("FAILURE", "disk not found")
        if meta["state"] != "Free":
            return reply("FAILURE", "disk in DSS; cannot deregister")
        del disks[dname]
        return reply("SUCCESS", data={"disk_name": dname})

    return reply("FAILURE", f"unknown type: {mtype}")


def listener(jsock: JsonSocket):
    while True:
        msg, peer = jsock.recv_json()
        handle_message(jsock, msg, peer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("m_port", type=int)
    args = ap.parse_args()

    jsock = JsonSocket("0.0.0.0", args.m_port, "manager-m")
    log(MANAGER_ROLE, "INFO", f"listening on 0.0.0.0:{args.m_port}")

    t = threading.Thread(target=listener, args=(jsock,), daemon=True)
    t.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        log(MANAGER_ROLE, "INFO", "shutting down")

if __name__ == "__main__":
    main()