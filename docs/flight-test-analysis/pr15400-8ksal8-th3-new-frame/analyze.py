#!/usr/bin/env python3

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt


AXES = "RPY"
COMMON_HEADERS = {
    "Firmware revision": "Betaflight 2026.6.0-alpha (919116fed) STM32F7X2",
    "Board information": "BEFH BETAFPVF722",
    "Craft name": "THIII+ Freestyle",
    "pid_type": "1",
    "adrcWC": "110,110,47",
    "adrcWO": "150,150,150",
    "adrc_b0_law": "1",
    "adrc_gyro_lpf_hz": "200",
    "P interval": "4",
    "dshot_bidir": "1",
    "rpm_filter_harmonics": "0",
}
PACK_HEADERS = {
    "2s": {
        "adrcB0": "4912,2947,1965",
        "adrc_hover_throttle": "50",
        "motor_output_limit": "100",
        "motorOutput": "48,2047",
        "frames": 266980,
    },
    "3s": {
        "adrcB0": "6560,3936,2624",
        "adrc_hover_throttle": "36",
        "motor_output_limit": "100",
        "motorOutput": "48,2047",
        "frames": 287464,
    },
    "4s": {
        "adrcB0": "7832,4699,3133",
        "adrc_hover_throttle": "32",
        "motor_output_limit": "85",
        "motorOutput": "48,1747",
        "frames": 312022,
    },
}


def pack_from_path(path: Path) -> str:
    match = re.search(r"_([234])s_", path.name)
    if not match:
        raise SystemExit(f"cannot determine pack from filename: {path.name}")
    return f"{match.group(1)}s"


def read_headers(path: Path, pack: str) -> dict[str, str]:
    with path.open(newline="") as source:
        rows = csv.reader(source, skipinitialspace=True)
        column_names = [value.strip() for value in next(rows)]
        if column_names != ["fieldname", "fieldvalue"]:
            raise SystemExit(f"unexpected header columns: {column_names!r}")
        headers = {row[0].strip(): row[1].strip() for row in rows if len(row) == 2}

    expected_headers = COMMON_HEADERS | {
        key: value for key, value in PACK_HEADERS[pack].items() if key != "frames"
    }
    for key, expected in expected_headers.items():
        actual = headers.get(key)
        if actual != expected:
            raise SystemExit(f"{pack} header mismatch for {key}: {actual!r} != {expected!r}")
    return headers


def read_main_frames(path: Path, expected_frames: int) -> dict[str, np.ndarray]:
    fields = [
        "time (us)",
        *[f"axis{term}[{axis}]" for term in "PIDF" for axis in range(3)],
        *[f"setpoint[{axis}]" for axis in range(4)],
        *[f"gyroADC[{axis}]" for axis in range(3)],
        *[f"debug[{index}]" for index in range(8)],
        *[f"motor[{index}]" for index in range(4)],
        "vbatLatest (V)",
        "flightModeFlags",
        "rxSignalReceived",
        "rxFlightChannelsValid",
    ]
    values = {field: [] for field in fields}

    with path.open(newline="") as source:
        for raw in csv.DictReader(source, skipinitialspace=True):
            loop_iteration = raw.get("loopIteration", "").strip()
            if not loop_iteration.isdigit():
                continue
            row = {key.strip(): str(value).strip() for key, value in raw.items() if key is not None}
            try:
                parsed = {field: float(row[field]) for field in fields}
            except (KeyError, ValueError) as error:
                raise SystemExit(f"invalid main frame near loop {loop_iteration}: {error}") from error
            for field, value in parsed.items():
                values[field].append(value)

    if len(values["time (us)"]) != expected_frames:
        raise SystemExit(
            f"unexpected main-frame count for {path.name}: "
            f"{len(values['time (us)'])} != {expected_frames}"
        )
    return {field: np.asarray(column) for field, column in values.items()}


def axis_matrix(data: dict[str, np.ndarray], prefix: str) -> np.ndarray:
    return np.column_stack([data[f"{prefix}[{axis}]"] for axis in range(3)])


