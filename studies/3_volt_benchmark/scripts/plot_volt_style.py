"""
Case 3 (Volt benchmark) reproduction figures: our PowerGAMA results for the
Volt offshore-wind scenarios, with Volt/BCG's published values overlaid as
reference markers. Rendered in the thesis's standard clean style (white
background, English labels), matching the other Case 3 figures.

Bars: stacked green per zone, dark = Scenario 1 (2 GW OW @ NO2), light = the
increment to Scenario 2 (4 GW OW). Red solid/dashed lines = Volt's published
Scenario 1 / Scenario 2 values. Filenames unchanged: volt_compare_prices,
volt_compare_savings.
"""
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

BASE = pathlib.Path(__file__).resolve().parents[3]
OUT = BASE / 'studies' / '3_volt_benchmark' / 'plots'
OUT.mkdir(parents=True, exist_ok=True)
OVERLEAF = BASE / 'overleaf' / 'pictures' / 'results'
OVERLEAF.mkdir(parents=True, exist_ok=True)

ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
DEMAND = {'NO1': 44, 'NO2': 56, 'NO3': 40, 'NO4': 30, 'NO5': 25}
NOK_PER_EUR = 11.4

# Volt/BCG published reference values (report, Figs. 1-2).
VOLT_PRICE_OERE = {
    'S1': {'NO1': -7, 'NO2': -7, 'NO3': -6, 'NO4': -4, 'NO5': -7},
    'S2': {'NO1': -13, 'NO2': -14, 'NO3': -12, 'NO4': -7, 'NO5': -12},
}
VOLT_SAVE_BNOK = {
    'S1': {'NO1': 3.0, 'NO2': 4.1, 'NO3': 2.6, 'NO4': 1.2, 'NO5': 1.6},
    'S2': {'NO1': 5.7, 'NO2': 7.9, 'NO3': 4.6, 'NO4': 2.3, 'NO5': 3.0},
}

# Our PowerGAMA volume-weighted zone prices (EUR/MWh), verified results
PRICES = {
    'V0': {'NO1': 86.80, 'NO2': 68.97, 'NO3': 59.41, 'NO4': 23.59, 'NO5': 64.72},
    'V1': {'NO1': 84.55, 'NO2': 62.27, 'NO3': 58.43, 'NO4': 23.51, 'NO5': 69.07},
    'V2': {'NO1': 78.88, 'NO2': 56.23, 'NO3': 53.98, 'NO4': 23.43, 'NO5': 61.39},
}

DARK = '#2e7d4f'    # PowerGAMA Scenario 1
LIGHT = '#8ccf8e'   # PowerGAMA Scenario 2 increment
REF1 = '#b3202f'    # Volt Scenario 1 reference marker (solid)
REF2 = '#7a1420'    # Volt Scenario 2 reference marker (dashed)


