#!/usr/bin/env python3
"""Basic DFIR parser for Linux utmp/wtmp/btmp and Windows Security EVTX logs."""

import argparse
import csv
import datetime
import ipaddress
import json
import os
import struct
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict

# Linux utmp record layout (common on 64-bit Linux)
UTMP_STRUCT = struct.Struct("=h2xi32s4s32s256shhiii4i20s")

TYPE_MAP = {
    0: "EMPTY",
    1: "RUN_LVL",
    2: "BOOT_TIME",
    3: "NEW_TIME",
    4: "OLD_TIME",
    5: "INIT_PROCESS",
    6: "LOGIN_PROCESS",
    7: "USER_PROCESS",
    8: "DEAD_PROCESS",
    9: "ACCOUNTING",
}


def clean_text(raw):
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def decode_ip(a0, a1, a2, a3):
    if a0 == a1 == a2 == a3 == 0:
        return ""
    if a1 == 0 and a2 == 0 and a3 == 0:
        packed = struct.pack("!I", a0 & 0xFFFFFFFF)
        return str(ipaddress.IPv4Address(packed))
    packed = b"".join(struct.pack("!I", x & 0xFFFFFFFF) for x in (a0, a1, a2, a3))
    return str(ipaddress.IPv6Address(packed))


def parse_linux_records(path):
    records = []
    with open(path, "rb") as f:
        while True:
            chunk = f.read(UTMP_STRUCT.size)
            if len(chunk) < UTMP_STRUCT.size:
                break
            (
                ut_type,
                ut_pid,
                ut_line,
                _ut_id,
                ut_user,
                ut_host,
                _e_termination,
                _e_exit,
                _ut_session,
                tv_sec,
                _tv_usec,
                a0,
                a1,
                a2,
                a3,
                _unused,
            ) = UTMP_STRUCT.unpack(chunk)

            ts = int(tv_sec)
            readable = ""
            if ts > 0:
                readable = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            records.append(
                {
                    "source_os": "linux",
                    "type": TYPE_MAP.get(ut_type, f"UNKNOWN_{ut_type}"),
                    "user": clean_text(ut_user),
                    "pid": int(ut_pid),
                    "terminal": clean_text(ut_line),
                    "host": clean_text(ut_host),
                    "ip": decode_ip(a0, a1, a2, a3),
                    "timestamp": ts,
                    "time_readable": readable,
                }
            )
    return records


def strip_ns(tag):
    return tag.split("}", 1)[-1]


