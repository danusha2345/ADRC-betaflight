#!/usr/bin/env python3
"""Corpus-level facts about @8ksal8's logs: size, duration, write rate, clean end, FC identity.

Reproduces the inventory table in ANALYSIS.md section 2. Decoding is delegated to the
pinned decoder with the same flags used everywhere else in this repo.

Usage: python3 corpus_probe.py <decoder> <dir-with-bbl-files> [...]
"""

import json
import os
import re
import subprocess
import sys

DECODE_FLAGS = ["--unit-acceleration", "g", "--unit-frame-time", "us", "--save-headers"]


def header_field(path, name):
    with open(path, "rb") as f:
        blob = f.read(6000)
    m = re.search(rb"H " + name.encode() + rb":([^\x0a]*)", blob)
    return m.group(1).decode(errors="replace").strip() if m else "?"


def main(decoder, dirs):
    rows = []
    for d in dirs:
        for root, _, files in os.walk(d):
            for fn in sorted(files):
                if not fn.lower().endswith(".bbl"):
                    continue
                path = os.path.join(root, fn)
                res = subprocess.run([decoder] + DECODE_FLAGS + [path],
                                     capture_output=True, text=True)
                if res.returncode != 0:
                    sys.exit(f"decoder failed on {path} (rc={res.returncode}):\n{res.stderr}")
                out = res.stdout + res.stderr
                dur = re.search(r"duration (\d+):(\d+)\.(\d+)", out)
                seconds = (int(dur.group(1)) * 60 + int(dur.group(2))
                           + int(dur.group(3)) / 1000.0) if dur else float("nan")
                logs = re.search(r"Log (\d+) of (\d+)", out)
                unreadable = re.search(r"rendering (\d+) loop iterations unreadable", out)
                ev = os.path.splitext(path)[0] + ".01.event"
                events = []
                if os.path.exists(ev):
                    with open(ev) as f:
                        events = [json.loads(line)["name"] for line in f if line.strip()]
                rows.append(dict(
                    name=os.path.splitext(fn)[0],
                    size=os.path.getsize(path),
                    seconds=seconds,
                    logs=f"{logs.group(1)}/{logs.group(2)}" if logs else "?",
                    clean="Log clean end" in events,
                    unreadable=int(unreadable.group(1)) if unreadable else -1,
                    uid=header_field(path, "DeviceUID"),
                    craft=header_field(path, "Craft name"),
                    fw=(re.search(r"\(([0-9a-f]+)\)", header_field(path, "Firmware revision"))
                        or [None, "?"])[1],
                ))

    rows.sort(key=lambda r: r["size"])
    print(f"{'log':26s} {'bytes':>10s} {'MiB':>7s} {'sec':>8s} {'kB/s':>6s} "
          f"{'logs':>5s} {'clean':>5s} {'unread/s':>8s}")
    for r in rows:
        print(f"{r['name']:26s} {r['size']:10d} {r['size']/1048576:7.3f} {r['seconds']:8.3f} "
              f"{r['size']/r['seconds']/1000:6.2f} {r['logs']:>5s} "
              f"{'yes' if r['clean'] else 'NO':>5s} {r['unreadable']/r['seconds']:8.3f}")

    print(f"\nrate band: {min(r['size']/r['seconds'] for r in rows)/1000:.2f}"
          f"–{max(r['size']/r['seconds'] for r in rows)/1000:.2f} kB/s")
    print(f"distinct DeviceUID: {sorted({r['uid'] for r in rows})}")
    print(f"distinct craft:     {sorted({r['craft'] for r in rows})}")
    print(f"distinct firmware:  {sorted({r['fw'] for r in rows})}")
    print(f"16.00 MiB exactly:  {[r['name'] for r in rows if r['size'] == 16777216]}")


main(sys.argv[1], sys.argv[2:])
