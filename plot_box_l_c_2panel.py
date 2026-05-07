"""
2-panel box plot showing the two ISL utility components from paper
Eq. (utility_components):
  (a) Average ISL Duration  l_ij (s)
  (b) Average ISL Capacity  c_ij = B * log2(1 + SINR)  (Gbps)
per algorithm (Proposed, GRLR, DR, STR).

Reads results/paths_graphs_s2.pkl. Output: results/fig3_combined_box_l_c.{eps,png}

This script is independent of plot_utility_box_3panel.py (kept intact for
rollback) and of plots/plot_figures.py.
"""
import os
import pickle
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg


FONT_SIZE = 32
plt.rcParams.update({
    'font.family': 'Times New Roman',
    'font.size': FONT_SIZE,
    'axes.labelsize': FONT_SIZE,
    'xtick.labelsize': FONT_SIZE,
    'ytick.labelsize': FONT_SIZE,
    'legend.fontsize': FONT_SIZE - 4,
    'axes.grid': True,
})

BOX_COLORS = {
    "Proposed": "#005EB8",
    "GRLR":     "#FF7F0E",
    "DR":       "#3CB44B",
    "STR":      "#D62728",
}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
PKL_PATH = os.path.join(OUT_DIR, 'paths_graphs_s2.pkl')


def collect_per_algorithm(paths, graphs):
    """Per-algorithm path-averaged duration (s) and capacity (Gbps)."""
    durations  = {a: [] for a in cfg.ALGORITHMS}
    capacities = {a: [] for a in cfg.ALGORITHMS}

    for alg in cfg.ALGORITHMS:
        if alg not in paths:
            continue
        for cycle, path in paths[alg].items():
            if path is None or len(path) < 2:
                continue
            G = graphs.get(cycle)
            if G is None:
                continue
            d_list, c_list = [], []
            for u, v in zip(path[:-1], path[1:]):
                edata = G.get_edge_data(u, v) or G.get_edge_data(v, u)
                if edata is None:
                    continue
                d_list.append(edata['duration'])
                # capacity stored as bits/sec (B * log2(1+SNR)) → convert to Gbps
                c_list.append(edata['capacity'] / 1e9)
            if d_list:
                durations[alg].append(float(np.mean(d_list)))
                capacities[alg].append(float(np.mean(c_list)))

    return durations, capacities


def style_box(ax, data_dict, order, ylabel):
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
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle='--', alpha=0.6)


def main():
    if not os.path.exists(PKL_PATH):
        print(f"ERROR: {PKL_PATH} not found. Run run_from_existing.py first.", flush=True)
        sys.exit(1)

    with open(PKL_PATH, 'rb') as f:
        data = pickle.load(f)
    paths = data['paths']
    graphs = data['graphs']

    durations, capacities = collect_per_algorithm(paths, graphs)

    order = [a for a in cfg.ALGORITHMS if durations.get(a)]
    print("Per-algorithm sample counts:", flush=True)
    for a in order:
        print(f"  {a:>10s}: dur={len(durations[a])}, cap={len(capacities[a])}", flush=True)
    print("\nMean values:")
    for a in order:
        print(f"  {a:>10s}: l_ij={np.mean(durations[a]):.2f} s, "
              f"c_ij={np.mean(capacities[a]):.3f} Gbps", flush=True)

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    panels = [
        (axes[0], durations,  r'Average ISL Duration $l_{ij}$ (s)',     '(a) Average ISL Duration'),
        (axes[1], capacities, r'Average ISL Capacity $c_{ij}$ (Gbps)',  '(b) Average ISL Capacity'),
    ]
    for ax, data_dict, yl, _title in panels:
        style_box(ax, data_dict, order, yl)

    plt.tight_layout()
    for ax, _, _, title in panels:
        ax.text(0.5, -0.18, title, transform=ax.transAxes,
                ha='center', va='top', fontsize=FONT_SIZE)

    eps_path = os.path.join(OUT_DIR, 'fig3_combined_box_l_c.eps')
    png_path = os.path.join(OUT_DIR, 'fig3_combined_box_l_c.png')
    fig.savefig(eps_path, format='eps', bbox_inches='tight')
    fig.savefig(png_path, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print(f"\nSaved:\n  {eps_path}\n  {png_path}")


if __name__ == '__main__':
    main()