def neutral_band_summary(
    time_s: np.ndarray, setpoint: np.ndarray, gyro: np.ndarray
) -> tuple[int, np.ndarray]:
    sample_rate = 1000.0
    uniform_time = np.arange(0.0, time_s[-1], 1.0 / sample_rate)
    uniform_setpoint = np.column_stack([
        np.interp(uniform_time, time_s, setpoint[:, axis]) for axis in range(3)
    ])
    uniform_gyro = np.column_stack([
        np.interp(uniform_time, time_s, gyro[:, axis]) for axis in range(3)
    ])
    residual = uniform_gyro - uniform_setpoint
    bandpass = butter(4, [20.0, 100.0], btype="bandpass", fs=sample_rate, output="sos")
    filtered = sosfiltfilt(bandpass, residual, axis=0)
    neutral = np.max(np.abs(uniform_setpoint), axis=1) <= 30.0

    window = 2000
    hop = 500
    rms_values = []
    for start in range(0, len(uniform_time) - window + 1, hop):
        stop = start + window
        if np.mean(neutral[start:stop]) < 0.9:
            continue
        rms_values.append(np.sqrt(np.mean(filtered[start:stop] ** 2, axis=0)))
    if not rms_values:
        raise SystemExit("no command-neutral spectral windows found")
    return len(rms_values), np.max(np.asarray(rms_values), axis=0)


