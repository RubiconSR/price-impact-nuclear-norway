"""
Baseline analysis script - comparing PowerGAMA results with Hjelmeland EMPS results.
Uses PowerGAMA's built-in Results class and NordicNuclearAnalysis database_functions.
"""

import sys
sys.path.insert(0, 'NordicNuclearAnalysis NY/functions')

import pathlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import powergama
from powergama.database import Database
from database_functions import (
    getZonePricesAverageFromDB,
    getZonePricesVolumeWeightedFromDB,
    getAreaPricesAverageFromDB,
    getLoadheddingSumsFromDB,
    getGeneratorOutputSumPerAreaFromDB,
    getSystemCostFromDB,
    getStorageFillingInAreaFromDB,
    getStorageFillingInZoneFromDB,
    getImportExportFromDB,
    getAverageUtilisationFromDB,
)

# ============================================================
# Configuration
# ============================================================
SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_baseline_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'

FIGURES_DIR = SCENARIO_DIR / 'figures'
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

N_YEARS = SIM_YEAR_END - SIM_YEAR_START + 1  # 30

# Hjelmeland Figure 10 approximate baseline prices (EUR/MWh)
HJELMELAND_PRICES = {
    'NO1': 35, 'NO2': 28, 'NO3': 28, 'NO4': 28, 'NO5': 30,
    'SE1': 30, 'SE2': 33, 'SE3': 42, 'SE4': 55,
    'DK1': 55, 'DK2': 50, 'FI': 40,
}


# ============================================================
# Load grid data
# ============================================================
def load_data():
    data = powergama.GridData()
    system_path = DATA_PATH / 'system'
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )
    profiles = pd.read_csv(DATA_PATH / 'timeseries_profiles.csv', index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    storval = pd.read_csv(DATA_PATH / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)
    return data


# ============================================================
# Use PowerGAMA Results class (built-in)
# ============================================================
def load_results(data):
    """Load results using PowerGAMA's built-in Results class."""
    res = powergama.Results(data, SQL_FILE, replace=False)
    return res


# ============================================================
# Plot functions using PowerGAMA Results
# ============================================================

def plot_zone_prices_comparison(data, db, time_max_min):
    """Bar chart comparing PowerGAMA zone prices with Hjelmeland EMPS."""
    zone_prices = getZonePricesVolumeWeightedFromDB(data, db, time_max_min)

    zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5', 'SE1', 'SE2', 'SE3', 'SE4', 'DK1', 'DK2', 'FI']
    pg_vals = [zone_prices.get(z, 0) for z in zones]
    hj_vals = [HJELMELAND_PRICES.get(z, 0) for z in zones]

    x = np.arange(len(zones))
    width = 0.35

    fig, ax = plt.subplots(figsize=(14, 6))
    bars1 = ax.bar(x - width/2, pg_vals, width, label='PowerGAMA (this study)', color='steelblue')
    bars2 = ax.bar(x + width/2, hj_vals, width, label='Hjelmeland EMPS (approx.)', color='coral')

    ax.set_ylabel('Average Price (EUR/MWh)')
    ax.set_title('Baseline (B) - Volume Weighted Mean Price by Zone')
    ax.set_xticks(x)
    ax.set_xticklabels(zones, rotation=45)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'zone_prices_comparison.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "zone_prices_comparison.png"}')


def plot_norway_price_map(res, time_max_min):
    """Use PowerGAMA's built-in plotMapGrid for Norwegian prices."""
    fig, ax = plt.subplots(figsize=(10, 12))
    res.plotMapGrid(
        ax=ax,
        timeMaxMin=time_max_min,
        variable='nodalprice',
        title='Baseline - Average Nodal Prices',
    )
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'nodal_price_map.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "nodal_price_map.png"}')


def plot_storage_filling_norway(data, db, time_max_min):
    """Plot reservoir filling trajectory for Norway (comparable to Hjelmeland Figure 7)."""
    filling = getStorageFillingInAreaFromDB(
        data, db, areas=['NO'], generator_type=['hydro'],
        relative_storage=True, timeMaxMin=time_max_min
    )

    if not filling:
        print('No storage filling data found for Norway')
        return

    timesteps = sorted(filling.keys())
    values = [filling[t] * 100 for t in timesteps]

    # Convert to weekly averages over the year (averaged across 30 years)
    hours_per_week = 168
    weeks_per_year = 52
    hours_per_year = int(365.2425 * 24)

    # Reshape into years
    weekly_filling = {}
    for t, v in zip(timesteps, values):
        year_idx = t // hours_per_year
        week = (t % hours_per_year) // hours_per_week
        if week >= weeks_per_year:
            week = weeks_per_year - 1
        if week not in weekly_filling:
            weekly_filling[week] = []
        weekly_filling[week].append(v)

    weeks = sorted(weekly_filling.keys())
    mean_filling = [np.mean(weekly_filling[w]) for w in weeks]
    min_filling = [np.min(weekly_filling[w]) for w in weeks]
    max_filling = [np.max(weekly_filling[w]) for w in weeks]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.fill_between(weeks, min_filling, max_filling, alpha=0.2, color='steelblue', label='Min-Max range')
    ax.plot(weeks, mean_filling, 'b-', linewidth=2, label='Mean (30 years)')
    ax.set_xlabel('Week of Year')
    ax.set_ylabel('Reservoir Filling (%)')
    ax.set_title('Norway Total Reservoir Trajectory - Baseline (cf. Hjelmeland Fig. 7)')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 51)
    ax.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'reservoir_trajectory_norway.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "reservoir_trajectory_norway.png"}')


