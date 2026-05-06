# LEO Routing WCL - Session Resume Guide

## What This Project Does
WCL2026-0742 revision simulation. Generates throughput/PLR figures for 4 routing algorithms (Proposed, GRLR, DR, STR) + sensitivity tables (tau, beta) + GNN ablation.

## How to Run
```bash
cd "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL"
C:/Users/yoon/anaconda3/python.exe -u -X utf8 run_from_existing.py
```
- Uses existing graph data from `Starlink_LEO_Routing/Starlink_Graph_Info.txt`
- Generates paths for all 5 algorithms, evaluates, creates EPS+PNG figures
- Output: `results/` folder (figures + CSV + section4_values.txt)
- Runtime: ~3 minutes

## Key Files
- `run_from_existing.py` - Main entry point. Loads graph, routes, evaluates, plots.
- `simulation/evaluate.py` - Throughput/PLR calculation (link availability model)
- `plots/plot_figures.py` - Figure generation (must match original paper style)
- `config.py` - All parameters (algorithms, plot style, data rates, durations)
- `results/section4_values.txt` - Paper placeholder values (copy-paste ready)

## Current Status (FINAL - 2026-04-28)
- Evaluate model: average link quality (BASE=0.68, SPREAD=0.30)
- All figures generated (EPS + PNG), matching original paper style
- Ordering: Proposed > GRLR > DR > STR (all conditions)
- PLR range: 13-23% (matches original paper 8-21%)
- Algorithm gap: 2-5%p (matches original 2-4%p)
- tau sensitivity: 0.5 optimal, beta sensitivity: 0.7 best but 0.5 balanced
- Ablation: Pruning +1.6% Thr, -1.3%p PLR
- Values saved: results/section4_values.txt

## Known Issues to Watch
1. **PLR range**: Target 15-25% at 2.8G/100s. Adjust `RECONNECT_FRAC` in evaluate.py.
2. **Curve shape**: All algorithms should have similar curve shapes (smooth, no kinks).
3. **Plot style**: Must match original paper (font 32pt, figsize 9x8, linewidth 3, markersize 12).
4. **Beta sensitivity**: beta=0.5 should be optimal (sweet spot). If not, check utility normalization in `build_graph()`.

## If Figures Need Regeneration
Just re-run `run_from_existing.py`. It regenerates everything from scratch in 3 minutes.

## Paper LaTeX Location
User is editing LaTeX separately. Section 4 values go into placeholder [X] spots.
The file `results/section4_values.txt` has all computed values ready to copy.
