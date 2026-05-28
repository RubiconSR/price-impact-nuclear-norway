"""
To figurer i Volt/BCGs stil:

Figur 1: Endring i kraftpris per sone (Δ EUR/MWh vs V0)
Figur 2: Besparelse i forbrukerkostnad per sone (mrd NOK/år)

Inkluderer Volts originaltall som referanse-søyler for direkte sammenligning.
"""

import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
PLOTS_DIR = BASE_DIR / 'master_volt_benchmark' / 'plots'

ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
NOK_PER_EUR = 11.4  # samme som NVE LA2025 og BCG bruker

# Volts forbruk 2040 per sone (TWh)
DEMAND = {'NO1': 44, 'NO2': 56, 'NO3': 40, 'NO4': 30, 'NO5': 25}

# 30-års volumvektede sonepriser (EUR/MWh) fra våre PowerGAMA-kjøringer
PRICES = {
    'V0':       {'NO1': 86.80, 'NO2': 68.97, 'NO3': 59.41, 'NO4': 23.59, 'NO5': 64.72},
    'V1':       {'NO1': 84.55, 'NO2': 62.27, 'NO3': 58.43, 'NO4': 23.51, 'NO5': 69.07},
    'V2':       {'NO1': 78.88, 'NO2': 56.23, 'NO3': 53.98, 'NO4': 23.43, 'NO5': 61.39},
    'N1':       {'NO1': 76.81, 'NO2': 53.84, 'NO3': 52.69, 'NO4': 23.42, 'NO5': 59.58},
    'N2':       {'NO1': 67.43, 'NO2': 41.60, 'NO3': 44.33, 'NO4': 23.32, 'NO5': 34.73},
    'N1jevnt':  {'NO1': 56.37, 'NO2': 66.32, 'NO3': 33.36, 'NO4': 16.65, 'NO5': 38.65},
}

# Volts originaltall fra rapportens Figur 1 (øre/kWh konvertert til EUR/MWh)
# 1 øre/kWh = 1.149 EUR/MWh (ved 11.4 NOK/EUR; vi bruker omtrent ×1.14)
VOLT_DELTA = {
    'Volt S1': {'NO1': -7 * 0.114 * 10, 'NO2': -7 * 0.114 * 10, 'NO3': -6 * 0.114 * 10,
                'NO4': -4 * 0.114 * 10, 'NO5': -7 * 0.114 * 10},
    'Volt S2': {'NO1': -13 * 0.114 * 10, 'NO2': -14 * 0.114 * 10, 'NO3': -12 * 0.114 * 10,
                'NO4': -7 * 0.114 * 10, 'NO5': -12 * 0.114 * 10},
}
# (-7 øre/kWh = -0.07 NOK/kWh = -70 NOK/MWh = -6.14 EUR/MWh ved 11.4)
# fix: -7 øre/kWh × 10 = -70 NOK/MWh / 11.4 NOK/EUR = -6.14 EUR/MWh
VOLT_DELTA = {
    'Volt S1': {z: v * 10 / NOK_PER_EUR for z, v in
                {'NO1': -7, 'NO2': -7, 'NO3': -6, 'NO4': -4, 'NO5': -7}.items()},
    'Volt S2': {z: v * 10 / NOK_PER_EUR for z, v in
                {'NO1': -13, 'NO2': -14, 'NO3': -12, 'NO4': -7, 'NO5': -12}.items()},
}


def delta_from_v0(scenario):
    return {z: PRICES[scenario][z] - PRICES['V0'][z] for z in ZONES}


def savings_mrd_nok(delta_eur):
    """Besparelse per sone i mrd NOK/år.
    ΔPris [EUR/MWh] × Forbruk [TWh] × 1e6 [MWh/TWh] × NOK/EUR / 1e9
    = ΔPris × Forbruk × NOK_per_EUR / 1000
    Negativ ΔPris → positiv besparelse.
    """
    return {z: -delta_eur[z] * DEMAND[z] * NOK_PER_EUR / 1000 for z in ZONES}


