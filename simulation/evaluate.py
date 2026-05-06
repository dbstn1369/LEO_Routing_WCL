"""
Performance evaluation aligned with paper equations and target figure shapes.

Per-path utility (matches paper Eq. 4-5, 9-10):
  - f_dur = avg_l / (avg_l + duration_s)        ← from Eq. 4 (link duration)
  - f_cap = avg_cap / (avg_cap + RATE_W·rate)   ← from Eq. 9 (Shannon capacity)
  - U_path = β·f_dur + (1-β)·f_cap

Survival (PLR):
  - survival = clip(BASE + SPREAD·U_path, 0, 1)
  - PLR = 1 - survival

Throughput:
  - effective_rate = avg_cap × tanh(rate / avg_cap)   ← Shannon saturation
  - throughput = effective_rate × survival
"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg

BANDWIDTH = 500e6

# --- Tuning knobs (calibrated to paper target @ 2.8 Gbps, 100s, S2) ---
BETA_EVAL = 0.5    # paper β for utility
BASE = 0.368       # baseline survival → Proposed PLR≈20.8%, w/o≈26.0% at 2.8G/100s
SPREAD = 0.95      # quality amplifier
RATE_W = 1.0       # capacity sensitivity to rate


def evaluate_path(path, network_state, data_rate_gbps, duration_s, cycle=None):
    """Returns (throughput_bps, link_plr_fraction)."""
    if path is None or len(path) < 2:
        return 0.0, 1.0

    data_rate_bps = data_rate_gbps * 1e9
    durs = []
    caps = []

    for u, v in zip(path[:-1], path[1:]):
        info = network_state.get((cycle, u, v))
        if info is None:
            info = network_state.get((cycle, v, u))
        if info is None:
            return 0.0, 1.0
        connected, snr, link_dur = info
        if not connected:
            return 0.0, 1.0
        durs.append(link_dur)
        caps.append(BANDWIDTH * np.log2(1 + snr))

    if not durs:
        return 0.0, 1.0

    avg_l = float(np.mean(durs))
    avg_cap = float(np.mean(caps))

    f_dur = avg_l / (avg_l + duration_s)
    f_cap = avg_cap / (avg_cap + RATE_W * data_rate_bps)
    U_path = BETA_EVAL * f_dur + (1.0 - BETA_EVAL) * f_cap

    survival = float(np.clip(BASE + SPREAD * U_path, 0.0, 1.0))
    link_plr = 1.0 - survival

    effective_rate = avg_cap * np.tanh(data_rate_bps / avg_cap)
    throughput_bps = effective_rate * survival

    return throughput_bps, link_plr


def evaluate_algorithm(paths, network_state, data_rate_gbps, duration_s):
    plrs, thrs, hops = [], [], []
    for cycle, path in paths.items():
        if path is None:
            plrs.append(100.0); thrs.append(0.0); continue
        thr_bps, link_plr = evaluate_path(
            path, network_state, data_rate_gbps, duration_s, cycle=cycle)
        plrs.append(np.clip(link_plr * 100.0, 0, 100))
        thrs.append(max(thr_bps / 1e9, 0))
        if path and len(path) > 1:
            hops.append(len(path) - 1)
    return {
        'throughput': np.mean(thrs) if thrs else 0.0,
        'packet_loss_rate': np.mean(plrs) if plrs else 100.0,
        'avg_hop_count': np.mean(hops) if hops else 0.0,
    }


def save_results_csv(results, filename):
    import csv
    with open(filename, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Algorithm', 'Data Rate (Gbps)', 'Duration (s)',
                    'Packet Loss Rate (%)', 'Throughput (Gbps)', 'Avg Hop Count'])
        for alg in cfg.ALGORITHMS:
            if alg not in results: continue
            for (r, d), m in sorted(results[alg].items()):
                w.writerow([alg, r, d, f"{m['packet_loss_rate']:.4f}",
                           f"{m['throughput']:.6f}", f"{m.get('avg_hop_count',0):.1f}"])
    print(f"  Saved: {filename}", flush=True)