def parse_windows_evtx(path):
    """Parse 4624/4625 logon records from a Windows .evtx file using wevtutil."""
    cmd = [
        "wevtutil",
        "qe",
        path,
        "/lf:true",
        "/f:xml",
        "/q:*[System[(EventID=4624 or EventID=4625)]]",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("wevtutil not found. Windows parsing must be run on Windows.")

    if result.returncode != 0:
        raise SystemExit(
            "Failed to read Windows EVTX log. Ensure this runs on Windows with wevtutil available. "
            f"Details: {result.stderr.strip()}"
        )

    xml_text = "<Events>" + result.stdout + "</Events>"
    root = ET.fromstring(xml_text)

    records = []
    for event in root:
        if strip_ns(event.tag) != "Event":
            continue

        event_id = ""
        computer = ""
        timestamp_text = ""
        event_data = {}

        for child in event:
            name = strip_ns(child.tag)
            if name == "System":
                for sys_item in child:
                    sys_name = strip_ns(sys_item.tag)
                    if sys_name == "EventID":
                        event_id = (sys_item.text or "").strip()
                    elif sys_name == "Computer":
                        computer = (sys_item.text or "").strip()
                    elif sys_name == "TimeCreated":
                        timestamp_text = sys_item.attrib.get("SystemTime", "")
            elif name == "EventData":
                for data_item in child:
                    if strip_ns(data_item.tag) == "Data":
                        key = data_item.attrib.get("Name", "")
                        event_data[key] = (data_item.text or "").strip()

        user = event_data.get("TargetUserName") or event_data.get("SubjectUserName") or ""
        ip = event_data.get("IpAddress") or ""
        host = event_data.get("WorkstationName") or computer

        ts = 0
        readable = ""
        if timestamp_text:
            clean = timestamp_text.replace("Z", "+00:00")
            try:
                dt = datetime.datetime.fromisoformat(clean)
                ts = int(dt.timestamp())
                readable = dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                readable = timestamp_text

        event_type = "WINDOWS_LOGON_SUCCESS" if event_id == "4624" else "WINDOWS_LOGON_FAILURE"
        records.append(
            {
                "source_os": "windows",
                "type": event_type,
                "user": user,
                "pid": 0,
                "terminal": "",
                "host": host,
                "ip": ip,
                "timestamp": ts,
                "time_readable": readable,
            }
        )

    return records


def detect_anomalies(records):
    anomalies = []
    fail_counts = defaultdict(int)

    for r in records:
        ip = r.get("ip", "")
        user = r.get("user", "") or "<unknown>"

        if ip and ip != "-":
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_unspecified or ip_obj.is_reserved:
                    anomalies.append({"anomaly": "suspicious_ip", "details": f"Suspicious IP {ip}", "record": r})
            except ValueError:
                anomalies.append({"anomaly": "suspicious_ip", "details": f"Invalid IP {ip}", "record": r})

        if r.get("timestamp", 0) > 0:
            hour = datetime.datetime.fromtimestamp(r["timestamp"]).hour
            if hour < 6 or hour > 22:
                anomalies.append({"anomaly": "off_hours_login", "details": f"Login at hour {hour}", "record": r})

        is_failed = r.get("type") in ("LOGIN_PROCESS", "WINDOWS_LOGON_FAILURE")
        if is_failed:
            key = f"{user}|{ip or 'no_ip'}"
            fail_counts[key] += 1
            if fail_counts[key] >= 5:
                anomalies.append(
                    {
                        "anomaly": "repeated_failed_logins",
                        "details": f"{fail_counts[key]} failed logins for {key}",
                        "record": r,
                    }
                )

    return anomalies


def write_json(path, records, anomalies):
    data = {"records": records}
    if anomalies is not None:
        data["anomalies"] = anomalies
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_csv(path, records, anomalies):
    fields = ["source_os", "type", "user", "pid", "terminal", "host", "ip", "timestamp", "time_readable"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fields})

    if anomalies is not None:
        a_path = path + ".anomalies.csv"
        with open(a_path, "w", newline="", encoding="utf-8") as f:
            fields2 = ["anomaly", "details", "source_os", "user", "ip", "timestamp", "type", "host"]
            writer = csv.DictWriter(f, fieldnames=fields2)
            writer.writeheader()
            for a in anomalies:
                rec = a.get("record", {})
                writer.writerow(
                    {
                        "anomaly": a.get("anomaly", ""),
                        "details": a.get("details", ""),
                        "source_os": rec.get("source_os", ""),
                        "user": rec.get("user", ""),
                        "ip": rec.get("ip", ""),
                        "timestamp": rec.get("timestamp", ""),
                        "type": rec.get("type", ""),
                        "host": rec.get("host", ""),
                    }
                )


def main():
    parser = argparse.ArgumentParser(description="Simple Linux/Windows DFIR log parser")
    parser.add_argument("--input", required=True, help="Input log file path")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--format", required=True, choices=["csv", "json"], help="Output format")
    parser.add_argument("--os-type", choices=["auto", "linux", "windows"], default="auto", help="Log source OS")
    parser.add_argument("--anomaly-detect", action="store_true", help="Enable basic anomaly detection")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(f"Input does not exist: {args.input}")

    os_type = args.os_type
    if os_type == "auto":
        os_type = "windows" if args.input.lower().endswith(".evtx") else "linux"

    if os_type == "windows":
        records = parse_windows_evtx(args.input)
    else:
        records = parse_linux_records(args.input)

    anomalies = detect_anomalies(records) if args.anomaly_detect else None

    if args.format == "json":
        write_json(args.output, records, anomalies)
    else:
        write_csv(args.output, records, anomalies)

    print(f"Parsed {len(records)} records")
    if anomalies is not None:
        print(f"Detected {len(anomalies)} anomalies")


if __name__ == "__main__":
    main()