def analyze_pair(csv_path: Path, headers_path: Path) -> list[str]:
    pack = pack_from_path(csv_path)
    if pack_from_path(headers_path) != pack:
        raise SystemExit(f"CSV/header pack mismatch: {csv_path.name} / {headers_path.name}")
    headers = read_headers(headers_path, pack)
    data = read_main_frames(csv_path, int(PACK_HEADERS[pack]["frames"]))
    time_s = (data["time (us)"] - data["time (us)"][0]) * 1e-6
    setpoint = axis_matrix(data, "setpoint")
    gyro = axis_matrix(data, "gyroADC")
    terms = {term: axis_matrix(data, f"axis{term}") for term in "PIDF"}
    axis_sum = sum(terms.values())
    debug = np.column_stack([data[f"debug[{index}]"] for index in range(8)])
    motors = np.column_stack([data[f"motor[{index}]"] for index in range(4)])
    modes = data["flightModeFlags"].astype(int)
    gate_open = debug[:, 7] > 0
    limits = np.asarray([500.0, 500.0, 400.0])

    first_gate = np.flatnonzero(gate_open)
    gate_open_s = time_s[first_gate[0]] if len(first_gate) else float("nan")
    gate_closures = int(np.sum(np.diff(gate_open.astype(np.int8)) < 0))
    invalid_rx = int(np.sum((data["rxSignalReceived"] == 0) | (data["rxFlightChannelsValid"] == 0)))

    motor_max = float(headers["motorOutput"].split(",")[1])
    exact_upper = np.any(motors >= motor_max, axis=1)
    rail_throttle = data["setpoint[3]"][exact_upper]
    neutral_windows, neutral_axis_rms = neutral_band_summary(time_s, setpoint, gyro)
    mode_counts = ", ".join(
        f"{mode}:{int(np.sum(modes == mode))}" for mode in np.unique(modes)
    )

    any_limit_hit = np.any(np.abs(axis_sum) >= limits, axis=1)
    hit_indices = np.flatnonzero(any_limit_hit)
    terminal_limit_event = bool(
        len(hit_indices)
        and hit_indices[-1] == len(time_s) - 1
        and np.all(np.diff(hit_indices) == 1)
    )
    terminal_span_ms = (
        (time_s[-1] - time_s[hit_indices[0]]) * 1000.0
        if terminal_limit_event else 0.0
    )
    preterminal = time_s < time_s[-1] - 0.020

    lines = [
        f"=== {pack} ===",
        f"firmware={headers['Firmware revision']}",
        f"board={headers['Board information']} craft={headers['Craft name']}",
        f"tune wc={headers['adrcWC']} wo={headers['adrcWO']} b0={headers['adrcB0']} law={headers['adrc_b0_law']}",
        (
            f"config hover={headers['adrc_hover_throttle']} gyro_lpf={headers['adrc_gyro_lpf_hz']} "
            f"motor_limit={headers['motor_output_limit']} motor_output={headers['motorOutput']} "
            f"dshot_bidir={headers['dshot_bidir']} rpm_harmonics={headers['rpm_filter_harmonics']} "
            f"motor_kv={headers['motor_kv']}"
        ),
        f"frames={len(time_s)} duration_s={time_s[-1]:.6f} median_dt_us={np.median(np.diff(data['time (us)'])):.1f}",
        f"raw_mode_counts={mode_counts} feature_airmode={bool(int(headers['features']) & (1 << 22))}",
        f"invalid_rx_rows={invalid_rx}",
        f"gate_first_open_s={gate_open_s:.6f} gate_closures={gate_closures}",
    ]

    for axis, name in enumerate(AXES):
        error = np.abs(setpoint[:, axis] - gyro[:, axis])
        limit_hits = int(np.sum(np.abs(axis_sum[:, axis]) >= limits[axis]))
        preterminal_hits = int(np.sum(np.abs(axis_sum[preterminal, axis]) >= limits[axis]))
        lines.append(
            f"{name} tracking_med_p90={np.median(error):.1f}/{np.percentile(error, 90):.1f} "
            f"sum_abs_max={np.max(np.abs(axis_sum[:, axis])):.0f} sum_limit_hits={limit_hits} "
            f"preterminal20ms_sum_abs_max={np.max(np.abs(axis_sum[preterminal, axis])):.0f} "
            f"preterminal20ms_limit_hits={preterminal_hits}"
        )

    lines.append(
        f"terminal_limit_event={terminal_limit_event} frames={len(hit_indices) if terminal_limit_event else 0} "
        f"span_ms={terminal_span_ms:.3f}"
    )
    lines.append(
        f"motor_upper_rail={int(np.sum(exact_upper))}/{len(time_s)} "
        f"share_pct={np.mean(exact_upper) * 100:.4f} "
        f"rail_throttle_min_median_max={np.min(rail_throttle):.0f}/"
        f"{np.median(rail_throttle):.0f}/{np.max(rail_throttle):.0f}"
    )
    for name, index in zip(AXES, [2, 5, 6]):
        railed = np.abs(debug[:, index]) >= 32767.0
        lines.append(
            f"z3_{name}_rail={int(np.sum(railed))}/{len(time_s)} "
            f"share_pct={np.mean(railed) * 100:.4f}"
        )
    lines.append(
        f"neutral_windows={neutral_windows} "
        f"neutral_20_100hz_residual_rms_max_RPY="
        f"{neutral_axis_rms[0]:.4f}/{neutral_axis_rms[1]:.4f}/{neutral_axis_rms[2]:.4f} "
        f"max={np.max(neutral_axis_rms):.4f}"
    )
    lines.append(
        f"vbat_start_min_median_end={data['vbatLatest (V)'][0]:.2f}/"
        f"{np.min(data['vbatLatest (V)']):.2f}/"
        f"{np.median(data['vbatLatest (V)']):.2f}/"
        f"{data['vbatLatest (V)'][-1]:.2f}"
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair",
        nargs=2,
        action="append",
        metavar=("CSV", "HEADERS"),
        required=True,
        help="raw-flags decoded CSV and matching --save-headers CSV",
    )
    args = parser.parse_args()

    pairs = sorted(
        ((Path(csv_path), Path(headers_path)) for csv_path, headers_path in args.pair),
        key=lambda pair: pack_from_path(pair[0]),
    )
    if [pack_from_path(pair[0]) for pair in pairs] != ["2s", "3s", "4s"]:
        raise SystemExit("expected exactly one --pair for each of 2s, 3s and 4s")

    sections = [analyze_pair(csv_path, headers_path) for csv_path, headers_path in pairs]
    print("\n\n".join("\n".join(section) for section in sections))


if __name__ == "__main__":
    main()
