"""
Regenerate the thesis validation figure (Fig. 6.1 / fig:val_prices):
pictures/results/validation_prices_paper.png

Paper-styled grouped bar chart of Norwegian zonal prices:
Historical 2024 spot vs PowerGAMA (2020) vs PowerGAMA (30-yr avg) vs EMPS baseline.

The bar values are the reported R3 validation results (Table 6.3 in the thesis;
PowerGAMA columns come from the R3 SQLite runs and are already rounded there).
Only change vs the previous render: the EMPS NO3 reference is corrected from the
old 28 to 33.4 EUR/MWh (the value stated explicitly in the journal text of
Hjelmeland and Noland), to match Table 6.3. All other bars are unchanged.
"""

import pathlib
import matplotlib.pyplot as plt
import numpy as np

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

# Values as displayed in Table 6.3 (EUR/MWh).
HIST_2024 = [41, 50, 28, 23, 41]
PG_2020   = [45, 42, 26, 16, 35]
PG_30YR   = [58, 59, 38, 16, 41]
EMPS_B    = [55, 55, 33.4, 16, 50]   # NO3 corrected 28 -> 33.4

SERIES = [
    ('Historical (2024)',        HIST_2024, '#2ca02c'),
    ('PowerGAMA (2020)',         PG_2020,   '#1f77b4'),
    ('PowerGAMA (30 year avg.)', PG_30YR,   '#aec7e8'),
    ('EMPS (baseline)',          EMPS_B,    '#ff7f0e'),
]

x = np.arange(len(NO_ZONES))
width = 0.2

fig, ax = plt.subplots(figsize=(10, 5.6))

offsets = [-1.5, -0.5, 0.5, 1.5]
for (label, vals, color), off in zip(SERIES, offsets):
    bars = ax.bar(x + off * width, vals, width, label=label,
                  color=color, edgecolor='black', linewidth=0.5)
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f'{h:g}',
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords='offset points',
                    ha='center', va='bottom', fontsize=8)

ax.set_xlabel('Price zone', fontsize=12)
ax.set_ylabel('Average price [EUR/MWh]', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(NO_ZONES, fontsize=12)
ax.set_ylim(0, 80)
ax.legend(fontsize=10, loc='upper right')
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()

OUT = (pathlib.Path(__file__).parent.parent.parent
       / 'overleaf' / 'pictures' / 'results')
plt.savefig(OUT / 'validation_prices_paper.png', dpi=150, bbox_inches='tight')
plt.savefig(OUT / 'validation_prices_paper.pdf', bbox_inches='tight')
print('Saved:', OUT / 'validation_prices_paper.png')
