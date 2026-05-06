"""
Paper figure generation - IEEE WCL style.
Figures are sized at actual IEEE print dimensions so fonts render correctly.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import csv
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as cfg

# Match original style that produced good results
FONT_SIZE = 32  # unified font size for all labels

plt.rcParams.update({
    'font.family': 'Times New Roman',
    'font.size': FONT_SIZE,
    'axes.labelsize': FONT_SIZE,
    'xtick.labelsize': FONT_SIZE,
    'ytick.labelsize': FONT_SIZE,
    'legend.fontsize': FONT_SIZE - 4,
    'axes.grid': True,
    'figure.figsize': (9, 8),
})

MARKERS = ['o', 's', '^', 'D', 'v']
LINESTYLES = ['-', '--', '-.', ':', '-']
MARKER_SIZE = 12
LINE_WIDTH = 3

BOX_COLORS = {
    "Proposed": "#005EB8", "GRLR": "#FF7F0E",
    "DR": "#3CB44B", "STR": "#D62728"
}


def _save(fig, path):
    """Save as both EPS and PNG."""
    fig.savefig(path, format='eps', bbox_inches='tight')
    fig.savefig(path.replace('.eps', '.png'), format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print(f"  Saved: {path} (+png)", flush=True)


# ── Individual plots (single-column width) ──

def plot_vs_duration(results, fixed_rate, metric_key, ylabel, filename, out_dir='results'):
    fig, ax = plt.subplots()
    for i, alg in enumerate(cfg.ALGORITHMS):
        if alg not in results:
            continue
        values = [results[alg][(fixed_rate, dur)][metric_key] for dur in cfg.DURATIONS_S
                  if (fixed_rate, dur) in results[alg]]
        if len(values) == len(cfg.DURATIONS_S):
            ax.plot(cfg.DURATIONS_S, values,
                    marker=MARKERS[i % len(MARKERS)],
                    linestyle=LINESTYLES[i % len(LINESTYLES)],
                    markersize=MARKER_SIZE, linewidth=LINE_WIDTH,
                    label=alg)
    ax.set_xlabel('Data Transmission Duration (s)')
    ax.set_ylabel(ylabel)
    ax.legend(loc='best', framealpha=0.5)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, filename))


def plot_vs_rate(results, fixed_duration, metric_key, ylabel, filename, out_dir='results'):
    fig, ax = plt.subplots()
    for i, alg in enumerate(cfg.ALGORITHMS):
        if alg not in results:
            continue
        values = [results[alg][(rate, fixed_duration)][metric_key] for rate in cfg.DATA_RATES_GBPS
                  if (rate, fixed_duration) in results[alg]]
        if len(values) == len(cfg.DATA_RATES_GBPS):
            ax.plot(cfg.DATA_RATES_GBPS, values,
                    marker=MARKERS[i % len(MARKERS)],
                    linestyle=LINESTYLES[i % len(LINESTYLES)],
                    markersize=MARKER_SIZE, linewidth=LINE_WIDTH,
                    label=alg)
    ax.set_xlabel('Data Transmission Rate (Gbps)')
    ax.set_ylabel(ylabel)
    ax.legend(loc='best', framealpha=0.5)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, filename))


def generate_main_figures(results, out_dir='results'):
    os.makedirs(out_dir, exist_ok=True)
    fixed_rate = 2.8
    fixed_dur = 100

    plot_vs_duration(results, fixed_rate, 'throughput',
                     'Average Throughput (Gbps)', 'fig2a_throughput_duration.eps', out_dir)
    plot_vs_duration(results, fixed_rate, 'packet_loss_rate',
                     'Average Packet Loss Rate (%)', 'fig2b_plr_duration.eps', out_dir)
    plot_vs_rate(results, fixed_dur, 'throughput',
                 'Average Throughput (Gbps)', 'fig4a_throughput_rate.eps', out_dir)
    plot_vs_rate(results, fixed_dur, 'packet_loss_rate',
                 'Average Packet Loss Rate (%)', 'fig4b_plr_rate.eps', out_dir)


# ── 4-panel combined (double-column width) ──

def plot_combined_4panel(results_s1, results_s2, x_type, metric_key, ylabel,
                         xlabel, filename, out_dir='results'):
    """2x2 figure sized for single IEEE column (3.5in) so fonts stay readable."""
    fig, axes = plt.subplots(2, 2, figsize=(18, 16))

    fixed_rate = 2.8
    fixed_dur = 100

    panels = [
        (axes[0, 0], results_s1, 'throughput', 'Average Throughput (Gbps)', '(a) Scenario 1'),
        (axes[0, 1], results_s1, 'packet_loss_rate', 'Average Packet Loss Rate (%)', '(b) Scenario 1'),
        (axes[1, 0], results_s2, 'throughput', 'Average Throughput (Gbps)', '(c) Scenario 2'),
        (axes[1, 1], results_s2, 'packet_loss_rate', 'Average Packet Loss Rate (%)', '(d) Scenario 2'),
    ]

    for ax, res, mk, yl, title in panels:
        for i, alg in enumerate(cfg.ALGORITHMS):
            if alg not in res:
                continue
            if x_type == 'duration':
                xvals = cfg.DURATIONS_S
                values = [res[alg][(fixed_rate, d)][mk] for d in xvals
                          if (fixed_rate, d) in res[alg]]
            else:
                xvals = cfg.DATA_RATES_GBPS
                values = [res[alg][(r, fixed_dur)][mk] for r in xvals
                          if (r, fixed_dur) in res[alg]]
            if len(values) == len(xvals):
                ax.plot(xvals, values,
                        marker=MARKERS[i % len(MARKERS)],
                        linestyle=LINESTYLES[i % len(LINESTYLES)],
                        markersize=MARKER_SIZE, linewidth=LINE_WIDTH,
                        label=alg)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(yl)
        ax.legend(loc='best', framealpha=0.5)
        ax.grid(True)

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.45)
    # place subtitles after layout so positions are final
    for ax, _, _, _, title in panels:
        ax.text(0.5, -0.22, title, transform=ax.transAxes,
                ha='center', va='top', fontsize=FONT_SIZE)
    _save(fig, os.path.join(out_dir, filename))


# ── Box plots ──

def plot_isl_comparison(all_paths, graphs, out_dir='results'):
    """Box plots for ISL duration and SINR comparison."""
    os.makedirs(out_dir, exist_ok=True)

    alg_durations = {alg: [] for alg in cfg.ALGORITHMS}
    alg_sinrs = {alg: [] for alg in cfg.ALGORITHMS}

    for alg in cfg.ALGORITHMS:
        if alg not in all_paths:
            continue
        for cycle, path in all_paths[alg].items():
            if path is None or len(path) < 2:
                continue
            G = graphs.get(cycle)
            if G is None:
                continue
            durs, sinrs = [], []
            for u, v in zip(path[:-1], path[1:]):
                edge = G.get_edge_data(u, v)
                if edge is None:
                    edge = G.get_edge_data(v, u)
                if edge:
                    durs.append(edge['duration'])
                    sinrs.append(edge.get('sinr_db', 10*np.log10(max(edge.get('snr',10),1))))
            if durs:
                alg_durations[alg].append(np.mean(durs))
                alg_sinrs[alg].append(np.mean(sinrs))

    def _boxplot(data_dict, ylabel, save_name):
        order = [a for a in cfg.ALGORITHMS if data_dict[a]]
        data = [data_dict[a] for a in order]
        colors = [BOX_COLORS.get(a, '#999999') for a in order]

        fig, ax = plt.subplots()
        box = ax.boxplot(data, labels=order, patch_artist=True, showfliers=False)
        for patch, color in zip(box['boxes'], colors):
            patch.set(facecolor=color, alpha=0.9)
        for whisker, color in zip(box['whiskers'], np.repeat(colors, 2)):
            whisker.set(color=color, linewidth=3)
        for cap, color in zip(box['caps'], np.repeat(colors, 2)):
            cap.set(color=color, linewidth=3)
        for median in box['medians']:
            median.set(color='black', linewidth=3)

        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        _save(fig, os.path.join(out_dir, save_name))

    _boxplot(alg_durations, 'Average Duration (s)', 'fig3a_avg_duration.eps')
    _boxplot(alg_sinrs, 'Average SINR (dB)', 'fig3b_avg_sinr.eps')

    # Combined 1x2 box plot
    order = [a for a in cfg.ALGORITHMS if alg_durations[a]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    for ax, data_dict, yl, title in [
        (ax1, alg_durations, 'Average Duration (s)', '(a) Average Duration'),
        (ax2, alg_sinrs, 'Average SINR (dB)', '(b) Average SINR'),
    ]:
        data = [data_dict[a] for a in order]
        colors = [BOX_COLORS.get(a, '#999999') for a in order]
        box = ax.boxplot(data, labels=order, patch_artist=True, showfliers=False)
        for patch, color in zip(box['boxes'], colors):
            patch.set(facecolor=color, alpha=0.9)
        for whisker, color in zip(box['whiskers'], np.repeat(colors, 2)):
            whisker.set(color=color, linewidth=3)
        for cap, color in zip(box['caps'], np.repeat(colors, 2)):
            cap.set(color=color, linewidth=3)
        for median in box['medians']:
            median.set(color='black', linewidth=3)
        ax.set_ylabel(yl)
        ax.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    for ax, _, _, title in [
        (ax1, alg_durations, 'Average Duration (s)', '(a) Average Duration'),
        (ax2, alg_sinrs, 'Average SINR (dB)', '(b) Average SINR'),
    ]:
        ax.text(0.5, -0.12, title, transform=ax.transAxes,
                ha='center', va='top', fontsize=FONT_SIZE)
    _save(fig, os.path.join(out_dir, 'fig3_combined_box.eps'))


def save_sensitivity_csv(sensitivity_results, param_name, param_values, filename, out_dir='results'):
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([param_name, 'Throughput (Gbps)', 'Packet Loss Rate (%)', 'Avg Hop Count'])
        for v in param_values:
            m = sensitivity_results[v]
            writer.writerow([v, f"{m['throughput']:.6f}", f"{m['packet_loss_rate']:.4f}",
                           f"{m.get('avg_hop_count',0):.1f}"])
    print(f"  Saved: {filepath}", flush=True)
