#!/usr/bin/env python3
"""Check that a FANUC controller (real or ROBOGUIDE) can be reached from this PC.

Run it before starting the ROS 2 driver. It checks:
  1. TCP port 16001 (RMI, needs the R912 option) accepts a connection.
  2. UDP port 60015 (Stream Motion, needs the J519 option) answers a
     controller-capability request, and prints the stream period and version.

Both probes are read-only. They send nothing that moves the robot.

    ros2 run fanuc_er4ia_moveit_config fanuc_connection_check.py 192.168.1.48
"""

import argparse
import socket
import struct
import sys

STOP, GET_CAP, VERSION = 2, 7, 3


def check_tcp(ip, port, timeout):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True, "connection accepted"
    except OSError as e:
        return False, str(e)


def check_udp(ip, port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.send(struct.pack(">II", STOP, VERSION))
        sock.send(struct.pack(">IIIIIII", GET_CAP, VERSION, 1, 0, 0, 0, 0))
        while True:
            data = sock.recv(1024)
            if len(data) >= 28 and struct.unpack(">I", data[:4])[0] == GET_CAP:
                _, _, _, period, _, version, _ = struct.unpack(">IIIIIII", data[:28])
                return True, f"Stream Motion version {version}, period {period} ms"
    except socket.timeout:
        return False, "no reply (blocked by a firewall, J519 missing, or wrong IP)"
    except OSError as e:
        return False, str(e)
    finally:
        sock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("robot_ip", help="controller IP, or the Windows PC running ROBOGUIDE")
    ap.add_argument("--rmi-port", type=int, default=16001)
    ap.add_argument("--stream-port", type=int, default=60015)
    ap.add_argument("--timeout", type=float, default=3.0)
    args, _ = ap.parse_known_args()  # ignore --ros-args when started with ros2 run

    ok_tcp, msg_tcp = check_tcp(args.robot_ip, args.rmi_port, args.timeout)
    print(f"[{'OK' if ok_tcp else 'FAIL'}] RMI TCP {args.robot_ip}:{args.rmi_port} - {msg_tcp}")
    ok_udp, msg_udp = check_udp(args.robot_ip, args.stream_port, args.timeout)
    print(f"[{'OK' if ok_udp else 'FAIL'}] Stream Motion UDP {args.robot_ip}:{args.stream_port} - {msg_udp}")

    if ok_tcp and ok_udp:
        print("Ready: start fanuc_er4ia.launch.py with use_mock:=false robot_ip:=" + args.robot_ip)
        return 0
    print("See docs/roboguide_setup.md sections 3, 4 and 7 (loopback setting, firewall, Wi-Fi isolation).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
