#!/usr/bin/env python3
"""Regenerate Fig_NTC_generation_mix_MD with the legend OUTSIDE the plot area
(the original overlapped the top of the SMR_NTC bar) and readable category
names. Values are the verified 30-year NO generation mix from the databases."""
import os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIG = "/Users/siva/Downloads/MT/Nuclear Power Norway Price/overleaf/pictures/results"
# (label, colour, BL_MD value, SMR_NTC_MD value)  TWh/yr
rows = [
    ("Hydro (reservoir)", "#1f5fa8", 130.1, 120.5),
    ("Hydro (run-of-river)", "#5aa1e3", 36.6, 35.5),
    ("Onshore wind", "#2c8a3d", 19.3, 18.4),
    ("Offshore wind", "#7fd08a", 13.7, 12.3),
    ("Solar", "#f2c200", 7.7, 7.1),
    ("Nuclear (SMR)", "#e8552d", 0.0, 55.7),
    ("Gas", "#7f7f7f", 0.2, 0.0),
    ("Biomass", "#8c6d4f", 1.4, 0.9),
]
scen = ["Baseline", "SMR$_{\\mathrm{NTC}}$"]
x = np.arange(2)

fig, ax = plt.subplots(figsize=(7.4, 5.2))
bottom = np.zeros(2)
for label, col, bl, ntc in rows:
    vals = np.array([bl, ntc])
    ax.bar(x, vals, 0.55, bottom=bottom, color=col, label=label, edgecolor="white", linewidth=0.4)
    bottom += vals
# total labels on top
for xi, tot in zip(x, bottom):
    ax.text(xi, tot + 3, f"{tot:.0f} TWh", ha="center", fontsize=11, fontweight="bold")

ax.set_xticks(x); ax.set_xticklabels(scen, fontsize=12)
ax.set_ylabel("Annual generation [TWh/yr]", fontsize=12)
ax.set_ylim(0, 275)
ax.set_title("Norwegian generation mix (MD)", fontsize=13)
# legend OUTSIDE the axes on the right - cannot overlap the bars
ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=11, frameon=False,
          title="Technology", title_fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "Fig_NTC_generation_mix_MD.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(FIG, "Fig_NTC_generation_mix_MD.png"), dpi=150, bbox_inches="tight")
print("regenerated Fig_NTC_generation_mix_MD")
