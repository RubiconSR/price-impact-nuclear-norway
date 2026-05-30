"""
Generate remaining plots (skipping slow plotStoragePerArea).
"""

import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import powergama

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_baseline_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'
PLOT_DIR = SCENARIO_DIR / 'plots'
PLOT_DIR.mkdir(parents=True, exist_ok=True)

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

def load_grid_data():
    system_path = DATA_PATH / 'system'
    data = powergama.GridData()
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

_plot_counter = [0]
_plot_prefix = ['plot']
def save_instead_of_show():
    _plot_counter[0] += 1
    filepath = PLOT_DIR / f"{_plot_prefix[0]}_{_plot_counter[0]:02d}.pdf"
    plt.savefig(filepath, bbox_inches='tight', dpi=150)
    print(f"  Saved: {filepath.name}")
    plt.close('all')
plt.show = save_instead_of_show


if __name__ == '__main__':
    print('Loading grid data...')
    data = load_grid_data()
    print(f'Opening results database...')
    res = powergama.Results(data, SQL_FILE, replace=False)

    num_hours = len(data.timerange)
    timeMaxMin = [0, num_hours]
    timestamps = pd.date_range(start=DATE_START, periods=num_hours, freq='h')

    year_hours = 8766
    yr2005_start = 14 * year_hours
    yr2005_end = yr2005_start + year_hours
    oneYear = [yr2005_start, yr2005_end]

    # Build zone->node index mapping
    zones = {}
    for _, row in data.node.iterrows():
        node_id = row['id']
        parts = node_id.split('_')
        if len(parts) >= 2 and parts[0][:2] == 'NO':
            zone = parts[0]
            if zone not in zones:
                zones[zone] = []
            node_idx = data.node['id'].tolist().index(node_id)
            zones[zone].append(node_idx)

    # ========== 1. Heatmap - nodal prices ==========
    print('\n1. Timeseries colour heatmap (nodal prices)...')
    _plot_prefix[0] = 'heatmap_price'
    _plot_counter[0] = 0
    try:
        res.plotTimeseriesColour(['NO', 'SE', 'FI', 'DK'], value='nodalprice')
    except Exception as e:
        print(f'  Error: {e}')

    # ========== 2. Demand Norway (year 2005) ==========
    print('\n2. Demand Norway (year 2005)...')
    _plot_prefix[0] = 'demand_NO'
    _plot_counter[0] = 0
    res.plotDemandPerArea(['NO'], timeMaxMin=oneYear)

    # ========== 3. Price duration curves ==========
    print('\n3. Price duration curves (all 30 years)...')
    _plot_prefix[0] = 'price_duration_curve'
    _plot_counter[0] = 0

    fig, ax = plt.subplots(figsize=(10, 6))
    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        zone_prices = np.zeros(num_hours)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, timeMaxMin)
            zone_prices += prices
        zone_prices /= len(node_indices)

        sorted_prices = np.sort(zone_prices)[::-1]
        pct = np.arange(1, len(sorted_prices) + 1) / len(sorted_prices) * 100
        ax.plot(pct, sorted_prices, label=zone, linewidth=1.2)

    ax.set_xlabel('Duration [%]')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Price Duration Curves - Norwegian Zones (30 years)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0, top=200)
    plt.show()

    # ========== 4. Annual average zone prices ==========
    print('\n4. Annual average zone prices...')
    _plot_prefix[0] = 'annual_zone_prices'
    _plot_counter[0] = 0

    fig, ax = plt.subplots(figsize=(12, 5))
    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        zone_prices = np.zeros(num_hours)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, timeMaxMin)
            zone_prices += prices
        zone_prices /= len(node_indices)

        ts = pd.Series(zone_prices, index=timestamps)
        annual = ts.resample('YE').mean()
        ax.plot(annual.index.year, annual.values, 'o-', label=zone, linewidth=1.5, markersize=4)

    ax.set_xlabel('Year')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Annual Average Zone Prices - Norwegian Zones')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.show()

    # ========== 5. Box plot of zone prices ==========
    print('\n5. Box plot of zone prices...')
    _plot_prefix[0] = 'zone_price_boxplot'
    _plot_counter[0] = 0

    fig, ax = plt.subplots(figsize=(8, 6))
    price_data = []
    labels = []
    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        zone_prices = np.zeros(num_hours)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, timeMaxMin)
            zone_prices += prices
        zone_prices /= len(node_indices)

        # Use monthly averages for box plot (less noisy)
        ts = pd.Series(zone_prices, index=timestamps)
        monthly = ts.resample('ME').mean()
        price_data.append(monthly.values)
        labels.append(zone)

    ax.boxplot(price_data, labels=labels)
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Zone Price Distribution (Monthly Averages)')
    ax.grid(True, alpha=0.3, axis='y')
    plt.show()

    print(f'\nAll plots saved to: {PLOT_DIR}')
    print('Done!')
