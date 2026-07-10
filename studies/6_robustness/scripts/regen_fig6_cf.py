#!/usr/bin/env python3
"""Regenerate Fig6_capacity_factor with a clean layout (annotation not hidden
behind the legend). Uses the verified capacity factors from Table 8.13 - no
database read required."""
import os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIG = "/Users/siva/Downloads/MT/Nuclear Power Norway Price/overleaf/pictures/results"
labels = ["SMR1\n(1.5 GW)", "SMR3\n(4.5 GW)", "SMR6\n(9.0 GW)"]
md = [74.0, 61.5, 50.8]
ic = [89.8, 76.4, 60.3]
x = np.arange(3); w = 0.38

fig, ax = plt.subplots(figsize=(8.5, 5.2))
b1 = ax.bar(x - w/2, md, w, label="Moderate Demand (208 TWh)", color="#2c7fb8", edgecolor="black", linewidth=0.5)
b2 = ax.bar(x + w/2, ic, w, label="Increased Consumption (230 TWh)", color="#e08a3c", edgecolor="black", linewidth=0.5)
ax.bar_label(b1, fmt="%.1f%%", fontsize=11, padding=2)
ax.bar_label(b2, fmt="%.1f%%", fontsize=11, padding=2)

# ~90% reference line for a typical operating reactor fleet, labelled via the
# legend so no floating text can collide with the bars or value labels
ax.axhline(90, ls="--", color="0.4", lw=1.3, label="~90% (typical fleet)")

ax.set_ylabel("Nuclear capacity factor [%]", fontsize=12)
ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=11)
ax.set_ylim(0, 108)
ax.tick_params(axis="y", labelsize=10)
ax.set_title("Nuclear capacity factor and price cannibalisation", fontsize=13)
ax.legend(frameon=True, loc="upper right", fontsize=10)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "Fig6_capacity_factor.pdf"))
fig.savefig(os.path.join(FIG, "Fig6_capacity_factor.png"), dpi=150)
print("regenerated Fig6_capacity_factor")
