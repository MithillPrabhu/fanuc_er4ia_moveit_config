#!/usr/bin/env python3
"""Minimal stand-in for a FANUC controller's RMI + Stream Motion interfaces.

Use this to test the full ROS 2 -> fanuc_hardware_interface -> network path
without ROBOGUIDE or a real robot. It answers the requests the FANUC ROS 2 driver
makes:

  * RMI over TCP (default port 16001, then a session port 16002), JSON
    packets ending in CRLF: FRC_Connect_STMO, FRC_GetStatus, FRC_Reset,
    FRC_Initialize, FRC_Abort, FRC_SetPayloadID, FRC_Call, FRC_Disconnect.
  * Stream Motion over UDP (default port 60015), big-endian packets: stop,
    controller capability, joint thresholds, GPIO config, start and command.
    It replies to each command with a robot status packet.

The emulated robot follows the commanded joint angles exactly. There are no
dynamics, safety checks or alarms, and it doesn't emulate I/O. This script is
NOT FANUC software and is no substitute for testing in ROBOGUIDE.

    python3 fanuc_controller_emulator.py                 # listen on all interfaces
    ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py \
        use_mock:=false robot_ip:=127.0.0.1
"""

import argparse
import json
import socket
import struct
import threading
import time

AXES = 9
IO_BYTES = 256

# Stream Motion packet types
STOP, THRESHOLD, GET_CAP, SET_CAP = 2, 3, 7, 8
START, COMMAND, GPIO_CFG, STATUS, FS_CFG = 200, 201, 203, 204, 205

STATUS_FMT = ">III BBBB I 9f 9f 9f f 6f I 256s"   # RobotStatusPacket (v4+)
COMMAND_FMT = ">III BBH 9d 256s"                    # CommandPacket
THRESH_REQ_FMT = ">IIII"
THRESH_RES_FMT = ">IIIIII20f20f"
CAP_FMT = ">IIIIIII"
GPIO_RES_FMT = ">III"


class Robot:
    def __init__(self, home_deg):
        self.joints = list(home_deg) + [0.0] * (AXES - len(home_deg))
        self.lock = threading.Lock()


# ----------------------------------------------------------------------------- RMI
def rmi_reply(req, state):
    """Build the JSON reply for one RMI request (or None for no reply)."""
    if "Communication" in req:
        name = req["Communication"]
        if name in ("FRC_Connect_STMO", "FRC_Connect"):
            return {"Communication": name, "ErrorID": 0, "PortNumber": state["session_port"],
                    "MajorVersion": 1, "MinorVersion": 0}
        return {"Communication": name, "ErrorID": 0}
    if "Command" in req:
        name = req["Command"]
        if name == "FRC_GetStatus":
            return {"Command": name, "ErrorID": 0, "ServoReady": 1, "TPMode": 0,
                    "RMIMotionStatus": 0, "ProgramStatus": state["program_status"],
                    "SingleStepMode": 0, "NumberUTool": 1, "NextSequenceID": state["next_seq"],
                    "NumberUFrame": 0, "Override": 100}
        if name == "FRC_GetExtStatus":
            return {"Command": name, "ErrorID": 0, "InMotion": 0, "DrivesPowered": 1,
                    "GenOverride": 100}
        if name == "FRC_Initialize":
            state["program_status"] = 0
            state["next_seq"] = 1
            return {"Command": name, "ErrorID": 0, "GroupMask": req.get("GroupMask", 1)}
        if name == "FRC_Abort":
            state["program_status"] = 1
            return {"Command": name, "ErrorID": 0}
        return {"Command": name, "ErrorID": 0}
    if "Instruction" in req:
        # FRC_Call STREAM_MOTN keeps running while streaming, so the real
        # controller doesn't answer it right away. Other instructions are acknowledged.
        seq = req.get("SequenceID", 0)
        state["next_seq"] = seq + 1
        if req.get("ProgramName") == "STREAM_MOTN":
            return None
        return {"Instruction": req["Instruction"], "ErrorID": 0, "SequenceID": seq}
    return None


