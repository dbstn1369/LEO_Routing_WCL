"""
Regenerate Fig 2 (4-panel duration), Fig 3 (1x2 box), Fig 4 (4-panel rate)
from existing CSV outputs + saved pickles.
"""
import os
import sys
import pickle
import csv

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
from plots.plot_figures import plot_combined_4panel, plot_isl_comparison


def load_results_csv(filename):
    """Returns {alg: {(rate, dur): metric_dict}}."""
    results = {a: {} for a in cfg.ALGORITHMS_ALL}
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            alg = row['Algorithm']
            if alg not in results:
                results[alg] = {}
            r = float(row['Data Rate (Gbps)'])
            d = float(row['Duration (s)'])
            results[alg][(r, d)] = {
                'throughput': float(row['Throughput (Gbps)']),
                'packet_loss_rate': float(row['Packet Loss Rate (%)']),
                'avg_hop_count': float(row['Avg Hop Count']),
            }
    return results


OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# Load both scenarios
results_s1 = load_results_csv(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 'results_s1', 'performance_results_s1.csv'))
results_s2 = load_results_csv(os.path.join(OUT_DIR, 'performance_results.csv'))

print("[1/3] Generating Fig 2 (4-panel duration)...", flush=True)
plot_combined_4panel(results_s1, results_s2, x_type='duration',
                     metric_key='throughput', ylabel='Average Throughput (Gbps)',
                     xlabel='Data Transmission Duration (s)',
                     filename='fig2_combined_duration.eps', out_dir=OUT_DIR)

print("[2/3] Generating Fig 4 (4-panel rate)...", flush=True)
plot_combined_4panel(results_s1, results_s2, x_type='rate',
                     metric_key='throughput', ylabel='Average Throughput (Gbps)',
                     xlabel='Data Transmission Rate (Gbps)',
                     filename='fig4_combined_rate.eps', out_dir=OUT_DIR)

print("[3/3] Generating Fig 3 (combined box) using S2 paths...", flush=True)
with open(os.path.join(OUT_DIR, 'paths_graphs_s2.pkl'), 'rb') as f:
    s2_data = pickle.load(f)
plot_isl_comparison(s2_data['paths'], s2_data['graphs'], out_dir=OUT_DIR)

print("\nDone — figures saved to results/")
