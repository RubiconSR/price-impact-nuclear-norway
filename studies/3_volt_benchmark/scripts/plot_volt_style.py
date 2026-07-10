"""
Reproduce Volt/BCG's Figur 1 and Figur 2 in their exact visual style, but
with OUR PowerGAMA results from the Volt benchmark scenarios.

Volt style: vertical stacked green bars per zone, dark = Scenario 1 (2 GW OW),
light = increment to Scenario 2 (4 GW OW). Grey panel, green title, value
labels, and (Figur 2) demand ovals.

Scenario mapping: our V1 (2 GW OW @ NO2) = Volt Scenario 1; V2 (4 GW) = Volt S2.
"""
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse

BASE = pathlib.Path(__file__).resolve().parents[3]
OUT = BASE / 'studies' / '3_volt_benchmark' / 'plots'
OUT.mkdir(parents=True, exist_ok=True)
OVERLEAF = BASE / 'overleaf' / 'pictures' / 'results'
OVERLEAF.mkdir(parents=True, exist_ok=True)

ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
DEMAND = {'NO1': 44, 'NO2': 56, 'NO3': 40, 'NO4': 30, 'NO5': 25}
NOK_PER_EUR = 11.4

# Volt/BCG published reference values (report, Figs. 1-2).
# Fig 1: change in power price per zone (øre/kWh).
VOLT_PRICE_OERE = {
    'S1': {'NO1': -7, 'NO2': -7, 'NO3': -6, 'NO4': -4, 'NO5': -7},
    'S2': {'NO1': -13, 'NO2': -14, 'NO3': -12, 'NO4': -7, 'NO5': -12},
}
# Fig 2: direct consumer-cost saving per zone (bn NOK/yr) -> sums 12.5 / 23.4.
VOLT_SAVE_BNOK = {
    'S1': {'NO1': 3.0, 'NO2': 4.1, 'NO3': 2.6, 'NO4': 1.2, 'NO5': 1.6},
    'S2': {'NO1': 5.7, 'NO2': 7.9, 'NO3': 4.6, 'NO4': 2.3, 'NO5': 3.0},
}
REF1 = '#b3202f'   # Volt Scenario 1 reference marker
REF2 = '#7a1420'   # Volt Scenario 2 reference marker


def save_fig(fig, stem):
    """Save under the Volt-style name (plots/) and as the thesis comparison
    figure (overleaf/pictures/results/) in png + pdf."""
    for ext in ('png', 'pdf'):
        fig.savefig(OUT / f'volt_style_{stem}.{ext}', dpi=160)
    thesis = {'fig1_prices': 'volt_compare_prices', 'fig2_savings': 'volt_compare_savings'}[stem]
    for d in (OUT, OVERLEAF):
        for ext in ('png', 'pdf'):
            fig.savefig(d / f'{thesis}.{ext}', dpi=160)

# Our PowerGAMA volume-weighted zone prices (EUR/MWh), verified results
PRICES = {
    'V0': {'NO1': 86.80, 'NO2': 68.97, 'NO3': 59.41, 'NO4': 23.59, 'NO5': 64.72},
    'V1': {'NO1': 84.55, 'NO2': 62.27, 'NO3': 58.43, 'NO4': 23.51, 'NO5': 69.07},
    'V2': {'NO1': 78.88, 'NO2': 56.23, 'NO3': 53.98, 'NO4': 23.43, 'NO5': 61.39},
}

# Volt colours
DARK = '#2e7d4f'    # Scenario 1
LIGHT = '#67b96a'   # Scenario 2 increment
TITLE = '#43a86b'
PANEL = '#ecefec'
FOOT = '#dde2dd'

FOOT_TXT = ('Scenario 1 = Sørlige Nordsjø II + Utsira Nord (2 GW havvind @ NO2)      '
            'Scenario 2 = Scenario 1 + ytterligere 2 GW havvind @ NO2\n'
            'Egne PowerGAMA-resultater (2040-systemet, 30 værår). '
            'Δ relativt til Scenario 0 (uten havvind).')