def plot_production_mix_norway(data, db, time_max_min):
    """Bar chart of production mix in Norway per type."""
    gen_types = data.getGeneratorsPerAreaAndType().get('NO', {})

    types = []
    production = []
    for gt, indices in gen_types.items():
        prod = sum(db.getResultGeneratorPower(indices, time_max_min))
        twh_yr = prod / 1e6 / N_YEARS
        if twh_yr > 0.01:
            types.append(gt)
            production.append(twh_yr)

    # Sort by production
    sorted_idx = np.argsort(production)[::-1]
    types = [types[i] for i in sorted_idx]
    production = [production[i] for i in sorted_idx]

    colors = {
        'hydro': '#1f77b4', 'ror': '#4a9bd9', 'wind_on': '#2ca02c',
        'wind_off': '#98df8a', 'solar': '#ffdd57', 'fossil_gas': '#d62728',
        'biomass': '#8c564b', 'nuclear': '#ff7f0e', 'fossil_other': '#7f7f7f'
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(types, production, color=[colors.get(t, 'gray') for t in types])
    ax.set_ylabel('Production (TWh/yr)')
    ax.set_title(f'Norway Production Mix - Baseline ({SIM_YEAR_START}-{SIM_YEAR_END} avg)')
    ax.grid(axis='y', alpha=0.3)

    for bar, val in zip(bars, production):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'production_mix_norway.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "production_mix_norway.png"}')


def plot_price_duration_curves(data, db, time_max_min):
    """Price duration curves for Norwegian zones (cf. Hjelmeland Figure 11)."""
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = {'NO1': '#1f77b4', 'NO2': '#ff7f0e', 'NO3': '#2ca02c', 'NO4': '#d62728', 'NO5': '#9467bd'}

    for zone in ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']:
        zone_nodes = data.node[data.node['zone'] == zone].index.tolist()
        if not zone_nodes:
            continue

        # Get prices for first node in zone as representative
        prices = np.array(db.getResultNodalPrice(zone_nodes[0], time_max_min), dtype=float)
        prices_sorted = np.sort(prices)[::-1]

        x = np.linspace(0, 100, len(prices_sorted))
        ax.plot(x, prices_sorted, label=zone, color=colors[zone], linewidth=1.5)

    ax.set_xlabel('Duration (%)')
    ax.set_ylabel('Price (EUR/MWh)')
    ax.set_title('Price Duration Curves - Norwegian Zones (cf. Hjelmeland Fig. 11)')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 150)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'price_duration_curves_norway.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "price_duration_curves_norway.png"}')


def plot_branch_utilisation(data, db, time_max_min):
    """Bar chart of branch utilisation for key inter-zone connections."""
    util_ac = getAverageUtilisationFromDB(data, db, time_max_min, branchtype='ac')

    # Filter for Norwegian inter-zone branches
    branches = []
    utils = []
    for i, row in data.branch.iterrows():
        nf, nt = row['node_from'], row['node_to']
        zone_from = nf.split('_')[0] if '_' in nf else nf
        zone_to = nt.split('_')[0] if '_' in nt else nt
        # Only inter-zone branches involving Norway or Nordic
        if zone_from != zone_to:
            label = f'{zone_from}-{zone_to}'
            branches.append(label)
            utils.append(util_ac[i] * 100)

    # Sort by utilisation
    sorted_idx = np.argsort(utils)[::-1][:20]
    branches = [branches[i] for i in sorted_idx]
    utils = [utils[i] for i in sorted_idx]

    fig, ax = plt.subplots(figsize=(14, 6))
    colors = ['#d62728' if u > 80 else '#ff7f0e' if u > 60 else '#2ca02c' for u in utils]
    ax.barh(range(len(branches)), utils, color=colors)
    ax.set_yticks(range(len(branches)))
    ax.set_yticklabels(branches)
    ax.set_xlabel('Average Utilisation (%)')
    ax.set_title('Top 20 Inter-Zone Branch Utilisation - Baseline')
    ax.axvline(x=80, color='red', linestyle='--', alpha=0.5, label='80% threshold')
    ax.legend()
    ax.grid(axis='x', alpha=0.3)
    ax.invert_yaxis()

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'branch_utilisation.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "branch_utilisation.png"}')


