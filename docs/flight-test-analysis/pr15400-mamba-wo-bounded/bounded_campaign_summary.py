#!/usr/bin/env python3
"""Recompute the restrained MAMBA wo-sweep summary from decoded Blackbox CSVs."""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CELLS = {
    "wo100": ("wo100-baseline-arm01.0[1-6].csv", 100, 750_000, "b9t750p30"),
    "wo125": ("wo125-arm01.0[1-4].csv", 125, 750_000, "b9t750p30"),
    "wo137": ("wo137-1000ms-arm01.0[1-3].csv", 137, 1_000_000, "b9t1000p30"),
    "wo150": ("wo150-arm01.0[1-4].csv", 150, 750_000, "b9t750p30"),
}


def read_headers(path: Path) -> dict[str, str]:
    with path.open(newline="") as handle:
        return {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        raw = list(csv.DictReader(handle, skipinitialspace=True))
    rows = []
    for row in raw:
        try:
            int((row.get("loopIteration") or "").strip())
        except ValueError:
            continue
        rows.append(row)
    return rows


def numbers(rows: list[dict[str, str]], field: str) -> list[float]:
    return [float(row[field].strip()) for row in rows]


def summarize_log(path: Path, expected_wo: int, firmware: str) -> dict[str, object]:
    rows = read_rows(path)
    headers = read_headers(path.with_name(path.name.replace(".csv", ".headers.csv")))
    assert headers["Firmware revision"].find(f"({firmware})") >= 0
    assert headers["Board information"] == "DIAT MAMBAF722_I2C"
    assert headers["pid_type"] == "1"
    assert headers["adrcWC"] == "60,60,60"
    assert headers["adrcWO"] == f"{expected_wo},{expected_wo},{expected_wo}"
    assert headers["adrcB0"] == "2000,2000,2000"
    assert headers["adrc_b0_law"] == "1"  # SQRT
    assert headers["dshot_bidir"] == "0"
    assert headers["P interval"] == "2"

    time_us = numbers(rows, "time (us)")
    pids = []
    for axis in range(3):
        pids.append([
            sum(float(row[f"axis{term}[{axis}]"].strip()) for term in "PIDF")
            for row in rows
        ])
    motors = [numbers(rows, f"motor[{axis}]") for axis in range(4)]
    setpoints = [numbers(rows, f"setpoint[{axis}]") for axis in range(3)]
    debug7 = numbers(rows, "debug[7]")
    rx_valid = sum(
        row["rxSignalReceived"].strip() == "1"
        and row["rxFlightChannelsValid"].strip() == "1"
        for row in rows
    )

    return {
        "file": path.name,
        "duration_us": int(time_us[-1] - time_us[0]),
        "pid_abs_max": [int(max(map(abs, values))) for values in pids],
        "setpoint_abs_max": [int(max(map(abs, values))) for values in setpoints],
        "motor_max": int(max(max(values) for values in motors)),
        "upper_rail_frames": sum(any(value >= 2047 for value in frame) for frame in zip(*motors)),
        "debug7_min": int(min(debug7)),
        "debug7_max": int(max(debug7)),
        "amps_max": max(numbers(rows, "amperageLatest (A)")),
        "rx_valid_rows": rx_valid,
        "rows": len(rows),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    campaign: dict[str, dict[str, object]] = {}
    for name, (pattern, wo, deadline_us, firmware) in CELLS.items():
        paths = [Path(value) for value in sorted(glob.glob(str(ROOT / pattern)))]
        assert paths, f"No CSV files for {name}"
        logs = [summarize_log(path, wo, firmware) for path in paths]
        campaign[name] = {
            "wo": wo,
            "deadline_us": deadline_us,
            "firmware": firmware,
            "logs": logs,
        }

    # The wo100/wo125 runs all ended at the 750 ms firmware deadline. Their
    # decoded data windows establish the stable Blackbox header-write offset.
    baseline_durations = [
        log["duration_us"]
        for name in ("wo100", "wo125")
        for log in campaign[name]["logs"]
    ]
    header_delay_us = round(750_000 - statistics.median(baseline_durations))

    for cell in campaign.values():
        expected_window = cell["deadline_us"] - header_delay_us
        for log in cell["logs"]:
            early = log["duration_us"] < expected_window - 5_000
            pid_peak = max(log["pid_abs_max"])
            if not early and abs(log["duration_us"] - expected_window) <= 5_000:
                termination = "deadline_like"
            elif early and pid_peak >= 285:
                termination = "pid_cutoff_like"
            elif early:
                termination = "ambiguous_early"
            else:
                termination = "other"
            log["termination"] = termination

        logs = cell["logs"]
        cell["summary"] = {
            "arms": len(logs),
            "termination_counts": {
                key: sum(log["termination"] == key for log in logs)
                for key in ("deadline_like", "pid_cutoff_like", "ambiguous_early", "other")
            },
            "yaw_pid_abs_max": [log["pid_abs_max"][2] for log in logs],
            "motor_max": [log["motor_max"] for log in logs],
            "amps_max": [log["amps_max"] for log in logs],
            "upper_rail_frames": sum(log["upper_rail_frames"] for log in logs),
            "all_zero_setpoint": all(max(log["setpoint_abs_max"]) == 0 for log in logs),
            "all_gate_marker_closed": all(log["debug7_max"] < 0 for log in logs),
            "rx_valid_fraction": sum(log["rx_valid_rows"] for log in logs) / sum(log["rows"] for log in logs),
        }

    expected_counts = {
        "wo100": {"deadline_like": 6, "pid_cutoff_like": 0, "ambiguous_early": 0, "other": 0},
        "wo125": {"deadline_like": 4, "pid_cutoff_like": 0, "ambiguous_early": 0, "other": 0},
        "wo137": {"deadline_like": 1, "pid_cutoff_like": 1, "ambiguous_early": 1, "other": 0},
        "wo150": {"deadline_like": 0, "pid_cutoff_like": 4, "ambiguous_early": 0, "other": 0},
    }
    for name, expected in expected_counts.items():
        assert campaign[name]["summary"]["termination_counts"] == expected
        assert campaign[name]["summary"]["upper_rail_frames"] == 0
        assert campaign[name]["summary"]["all_zero_setpoint"]
        assert campaign[name]["summary"]["all_gate_marker_closed"]

    raw_files = sorted(ROOT.glob("*.bbl"))
    result = {
        "blackbox_header_delay_estimate_us": header_delay_us,
        "campaign": campaign,
        "raw_sha256": {path.name: sha256(path) for path in raw_files},
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
