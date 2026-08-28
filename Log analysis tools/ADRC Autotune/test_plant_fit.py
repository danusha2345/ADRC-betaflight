import numpy as np
import pandas as pd
import pytest

import plant_fit


def input_frame(pid_sum_fields):
    data = {'time': [0, 1000], **pid_sum_fields}
    for i in range(3):
        data[f'setpoint[{i}]'] = [0, 1]
        data[f'gyroADC[{i}]'] = [0, 1]
    return pd.DataFrame(data)


def test_direct_pid_sum_uses_header_scale():
    fields = {f'adrcPidSum[{i}]': [10 * (i + 1), 20 * (i + 1)] for i in range(3)}
    df = input_frame(fields)
    _, _, _, u = plant_fit.get_axis_signals(
        df, 'pitch', {'adrc_pid_sum_scale': '10'})
    np.testing.assert_allclose(u, [2, 4])


def test_explorer_axis_sum_is_accepted_without_rescaling():
    fields = {f'axisSum[{i}]': [i + 1, 2 * (i + 1)] for i in range(3)}
    df = input_frame(fields)
    _, _, _, u = plant_fit.get_axis_signals(df, 'yaw', {})
    np.testing.assert_allclose(u, [3, 6])


def test_decoder_csv_time_and_header_sidecar_are_normalized(tmp_path):
    csv_path = tmp_path / 'flight.01.csv'
    csv_path.write_text(
        'loopIteration, time (us), setpoint[0], setpoint[1], setpoint[2], '
        'gyroADC[0], gyroADC[1], gyroADC[2], adrcPidSum[0], '
        'adrcPidSum[1], adrcPidSum[2]\n'
        '0, 1000, 0, 0, 0, 0, 0, 0, 10, 20, 30\n')
    sidecar = tmp_path / 'flight.01.headers.csv'
    sidecar.write_text('fieldname, fieldvalue\nadrc_pid_sum_scale, "10"\n')

    df = plant_fit.load_blackbox_csv(csv_path)
    hdr = plant_fit.read_blackbox_header(csv_path)
    assert 'time' in df.columns
    assert hdr['adrc_pid_sum_scale'] == '10'
    _, _, _, u = plant_fit.get_axis_signals(df, 'roll', hdr)
    np.testing.assert_allclose(u, [1])


def test_reconstructed_or_partial_pid_sum_fails_closed():
    df = input_frame({'adrcPidSum[0]': [1, 2]})
    with pytest.raises(ValueError, match='partial adrcPidSum'):
        plant_fit.blackbox_input_contract(df, {'adrc_pid_sum_scale': '10'}, True)

    df = input_frame({})
    with pytest.raises(ValueError, match=r'P\+I\+D\+F reconstruction'):
        plant_fit.blackbox_input_contract(df, {}, True)


def test_wc_ceiling_reports_paired_wo():
    wc, wo = plant_fit.paired_wc_wo({'wc_max': 75.0}, wc=50.0, wo=120.0)
    assert wc == 75.0
    assert wo == 180.0


def passing_gate_inputs():
    fit = {'n_bins': 20, 'wm_at_bound': False}
    bw_fit = {'pole_at_bound': False}
    bw = {
        'f_3db_hz': 12.0,
        'wc_max_at_bound': False,
        'wc_max_band_limited': False,
        'cfg_extrapolated': False,
        'pm_cfg': 50.0,
        'pm_target': 45.0,
        'cl_peak_db': 2.0,
    }
    estimates = [
        {'name': 'ctrl-free', 'value': 2000.0, 'sd': 100.0, 'independent': True},
        {'name': 'eRPM', 'value': 2100.0, 'sd': 100.0, 'independent': True},
    ]
    return fit, bw, bw_fit, estimates


def test_final_tune_gate_passes_only_complete_evidence():
    fit, bw, bw_fit, estimates = passing_gate_inputs()
    assert plant_fit.tune_validation_gate(fit, bw, bw_fit, estimates)['ok']


def test_final_tune_gate_blocks_extrapolation_and_method_disagreement():
    fit, bw, bw_fit, estimates = passing_gate_inputs()
    bw['cfg_extrapolated'] = True
    estimates[1].update(value=3200.0, sd=50.0)
    result = plant_fit.tune_validation_gate(fit, bw, bw_fit, estimates)
    assert not result['ok']
    assert any('outside the identified band' in reason for reason in result['reasons'])
    assert any('disagree beyond fit error' in reason for reason in result['reasons'])