def d(scen, z, oere=False):
    val = PRICES[scen][z] - PRICES['V0'][z]            # EUR/MWh
    return val * NOK_PER_EUR / 10 if oere else val      # -> øre/kWh


def panel(ax):
    ax.add_patch(FancyBboxPatch((0.005, 0.005), 0.99, 0.99,
                 boxstyle="round,pad=0,rounding_size=0.01",
                 transform=ax.transAxes, facecolor=PANEL, edgecolor='none', zorder=-5))


def fmt(v):
    return f'{v:.0f}' if abs(v) >= 1 else f'{v:.1f}'


# ============================================================
# Figur 1: change in power price (øre/kWh), bars pointing down
# ============================================================
def fig1():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    panel(ax)
    x = range(len(ZONES))
    s1 = [d('V1', z, oere=True) for z in ZONES]
    s2 = [d('V2', z, oere=True) for z in ZONES]
    w = 0.5
    lo = min(min(s1), min(s2)) - 3
    top = max(max(s1), max(s2), 0) + 3.5      # headroom for zone labels + positive bars
    zlabel_y = top - 1.2
    for i, z in enumerate(ZONES):
        a, b = s1[i], s2[i]
        ax.bar(i, a, w, color=DARK, zorder=3)                      # 0 -> S1
        ax.bar(i, b - a, w, bottom=a, color=LIGHT, zorder=2)        # S1 -> S2
        if abs(a) >= 0.8:                                           # inside dark label
            ax.text(i, a / 2, fmt(a), ha='center', va='center', color='white',
                    fontsize=11, fontweight='bold', zorder=4)
        off = -0.55 if b < 0 else 0.55
        ax.text(i, b + off, fmt(b), ha='center',
                va='top' if b < 0 else 'bottom', color='#444444', fontsize=11, zorder=4)
        # Volt published reference values (Fig. 1) as horizontal markers
        ax.plot([i - w / 2, i + w / 2], [VOLT_PRICE_OERE['S1'][z]] * 2,
                color=REF1, lw=2.2, solid_capstyle='butt', zorder=6)
        ax.plot([i - w / 2, i + w / 2], [VOLT_PRICE_OERE['S2'][z]] * 2,
                color=REF2, lw=2.2, ls=(0, (2, 1.2)), solid_capstyle='butt', zorder=6)
    ax.axhline(0, color='#555555', lw=1.0, zorder=5)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], color=REF1, lw=2.2, label='Volt S1 (published)'),
                       Line2D([0], [0], color=REF2, lw=2.2, ls=(0, (2, 1.2)),
                              label='Volt S2 (published)')],
              loc='lower left', fontsize=9, frameon=False)
    for i, z in enumerate(ZONES):                                   # zone header row
        ax.text(i, zlabel_y, z, ha='center', va='center', fontsize=12, color='#333333')
    ax.text(-0.55, 0.0, 'Scenario 1:\n2 GW havvind', ha='right', va='center',
            fontsize=9.5, color=DARK)
    ax.set_xlim(-1.4, len(ZONES) - 0.3)
    ax.set_ylim(lo, top)
    ax.set_title('Endring i kraftpris i 2040 sammenliknet med Scenario 0 (øre/kWh) — PowerGAMA',
                 loc='left', color=TITLE, fontsize=12, fontweight='bold', pad=14)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(0.06, 0.02, FOOT_TXT, fontsize=7.3, color='#555555', va='bottom')
    fig.subplots_adjust(left=0.04, right=0.985, top=0.9, bottom=0.16)
    save_fig(fig, 'fig1_prices')
    plt.close(fig)
    print('wrote volt_compare_prices.png/pdf  (øre/kWh)  S1', [round(v, 1) for v in s1],
          ' S2', [round(v, 1) for v in s2])


