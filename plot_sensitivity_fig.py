"""Generate fig5_sensitivity.eps as 1x3 line chart with dual axis (throughput + PLR).
Unified font size with plots/plot_figures.py (FONT_SIZE=32)."""
import os, csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

FONT_SIZE = 32
plt.rcParams.update({
    'font.family': 'Times New Roman',
    'font.size': FONT_SIZE,
    'axes.labelsize': FONT_SIZE,
    'xtick.labelsize': FONT_SIZE,
    'ytick.labelsize': FONT_SIZE,
    'legend.fontsize': FONT_SIZE - 4,
    'axes.titlesize': FONT_SIZE,
    'axes.grid': False,
})


def load_csv(name):
    rows = []
    with open(os.path.join(OUT_DIR, name)) as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


tau_rows = load_csv('tau_sensitivity.csv')
beta_rows = load_csv('beta_sensitivity.csv')
T_rows = load_csv('T_sensitivity.csv')

tau_x = [float(r['tau']) if r['tau'] != 'w/o' else 0.0 for r in tau_rows]
tau_lbl = [r['tau'] for r in tau_rows]
tau_thr = [float(r['Throughput (Gbps)']) for r in tau_rows]
tau_plr = [float(r.get('PLR (%)', r.get('Packet Loss Rate (%)', 0))) for r in tau_rows]

beta_x = [float(r['beta']) for r in beta_rows]
beta_thr = [float(r['Throughput (Gbps)']) for r in beta_rows]
beta_plr = [float(r.get('PLR (%)', r.get('Packet Loss Rate (%)', 0))) for r in beta_rows]

def _get_T_min(r):
    if 'T (min)' in r:
        return float(r['T (min)'])
    return float(r['T_seconds']) / 60.0

def _get_T_plr(r):
    return float(r.get('PLR (%)', r.get('Packet Loss Rate (%)', 0)))

T_x = [_get_T_min(r) for r in T_rows]
T_thr = [float(r['Throughput (Gbps)']) for r in T_rows]
T_plr = [_get_T_plr(r) for r in T_rows]

fig, axes = plt.subplots(1, 3, figsize=(18, 8))

C_THR = '#1f77b4'
C_PLR = '#d62728'


def _plot(ax, x, thr, plr, xlabel, xticks=None, xticklabels=None, title=None,
          show_left_label=True, show_right_label=True):
    l1, = ax.plot(x, thr, '-o', color=C_THR, lw=3, ms=12, label='Throughput')
    ax.set_xlabel(xlabel, labelpad=6)
    if show_left_label:
        ax.set_ylabel('Throughput (Gbps)', color=C_THR, labelpad=6)
    ax.tick_params(axis='y', labelcolor=C_THR, pad=4)
    ax.tick_params(axis='x', pad=4)
    ax.grid(True, linestyle='--', alpha=0.5)
    if xticks is not None:
        ax.set_xticks(xticks)
        if xticklabels is not None:
            ax.set_xticklabels(xticklabels)
    ax2 = ax.twinx()
    ax2.grid(False)
    l2, = ax2.plot(x, plr, '--s', color=C_PLR, lw=3, ms=12, label='PLR')
    if show_right_label:
        ax2.set_ylabel('PLR (%)', color=C_PLR, labelpad=6)
    ax2.tick_params(axis='y', labelcolor=C_PLR, pad=4)
    if title:
        ax.set_title(title, pad=10)
    return l1, l2, ax2


l1, l2, ax0r = _plot(axes[0], tau_x, tau_thr, tau_plr,
                     r'Pruning Threshold $\tau$',
                     xticks=tau_x, xticklabels=tau_lbl,
                     title=r'(a) $\tau$ sweep',
                     show_left_label=True, show_right_label=False)

_, _, ax1r = _plot(axes[1], beta_x, beta_thr, beta_plr,
                   r'Weighting Factor $\beta$',
                   xticks=beta_x,
                   title=r'(b) $\beta$ sweep',
                   show_left_label=False, show_right_label=False)

_plot(axes[2], T_x, T_thr, T_plr,
      r'Snapshot Interval $T$ (min)',
      xticks=T_x,
      title=r'(c) $T$ sweep',
      show_left_label=False, show_right_label=True)

# Hide inner tick labels AFTER layout
ax0r.set_yticklabels([])
ax1r.set_yticklabels([])
axes[1].set_yticklabels([])
axes[2].set_yticklabels([])

fig.legend([l1, l2], ['Throughput', 'PLR'],
           loc='upper center', bbox_to_anchor=(0.5, 1.02),
           ncol=2, frameon=False, fontsize=FONT_SIZE)

plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.subplots_adjust(wspace=0.06)
out_eps = os.path.join(OUT_DIR, 'fig5_sensitivity.eps')
out_png = os.path.join(OUT_DIR, 'fig5_sensitivity.png')
fig.savefig(out_eps, format='eps', bbox_inches='tight')
fig.savefig(out_png, dpi=150, bbox_inches='tight')
print(f'Saved: {out_eps}')
print(f'Saved: {out_png}')
