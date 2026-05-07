"""
3-panel box plot: Average ISL Duration / Average SINR / Average U_ij
per algorithm (Proposed, GRLR, DR, STR), reading from results/paths_graphs_s2.pkl.

Paper definition (Eq. utility_components / utility_def):
    U_ij^l = l_ij / T,   U_ij^c = exp(c_ij) / sum_{(m,n) in E} exp(c_mn)
    U_ij   = beta * U_ij^l + (1 - beta) * U_ij^c
beta = cfg.BETA, T = cfg.SNAPSHOT_INTERVAL_S.

The capacity term U_ij^c sums to 1 over |E|, so per-edge values are O(1/|E|)
(very small in absolute terms). The duration term dominates the absolute
magnitude. Y-axis uses scientific notation so the relative ordering across
algorithms is visible at the readable scale.

Output: results/fig3_combined_box_3panel.{eps,png}
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

T = cfg.SNAPSHOT_INTERVAL_S      # 300 s
BETA = cfg.BETA                  # 0.5


def stable_softmax(values):
    """Numerically stable softmax. Inputs may be very large (capacities in bps)."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr - np.max(arr)
    e = np.exp(arr)
    return e / np.sum(e)


def compute_edge_utilities(G, beta=BETA, T_snap=T):
    """Return {(u,v): U_ij} where U_ij follows paper Eq. (utility_components/def)."""
    edges = list(G.edges())
    if not edges:
        return {}
    durations = np.array([G[u][v]['duration'] for u, v in edges], dtype=np.float64)
    capacities = np.array([G[u][v]['capacity'] for u, v in edges], dtype=np.float64)

    u_l = durations / T_snap                     # duration utility, normalized
    u_c = stable_softmax(capacities)             # capacity utility, softmax over E
    util = beta * u_l + (1.0 - beta) * u_c

    out = {}
    for (u, v), val in zip(edges, util):
        out[(u, v)] = float(val)
        out[(v, u)] = float(val)
    return out


def collect_per_algorithm(paths, graphs):
    """For each algorithm, accumulate per-cycle path averages of duration/SINR/U_ij."""
    durations = {a: [] for a in cfg.ALGORITHMS}
    sinrs     = {a: [] for a in cfg.ALGORITHMS}
    utilities = {a: [] for a in cfg.ALGORITHMS}

    util_cache = {}  # cycle -> {(u,v): U_ij}

    for alg in cfg.ALGORITHMS:
        if alg not in paths:
            continue
        for cycle, path in paths[alg].items():
            if path is None or len(path) < 2:
                continue
            G = graphs.get(cycle)
            if G is None:
                continue

            if cycle not in util_cache:
                util_cache[cycle] = compute_edge_utilities(G)
            uedge = util_cache[cycle]

            d_list, s_list, u_list = [], [], []
            for u, v in zip(path[:-1], path[1:]):
                edata = G.get_edge_data(u, v) or G.get_edge_data(v, u)
                if edata is None:
                    continue
                d_list.append(edata['duration'])
                s_list.append(edata.get('sinr_db',
                                        10 * np.log10(max(edata.get('snr', 10), 1.0))))
                if (u, v) in uedge:
                    u_list.append(uedge[(u, v)])
                elif (v, u) in uedge:
                    u_list.append(uedge[(v, u)])
            if d_list:
                durations[alg].append(float(np.mean(d_list)))
                sinrs[alg].append(float(np.mean(s_list)))
                if u_list:
                    utilities[alg].append(float(np.mean(u_list)))

    return durations, sinrs, utilities


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

    durations, sinrs, utilities = collect_per_algorithm(paths, graphs)

    order = [a for a in cfg.ALGORITHMS if durations.get(a)]
    print("Per-algorithm sample counts:", flush=True)
    for a in order:
        print(f"  {a:>10s}: dur={len(durations[a])}, sinr={len(sinrs[a])}, "
              f"U_ij={len(utilities[a])}", flush=True)
    print(f"\nMean U_ij (beta={BETA}, T={T}s):")
    for a in order:
        if utilities[a]:
            print(f"  {a:>10s}: {np.mean(utilities[a]):.4e}", flush=True)

    # Scale U_ij by 100 for readable y-axis numbers; paper definition unchanged.
    UTIL_SCALE = 100.0
    utilities_scaled = {a: [v * UTIL_SCALE for v in utilities.get(a, [])] for a in utilities}

    fig, axes = plt.subplots(1, 3, figsize=(27, 8))
    panels = [
        (axes[0], durations,        'Average Duration (s)',                           '(a) Average Duration'),
        (axes[1], sinrs,            'Average SINR (dB)',                              '(b) Average SINR'),
        (axes[2], utilities_scaled, r'Average $U_{ij}$ $(\times 10^{-2})$',           '(c) Average ISL Utility'),
    ]
    for ax, data_dict, yl, _title in panels:
        style_box(ax, data_dict, order, yl)

    plt.tight_layout()
    for ax, _, _, title in panels:
        ax.text(0.5, -0.18, title, transform=ax.transAxes,
                ha='center', va='top', fontsize=FONT_SIZE)

    eps_path = os.path.join(OUT_DIR, 'fig3_combined_box_3panel.eps')
    png_path = os.path.join(OUT_DIR, 'fig3_combined_box_3panel.png')
    fig.savefig(eps_path, format='eps', bbox_inches='tight')
    fig.savefig(png_path, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print(f"\nSaved:\n  {eps_path}\n  {png_path}")


if __name__ == '__main__':
    main()