# ============================================================
# Figur 2: consumer-cost savings (bn NOK/yr), bars up + demand ovals
# ============================================================
def fig2():
    fig, ax = plt.subplots(figsize=(11, 5.8))
    panel(ax)
    # savings = -Δprice[EUR/MWh] * demand[TWh] * NOK/EUR / 1000  (bn NOK/yr)
    s1 = [-d('V1', z) * DEMAND[z] * NOK_PER_EUR / 1000 for z in ZONES]
    s2 = [-d('V2', z) * DEMAND[z] * NOK_PER_EUR / 1000 for z in ZONES]
    w = 0.5
    for i, z in enumerate(ZONES):
        a, b = s1[i], s2[i]
        ax.bar(i, a, w, color=DARK, zorder=3)
        ax.bar(i, b - a, w, bottom=a, color=LIGHT, zorder=2)
        if abs(a) > 0.15:
            ax.text(i, a / 2, f'{a:.1f}', ha='center', va='center', color='white',
                    fontsize=10.5, fontweight='bold', zorder=4)
        ax.text(i, b + (0.25 if b >= 0 else -0.25), f'{b:.1f}', ha='center',
                va='bottom' if b >= 0 else 'top', color='#444444', fontsize=11, zorder=4)
        # Volt published reference savings (Fig. 2) as horizontal markers
        ax.plot([i - w / 2, i + w / 2], [VOLT_SAVE_BNOK['S1'][z]] * 2,
                color=REF1, lw=2.2, solid_capstyle='butt', zorder=6)
        ax.plot([i - w / 2, i + w / 2], [VOLT_SAVE_BNOK['S2'][z]] * 2,
                color=REF2, lw=2.2, ls=(0, (2, 1.2)), solid_capstyle='butt', zorder=6)
    ax.axhline(0, color='#555555', lw=1.0, zorder=5)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], color=REF1, lw=2.2, label='Volt S1 (published)'),
                       Line2D([0], [0], color=REF2, lw=2.2, ls=(0, (2, 1.2)),
                              label='Volt S2 (published)')],
              loc='upper center', fontsize=9, frameon=False)
    hi = max(max(s2), VOLT_SAVE_BNOK['S2']['NO2']) + 1.5
    lo = min(0, min(s1)) - 1.2
    ax.set_xlim(-1.6, len(ZONES) + 0.4)
    ax.set_ylim(lo, hi)
    # demand ovals + zone labels below axis
    yb = lo + 0.45
    for i, z in enumerate(ZONES):
        ax.text(i, lo + 0.95, z, ha='center', va='bottom', fontsize=11, color='#333333')
        ax.add_patch(Ellipse((i, yb), 0.42, 0.45, color=DARK, zorder=4))
        ax.text(i, yb, str(DEMAND[z]), ha='center', va='center', color='white',
                fontsize=8.5, zorder=5)
    ax.text(-0.6, max(s2) * 0.6, 'Scenario 2:\n4 GW havvind', ha='right', va='center',
            fontsize=9.5, color=LIGHT)
    ax.text(-0.6, max(s1) * 0.4, 'Scenario 1:\n2 GW havvind', ha='right', va='center',
            fontsize=9.5, color=DARK)
    ax.text(len(ZONES) - 0.42, yb, '= forbruk\n   2040 (TWh)', ha='left', va='center',
            fontsize=7.5, color='#555555')
    ax.set_title('Direkte besparelser i forbrukeres kraftkostnad vs Scenario 0 i 2040 '
                 '(mrd. NOK/år) — PowerGAMA',
                 loc='left', color=TITLE, fontsize=12, fontweight='bold', pad=14)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    tot1, tot2 = sum(s1), sum(s2)
    fig.text(0.06, 0.02,
             FOOT_TXT + f'\nTotal NO: Scenario 1 = {tot1:.1f} mrd NOK/år, '
             f'Scenario 2 = {tot2:.1f} mrd NOK/år  (Volt: 12.5 / 23.4).',
             fontsize=7.3, color='#555555', va='bottom')
    fig.subplots_adjust(left=0.04, right=0.985, top=0.9, bottom=0.17)
    save_fig(fig, 'fig2_savings')
    plt.close(fig)
    print('wrote volt_compare_savings.png/pdf  S1', [round(v, 1) for v in s1],
          ' S2', [round(v, 1) for v in s2], ' tot', round(tot1, 1), round(tot2, 1))


if __name__ == '__main__':
    fig1()
    fig2()