# ============================================================
# Figur 1: Δ-pris per sone — matcher Volts Figur 1
# ============================================================
def plot_delta_prices():
    scenarios_ours = ['V1', 'V2', 'N1', 'N2', 'N1jevnt']
    labels_ours = {
        'V1': '2 GW OW @ NO2 (S1)',
        'V2': '4 GW OW @ NO2 (S2)',
        'N1': '2.1 GW SMR @ NO2',
        'N2': '3.9 GW SMR @ NO2',
        'N1jevnt': '2.1 GW SMR (jevnt)',
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    # Venstre: våre fem scenarier
    ax = axes[0]
    n_bars = len(scenarios_ours)
    x = np.arange(len(ZONES))
    width = 0.8 / n_bars
    colors = ['#7fc97f', '#377eb8', '#fdc086', '#e7298a', '#beaed4']
    for i, s in enumerate(scenarios_ours):
        d = delta_from_v0(s)
        vals = [d[z] for z in ZONES]
        ax.bar(x + i * width - 0.4 + width / 2, vals,
               width, label=labels_ours[s], color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(ZONES)
    ax.set_ylabel('Endring i kraftpris [EUR/MWh]')
    ax.set_title('PowerGAMA — endring vs V0 baseline')
    ax.axhline(0, color='black', linewidth=0.6)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(axis='y', alpha=0.3)

    # Høyre: Volts originaltall (S1 og S2) + våre V1 og V2 for direkte sammenligning
    ax = axes[1]
    n_bars = 4
    width = 0.8 / n_bars
    pairs = [
        ('V1', '#377eb8', 'PowerGAMA 2 GW OW'),
        ('Volt S1', '#9ecae1', 'Volt S1 (2 GW OW)'),
        ('V2', '#e7298a', 'PowerGAMA 4 GW OW'),
        ('Volt S2', '#fbb4d5', 'Volt S2 (4 GW OW)'),
    ]
    for i, (key, color, lbl) in enumerate(pairs):
        if key.startswith('Volt'):
            vals = [VOLT_DELTA[key][z] for z in ZONES]
        else:
            d = delta_from_v0(key)
            vals = [d[z] for z in ZONES]
        ax.bar(x + i * width - 0.4 + width / 2, vals,
               width, label=lbl, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(ZONES)
    ax.set_title('Direkte sammenligning: PowerGAMA vs Volt (havvind)')
    ax.axhline(0, color='black', linewidth=0.6)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(axis='y', alpha=0.3)

    fig.suptitle('Figur 1: Endring i kraftpris per prisområde (Δ EUR/MWh vs V0)',
                 y=1.02, fontsize=12, fontweight='bold')
    plt.tight_layout()
    out = PLOTS_DIR / 'fig1_delta_prices.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Skrev {out.relative_to(BASE_DIR)}')


# ============================================================
# Figur 2: Besparelse i mrd NOK/år per sone — matcher Volts Figur 2
# ============================================================
def plot_savings():
    scenarios_ours = ['V1', 'V2', 'N1', 'N2', 'N1jevnt']
    labels_ours = {
        'V1': '2 GW OW @ NO2 (S1)',
        'V2': '4 GW OW @ NO2 (S2)',
        'N1': '2.1 GW SMR @ NO2',
        'N2': '3.9 GW SMR @ NO2',
        'N1jevnt': '2.1 GW SMR (jevnt)',
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    x = np.arange(len(ZONES))

    # Venstre: våre fem scenarier
    ax = axes[0]
    n_bars = len(scenarios_ours)
    width = 0.8 / n_bars
    colors = ['#7fc97f', '#377eb8', '#fdc086', '#e7298a', '#beaed4']
    totals = {}
    for i, s in enumerate(scenarios_ours):
        d = delta_from_v0(s)
        savings = savings_mrd_nok(d)
        vals = [savings[z] for z in ZONES]
        totals[s] = sum(vals)
        ax.bar(x + i * width - 0.4 + width / 2, vals,
               width, label=f'{labels_ours[s]} ({totals[s]:+.1f})',
               color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(ZONES)
    ax.set_ylabel('Besparelse [mrd NOK/år]')
    ax.set_title('PowerGAMA — direkte besparelse i forbrukerkostnad')
    ax.axhline(0, color='black', linewidth=0.6)
    ax.legend(fontsize=8, loc='upper right',
              title='Total NO (mrd NOK/år)')
    ax.grid(axis='y', alpha=0.3)

    # Høyre: våre V1/V2 vs Volts
    ax = axes[1]
    width = 0.8 / 4
    pairs = [
        ('V1', '#377eb8', 'PowerGAMA 2 GW OW'),
        ('Volt S1', '#9ecae1', 'Volt S1 (12.5 mrd)'),
        ('V2', '#e7298a', 'PowerGAMA 4 GW OW'),
        ('Volt S2', '#fbb4d5', 'Volt S2 (23.4 mrd)'),
    ]
    volt_savings_per_zone = {
        'Volt S1': {'NO1': 3.0, 'NO2': 4.1, 'NO3': 2.6, 'NO4': 1.2, 'NO5': 1.6},
        'Volt S2': {'NO1': 5.7, 'NO2': 7.9, 'NO3': 4.6, 'NO4': 2.3, 'NO5': 3.0},
    }
    for i, (key, color, lbl) in enumerate(pairs):
        if key.startswith('Volt'):
            vals = [volt_savings_per_zone[key][z] for z in ZONES]
        else:
            d = delta_from_v0(key)
            sav = savings_mrd_nok(d)
            vals = [sav[z] for z in ZONES]
        ax.bar(x + i * width - 0.4 + width / 2, vals,
               width, label=lbl, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(ZONES)
    ax.set_title('Direkte sammenligning: PowerGAMA vs Volt (havvind)')
    ax.axhline(0, color='black', linewidth=0.6)
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    fig.suptitle(f'Figur 2: Direkte besparelse i forbrukerkostnad 2040 '
                 f'(mrd NOK/år, {NOK_PER_EUR} NOK/EUR)',
                 y=1.02, fontsize=12, fontweight='bold')
    plt.tight_layout()
    out = PLOTS_DIR / 'fig2_savings.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Skrev {out.relative_to(BASE_DIR)}')

    # Print summary
    print('\n=== Total besparelse Norge (mrd NOK/år) ===')
    print(f'  Volt S1 (rapport):   12.5')
    print(f'  Volt S2 (rapport):   23.4')
    for s, t in totals.items():
        print(f'  {labels_ours[s]:<24} {t:+6.2f}')


if __name__ == '__main__':
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_delta_prices()
    plot_savings()
