# Distributed Storage System over UDP Sockets

A distributed storage system (DSS) built in Python with raw UDP sockets. A file copied into the system is split into fixed-size stripes and distributed round-robin across a set of independent disk processes, then reassembled on read. Three process types — **manager**, **disk**, and **user** — coordinate entirely through a plain-text message protocol over `SOCK_DGRAM`, with no networking framework or RPC library.

Built for CSE 434 (Computer Networks), Arizona State University.

## Architecture

| Process | Role |
|---|---|
| `manager.py` | Central registry and coordinator. Tracks registered users and disks, configures DSS instances, allocates disks, stores file metadata, and hands out the disk layout for each copy/read operation. Never touches file data. |
| `disk.py` | Storage node. Listens on two UDP ports: an `m` port for manager traffic and a `c` port for the data path. Stores stripes keyed by `(file, stripe_index)` and can simulate failure and recovery. |
| `user.py` | Interactive client. Registers with the manager, configures a DSS, and drives copy/read operations by talking to the manager for metadata and directly to disks for data. |

Control traffic and data traffic are deliberately separated: the user asks the manager *where* the stripes go, then transfers them to the disks itself. The manager stays off the data path.

## Message Protocol

All messages are single UTF-8 lines of the form `COMMAND key=value key=value`, with replies of `OK data=...` or `FAIL reason=...`. Stripe payloads are appended after a newline following the header.

**User → Manager:** `REGISTER-USER`, `DEREGISTER-USER`, `CONFIGURE-DSS`, `LS`, `COPY`, `COPY-COMPLETE`, `READ`, `READ-COMPLETE`, `DISK-FAILURE`, `RECOVERY-COMPLETE`, `DECOMMISSION-DSS`

**Disk → Manager:** `REGISTER-DISK`, `DEREGISTER-DISK`

**User → Disk:** `STORE-STRIPE`, `READ-STRIPE`, `DELETE-FILE`, `SIMULATE-FAIL`, `RECOVER-FROM-FAIL`

Disk layouts are exchanged in a compact encoded form, `[disk@ip:port;disk@ip:port;...]`, so a user can address every disk in a DSS from a single reply.

### Configuration rules

- A DSS requires `n >= 3` disks, chosen at random from those currently in the `Free` state.
- The striping unit `su` must be a power of two between 128 and 1,048,576 bytes.
- A disk is `Free` or `InDSS`; a disk cannot be deregistered while it belongs to a DSS.
- Decommissioning a DSS releases its disks back to `Free` and drops its file metadata.

## Requirements

- Python 3.8 or newer (standard library only — `socket`, `threading`, `argparse`)
- Any Unix or Windows host; processes may run on one machine or across several

## Setup and Usage

Clone the repository:

```
git clone https://github.com/tariq4014/socketProject.git
cd socketProject
```

Start the manager, then one process per disk, then the user. Each process needs its own ports.

```
python manager.py <manager_m_port>
python disk.py <disk_name> <manager_ip> <manager_m_port> <m_port> <c_port>
python user.py <user_name> <manager_ip> <manager_m_port> <m_port> <c_port>
```

### Example session

Terminal 1 — manager:

```
python manager.py 5000
```

Terminals 2–4 — three disks:

```
python disk.py d1 127.0.0.1 5000 5101 5201
python disk.py d2 127.0.0.1 5000 5102 5202
python disk.py d3 127.0.0.1 5000 5103 5203
```

At each disk prompt:

```
register-disk
```

Terminal 5 — user:

```
python user.py alice 127.0.0.1 5000 5301 5401
```

At the user prompt:

```
register-user
configure-dss dss1 3 512
copy ./sample.txt alice
ls
read dss1 sample.txt ./out.txt
disk-failure dss1
decommission-dss dss1
```

`copy` splits `sample.txt` into 512-byte stripes and writes stripe *i* to disk *i mod n*. `read` requests each stripe in order and concatenates them into `out.txt`.

### User commands

| Command | Description |
|---|---|
| `register-user` | Register this client with the manager |
| `configure-dss <name> <n> <su>` | Create a DSS from `n` free disks with striping unit `su` |
| `ls` | List every DSS, its disks, and the files stored in it |
| `copy <path> <owner>` | Stripe a local file across the DSS |
| `read <dss> <file> <out_path>` | Reassemble a file from its stripes |
| `disk-failure <dss>` | Simulate a disk failure and recovery |
| `decommission-dss <dss>` | Tear down a DSS and free its disks |
| `deregister-user` | Remove this client from the manager |
| `quit` | Exit |

## Logging

Every process prints timestamped `RX`/`TX` lines showing the peer address and message, which makes the full exchange traceable across terminals during a demo:

```
[2025-04-02 14:31:07.412] [MANAGER RX] from=('127.0.0.1', 5301) cmd=CONFIGURE-DSS kv={'dss': 'dss1', 'n': '3', 'su': '512'}
[2025-04-02 14:31:07.413] [MANAGER TX] to=('127.0.0.1', 5301) OK data=dss=dss1,n=3,su=512,disks=[d1,d2,d3]
```

## Implementation Notes

- **UDP by design.** The assignment required datagram sockets, so ordering and delivery are handled at the application layer through explicit request/response pairs rather than by the transport.
- **Threading.** The manager runs a single daemon listener thread; each disk runs two, one per port, so control and data traffic never block each other.
- **Shared helpers.** `common.py` holds the socket wrapper, logging, validation (`is_power_of_two`, `striping_valid`), key-value parsing, and layout encode/decode used by all three roles.

## Known Limitations

- Stripes live in disk-process memory, so data does not survive a disk restart.
- Payloads are decoded as UTF-8, so the current transfer path is text-safe rather than byte-exact for arbitrary binary files.
- Failure handling simulates a disk going offline and coming back; it does not yet reconstruct lost stripes from parity.
- `COPY` targets the first configured DSS rather than one named by the user.

## Author

Tariq Alharbi (GitHub: [tariq4014](https://github.com/tariq4014))