def clean_axes(ax):
    ax.axhline(0, color='#444444', lw=1.0, zorder=5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xticks(range(len(ZONES)))
    ax.set_xticklabels(ZONES, fontsize=12)
    ax.tick_params(axis='y', labelsize=11)
    ax.grid(axis='y', color='#dddddd', lw=0.7, zorder=0)
    ax.set_axisbelow(True)


def legend_handles(inc_label):
    return [Patch(facecolor=DARK, label='PowerGAMA S1 (2 GW OW)'),
            Patch(facecolor=LIGHT, label=inc_label),
            Line2D([0], [0], color=REF1, lw=2.4, label='Volt S1 (published)'),
            Line2D([0], [0], color=REF2, lw=2.4, ls=(0, (2, 1.2)),
                   label='Volt S2 (published)')]


def save_fig(fig, stem):
    thesis = {'fig1_prices': 'volt_compare_prices',
              'fig2_savings': 'volt_compare_savings'}[stem]
    for d_ in (OUT, OVERLEAF):
        for ext in ('png', 'pdf'):
            fig.savefig(d_ / f'{thesis}.{ext}', dpi=160, bbox_inches='tight')


def d(scen, z, oere=False):
    val = PRICES[scen][z] - PRICES['V0'][z]            # EUR/MWh
    return val * NOK_PER_EUR / 10 if oere else val      # -> øre/kWh


def fmt(v):
    return f'{v:.0f}' if abs(v) >= 1 else f'{v:.1f}'


# ============================================================
# Change in zonal power price (øre/kWh)
# ============================================================
def fig1():
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    s1 = [d('V1', z, oere=True) for z in ZONES]
    s2 = [d('V2', z, oere=True) for z in ZONES]
    w = 0.55
    for i, z in enumerate(ZONES):
        a, b = s1[i], s2[i]
        ax.bar(i, a, w, color=DARK, zorder=3)
        ax.bar(i, b - a, w, bottom=a, color=LIGHT, zorder=2)
        if abs(a) >= 0.8:
            ax.text(i, a / 2, fmt(a), ha='center', va='center', color='white',
                    fontsize=12, fontweight='bold', zorder=4)
        off = -0.5 if b < 0 else 0.5
        ax.text(i, b + off, fmt(b), ha='center', va='top' if b < 0 else 'bottom',
                color='#333333', fontsize=12, zorder=4)
        ax.plot([i - w / 2, i + w / 2], [VOLT_PRICE_OERE['S1'][z]] * 2,
                color=REF1, lw=2.4, solid_capstyle='butt', zorder=6)
        ax.plot([i - w / 2, i + w / 2], [VOLT_PRICE_OERE['S2'][z]] * 2,
                color=REF2, lw=2.4, ls=(0, (2, 1.2)), solid_capstyle='butt', zorder=6)
    clean_axes(ax)
    ax.set_xlim(-0.6, len(ZONES) - 0.4)
    ax.set_ylim(min(min(s1), min(s2), min(VOLT_PRICE_OERE['S2'].values())) - 3,
                max(max(s1), max(s2), 0) + 3)
    ax.set_ylabel('Price change vs Scenario 0 [øre/kWh]', fontsize=12)
    ax.set_title('Change in zonal power price, Case 3 (PowerGAMA vs Volt)',
                 fontsize=13, fontweight='bold', pad=10)
    ax.legend(handles=legend_handles('$\\rightarrow$ S2 (+2 GW OW)'),
              loc='lower left', fontsize=10, frameon=False, ncol=2)
    save_fig(fig, 'fig1_prices')
    plt.close(fig)
    print('wrote volt_compare_prices  S1', [round(v, 1) for v in s1],
          'S2', [round(v, 1) for v in s2])


# ============================================================
# Consumer-cost saving (bn NOK/yr); NO5 is negative (price rises there)
# ============================================================
def fig2():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    s1 = [-d('V1', z) * DEMAND[z] * NOK_PER_EUR / 1000 for z in ZONES]
    s2 = [-d('V2', z) * DEMAND[z] * NOK_PER_EUR / 1000 for z in ZONES]
    w = 0.55
    for i, z in enumerate(ZONES):
        a, b = s1[i], s2[i]
        ax.bar(i, a, w, color=DARK, zorder=3)
        ax.bar(i, b - a, w, bottom=a, color=LIGHT, zorder=2)
        if abs(a) > 0.15:
            ax.text(i, a / 2, f'{a:.1f}', ha='center', va='center', color='white',
                    fontsize=11, fontweight='bold', zorder=4)
        off = 0.22 if b >= 0 else -0.22
        ax.text(i, b + off, f'{b:.1f}', ha='center', va='bottom' if b >= 0 else 'top',
                color='#333333', fontsize=12,
                fontweight='bold' if b < 0 else 'normal', zorder=4)
        ax.plot([i - w / 2, i + w / 2], [VOLT_SAVE_BNOK['S1'][z]] * 2,
                color=REF1, lw=2.4, solid_capstyle='butt', zorder=6)
        ax.plot([i - w / 2, i + w / 2], [VOLT_SAVE_BNOK['S2'][z]] * 2,
                color=REF2, lw=2.4, ls=(0, (2, 1.2)), solid_capstyle='butt', zorder=6)
    clean_axes(ax)
    hi = max(max(s2), VOLT_SAVE_BNOK['S2']['NO2']) + 1.2
    lo = min(0, min(s1)) - 1.4
    ax.set_xlim(-0.6, len(ZONES) - 0.4)
    ax.set_ylim(lo, hi)
    ax.set_ylabel('Consumer-cost saving [bn NOK/yr]', fontsize=12)
    ax.set_title('Consumer-cost saving by zone, Case 3 (PowerGAMA vs Volt)',
                 fontsize=13, fontweight='bold', pad=10)
    # small demand markers under each zone
    yb = lo + 0.5
    for i, z in enumerate(ZONES):
        ax.add_patch(Ellipse((i, yb), 0.30, 0.55, color=DARK, zorder=4))
        ax.text(i, yb, str(DEMAND[z]), ha='center', va='center', color='white',
                fontsize=8.5, zorder=5)
    ax.text(len(ZONES) - 0.5, yb, 'demand\n2040 (TWh)', ha='left', va='center',
            fontsize=8.5, color='#555555')
    ax.legend(handles=legend_handles('$\\rightarrow$ S2 (+2 GW OW)'),
              loc='upper right', fontsize=10, frameon=False, ncol=1)
    tot1, tot2 = sum(s1), sum(s2)
    save_fig(fig, 'fig2_savings')
    plt.close(fig)
    print('wrote volt_compare_savings  S1', [round(v, 1) for v in s1],
          'S2', [round(v, 1) for v in s2], 'tot', round(tot1, 1), round(tot2, 1),
          '(Volt 12.5 / 23.4)')


if __name__ == '__main__':
    fig1()
    fig2()