def plot_generation_per_area(res, time_max_min):
    """Use PowerGAMA's built-in plotGenerationPerArea."""
    for area in ['NO', 'SE', 'FI']:
        fig, ax = plt.subplots(figsize=(14, 6))
        res.plotGenerationPerArea(area, timeMaxMin=time_max_min, ax=ax)
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / f'generation_{area}.png', dpi=150)
        plt.close()
        print(f'Saved: {FIGURES_DIR / f"generation_{area}.png"}')


def plot_storage_per_area(res, time_max_min):
    """Use PowerGAMA's built-in plotStoragePerArea."""
    for area in ['NO', 'SE']:
        fig, ax = plt.subplots(figsize=(14, 6))
        res.plotStoragePerArea(area, timeMaxMin=time_max_min, ax=ax)
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / f'storage_{area}.png', dpi=150)
        plt.close()
        print(f'Saved: {FIGURES_DIR / f"storage_{area}.png"}')


def plot_energy_mix(res, time_max_min):
    """Use PowerGAMA's built-in plotEnergyMix."""
    res.plotEnergyMix(timeMaxMin=time_max_min, relative=True)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'energy_mix.png', dpi=150)
    plt.close()
    print(f'Saved: {FIGURES_DIR / "energy_mix.png"}')


def print_summary(data, db, time_max_min):
    """Print key summary statistics."""
    print('=' * 60)
    print('BASELINE RESULTS SUMMARY')
    print('=' * 60)

    # Zone prices (volume-weighted)
    zone_prices = getZonePricesVolumeWeightedFromDB(data, db, time_max_min)
    print('\nZone Prices (EUR/MWh):')
    print(f'  {"Zone":<6} {"PowerGAMA":>10} {"Hjelmeland":>10} {"Diff":>8}')
    print(f'  {"-"*36}')
    for zone in ['NO1', 'NO2', 'NO3', 'NO4', 'NO5', 'SE1', 'SE2', 'SE3', 'SE4', 'DK1', 'DK2', 'FI']:
        pg = zone_prices.get(zone, float('nan'))
        hj = HJELMELAND_PRICES.get(zone, float('nan'))
        diff = pg - hj
        print(f'  {zone:<6} {pg:10.2f} {hj:10.0f} {diff:+8.2f}')

    # Norwegian average
    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    pg_avg = np.mean([zone_prices[z] for z in no_zones])
    hj_avg = np.mean([HJELMELAND_PRICES[z] for z in no_zones])
    print(f'  {"NO avg":<6} {pg_avg:10.2f} {hj_avg:10.0f} {pg_avg-hj_avg:+8.2f}')

    # Load shedding
    loadshed = getLoadheddingSumsFromDB(data, db, timeMaxMin=time_max_min)
    print(f'\nLoad Shedding:')
    for area in ['NO', 'SE', 'FI', 'DK']:
        ls = loadshed.get(area, 0)
        print(f'  {area}: {ls/1e3:.1f} GWh ({ls/1e3/N_YEARS:.2f} GWh/yr)')

    # Production
    gen_per_area = getGeneratorOutputSumPerAreaFromDB(data, db, timeMaxMin=time_max_min)
    print(f'\nTotal Generation (TWh/yr):')
    for area in ['NO', 'SE', 'FI', 'DK']:
        twh_yr = gen_per_area.get(area, 0) / 1e6 / N_YEARS
        print(f'  {area}: {twh_yr:.1f}')


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('Loading grid data...')
    data = load_data()
    num_hours = len(data.timerange)
    time_max_min = [0, num_hours]

    print('Opening database...')
    db = Database(SQL_FILE)

    print('Loading PowerGAMA Results object...')
    res = load_results(data)

    # Print summary
    print_summary(data, db, time_max_min)

    # Generate plots
    print('\n' + '=' * 60)
    print('GENERATING PLOTS')
    print('=' * 60)

    plot_zone_prices_comparison(data, db, time_max_min)
    plot_storage_filling_norway(data, db, time_max_min)
    plot_production_mix_norway(data, db, time_max_min)
    plot_price_duration_curves(data, db, time_max_min)
    plot_branch_utilisation(data, db, time_max_min)

    # PowerGAMA built-in plots
    print('\nPowerGAMA built-in plots:')
    plot_energy_mix(res, time_max_min)

    print('\nAll plots saved to:', FIGURES_DIR)
    print('Done!')
