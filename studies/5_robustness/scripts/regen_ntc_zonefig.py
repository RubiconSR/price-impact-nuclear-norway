#!/usr/bin/env python3
"""Regenerate zone_prices_NTC with SIMPLE (unweighted node-average) zonal
prices so the figure matches Table 27 (which is simple). Values are the
verified 30-year simple zonal prices from the official databases."""
import os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIG = "/Users/siva/Downloads/MT/Nuclear Power Norway Price/overleaf/pictures/results"
ZONES = ["NO1", "NO2", "NO3", "NO4", "NO5"]
# verified simple (unweighted node-average) 30-yr zonal prices
SERIES = [
    ("Baseline MD (NO 86)",        [157.0, 67.1, 99.3, 27.3, 77.8], "#3b0f70"),
    ("9.3 GW @ cables (MD) (NO 35)", [66.9, 23.1, 38.8, 13.1, 33.7], "#1f9e89"),
    ("9.3 GW @ cables (IC) (NO 53)", [96.4, 26.4, 64.8, 17.1, 60.7], "#a0da39"),
]
x = np.arange(len(ZONES)); w = 0.26
fig, ax = plt.subplots(figsize=(11, 5))
for i, (label, vals, col) in enumerate(SERIES):
    ax.bar(x + (i-1)*w, vals, w, label=label, color=col)
ax.set_xticks(x); ax.set_xticklabels(ZONES)
ax.set_ylabel("Zonal price (node average) [EUR/MWh]")
ax.set_title("Zonal electricity prices — 2050 NTC Border Placement")
ax.legend(frameon=True)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "zone_prices_NTC.pdf"))
fig.savefig(os.path.join(FIG, "zone_prices_NTC.png"), dpi=150)
print("regenerated zone_prices_NTC with simple values")