def serve_rmi_conn(conn, state, log):
    buf = b""
    with conn:
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                return
            if not data:
                return
            buf += data
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                if not line.strip():
                    continue
                try:
                    req = json.loads(line.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    log(f"RMI: bad JSON {line!r}")
                    continue
                log(f"RMI <- {req}")
                rep = rmi_reply(req, state)
                if rep is not None:
                    conn.sendall((json.dumps(rep) + "\r\n").encode())
                    log(f"RMI -> {rep}")


def rmi_listener(host, port, state, log):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(4)
    while True:
        conn, addr = srv.accept()
        log(f"RMI: connection on port {port} from {addr}")
        threading.Thread(target=serve_rmi_conn, args=(conn, state, log), daemon=True).start()


# ----------------------------------------------------------------------- Stream Motion
def stream_motion_server(host, port, robot, period_ms, version, log, verbose):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    seq = 0
    streaming = False
    t0 = time.monotonic()
    next_tick = time.monotonic()
    n_cmd = 0

    def status_packet():
        with robot.lock:
            j = robot.joints[:]
        ts = int((time.monotonic() - t0) * 1000) & 0xFFFFFFFF
        status_bits = 0x1  # ready for commands
        return struct.pack(STATUS_FMT, STATUS, version, seq, status_bits, 0, 0, 0, ts,
                           *([0.0] * AXES), *j, *([0.0] * AXES), 1.0,
                           0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0xFFFFFFFF, bytes(IO_BYTES))

    while True:
        data, addr = sock.recvfrom(65535)
        if len(data) < 8:
            continue
        ptype, _ver = struct.unpack(">II", data[:8])
        if ptype == STOP:
            if streaming:
                log(f"StreamMotion: stop after {n_cmd} commands")
            streaming = False
        elif ptype in (GET_CAP, SET_CAP):
            sock.sendto(struct.pack(CAP_FMT, ptype, version, 1, period_ms, 0, version, 0), addr)
            log(f"StreamMotion: capability -> period {period_ms} ms, version {version}")
        elif ptype == THRESHOLD:
            _, _, axis, ttype = struct.unpack(THRESH_REQ_FMT, data[:16])
            value = (720.0, 7200.0, 72000.0)[ttype] if ttype < 3 else 0.0
            sock.sendto(struct.pack(THRESH_RES_FMT, THRESHOLD, version, axis, ttype, 2000, 8,
                                    *([value] * 20), *([value] * 20)), addr)
        elif ptype == GPIO_CFG:
            sock.sendto(struct.pack(GPIO_RES_FMT, GPIO_CFG, 0, 0), addr)
            log("StreamMotion: GPIO configuration accepted")
        elif ptype == FS_CFG:
            pass  # no reply expected
        elif ptype == START:
            streaming = True
            seq = 1
            n_cmd = 0
            next_tick = time.monotonic()
            sock.sendto(status_packet(), addr)
            log("StreamMotion: start")
        elif ptype == COMMAND and streaming:
            f = struct.unpack(COMMAND_FMT, data[:struct.calcsize(COMMAND_FMT)])
            is_last, do_motn = f[3], f[4]
            cmd = f[6:6 + AXES]
            if do_motn:
                with robot.lock:
                    robot.joints = [float(c) for c in cmd]
            n_cmd += 1
            if verbose and n_cmd % 250 == 0:
                log("StreamMotion: joints " + " ".join(f"{v:7.2f}" for v in robot.joints[:6]))
            if is_last:
                streaming = False
                continue
            # Pace status packets at the controller period, like a real controller.
            next_tick += period_ms / 1000.0
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.monotonic()
            seq += 1
            sock.sendto(status_packet(), addr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--rmi-port", type=int, default=16001)
    ap.add_argument("--session-port", type=int, default=16002)
    ap.add_argument("--stream-port", type=int, default=60015)
    ap.add_argument("--period-ms", type=int, default=8)
    ap.add_argument("--version", type=int, default=4, help="Stream Motion version to report")
    ap.add_argument("--home", type=float, nargs=6, default=[0, 0, 0, 0, -90, 0],
                    metavar="DEG", help="initial joint angles J1..J6 in degrees")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    def log(msg):
        if args.verbose or not msg.startswith(("RMI <-", "RMI ->")):
            print(f"[emulator] {msg}", flush=True)

    robot = Robot(args.home)
    state = {"session_port": args.session_port, "program_status": 1, "next_seq": 1}
    for port in (args.rmi_port, args.session_port):
        threading.Thread(target=rmi_listener, args=(args.host, port, state, log), daemon=True).start()
    print(f"[emulator] RMI on TCP {args.rmi_port}/{args.session_port}, "
          f"Stream Motion on UDP {args.stream_port}, period {args.period_ms} ms", flush=True)
    try:
        stream_motion_server(args.host, args.stream_port, robot, args.period_ms, args.version,
                             log, args.verbose)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
