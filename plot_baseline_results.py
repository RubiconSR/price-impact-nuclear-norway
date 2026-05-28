"""
Plot baseline simulation results using PowerGAMA's built-in plotting functions.
Saves plots to PDF files since we're running in terminal mode.

Uses R5 results (the currently available simulation).
"""

import pathlib
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for terminal
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import powergama

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
PLOT_DIR = SCENARIO_DIR / 'plots'
PLOT_DIR.mkdir(parents=True, exist_ok=True)

ALL_AREAS = ['NO', 'SE', 'FI', 'DK']
# Norwegian zones are nodes, not areas. For zone-level plots we use custom code.
NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

# ============================================================
# Load grid data (same as run_baseline.py)
# ============================================================
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

    profiles = pd.read_csv(
        DATA_PATH / 'timeseries_profiles.csv',
        index_col=0,
        parse_dates=True,
    )
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
# Monkey-patch plt.show to save instead of display
# ============================================================
_plot_counter = [0]
_plot_prefix = ['plot']

def save_instead_of_show():
    """Save current figure to PDF instead of showing it."""
    _plot_counter[0] += 1
    filepath = PLOT_DIR / f"{_plot_prefix[0]}_{_plot_counter[0]:02d}.pdf"
    plt.savefig(filepath, bbox_inches='tight', dpi=150)
    print(f"  Saved: {filepath.name}")
    plt.close('all')

# Replace plt.show with our save function
plt.show = save_instead_of_show


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('Loading grid data...')
    data = load_grid_data()

    print(f'Opening results database: {SQL_FILE}')
    res = powergama.Results(data, SQL_FILE, replace=False)

    num_hours = len(data.timerange)
    timeMaxMin = [0, num_hours]

    # --- Show one year (2005) for detailed timeseries plots ---
    # 2005 starts at hour index: (2005-1991)*8766 = 122,724
    # We'll use approximate indices
    year_hours = 8766  # avg hours per year
    yr2005_start = 14 * year_hours  # 1991 + 14 = 2005
    yr2005_end = yr2005_start + year_hours
    oneYear = [yr2005_start, yr2005_end]

    # ========== 1. Area Prices (Nordic countries, 1 year) ==========
    print('\n1. Area prices - Nordic countries (year 2005)...')
    _plot_prefix[0] = 'area_price_nordic_2005'
    _plot_counter[0] = 0
    res.plotAreaPrice(ALL_AREAS, timeMaxMin=oneYear)

    # ========== 2. Area Price Norway (full period) ==========
    print('\n2. Area price - Norway (full 30-year period)...')
    _plot_prefix[0] = 'area_price_NO_30yr'
    _plot_counter[0] = 0
    res.plotAreaPrice(['NO'], timeMaxMin=timeMaxMin)

    # ========== 3. Zone Prices (custom - NO zones as weighted node prices) ==========
    print('\n3. Zone prices - Norwegian zones (full period, monthly avg)...')
    _plot_prefix[0] = 'zone_prices_NO'
    _plot_counter[0] = 0

    # Get zone prices using node-level data
    zones = {}
    for _, row in data.node.iterrows():
        node_id = row['id']
        # Extract zone from node name (e.g. NO1_1 -> NO1)
        parts = node_id.split('_')
        if len(parts) >= 2 and parts[0][:2] == 'NO':
            zone = parts[0]  # e.g. NO1, NO2, etc.
            if zone not in zones:
                zones[zone] = []
            node_idx = data.node['id'].tolist().index(node_id)
            zones[zone].append(node_idx)

    fig, ax = plt.subplots(figsize=(14, 5))
    timestamps = pd.date_range(start=DATE_START, periods=num_hours, freq='h')

    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        # Simple average of nodal prices in zone
        zone_prices = np.zeros(num_hours)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, timeMaxMin)
            zone_prices += prices
        zone_prices /= len(node_indices)

        # Resample to monthly for readability
        ts = pd.Series(zone_prices, index=timestamps)
        monthly = ts.resample('ME').mean()
        ax.plot(monthly.index, monthly.values, label=zone, linewidth=1.2)

    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Norwegian Zone Prices (Monthly Average)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.show()

    # ========== 4. Zone Prices (1 year - weekly) ==========
    print('\n4. Zone prices - Norwegian zones (year 2005, weekly avg)...')
    _plot_prefix[0] = 'zone_prices_NO_2005'
    _plot_counter[0] = 0

    fig, ax = plt.subplots(figsize=(12, 5))
    ts_2005 = timestamps[yr2005_start:yr2005_end]

    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        zone_prices = np.zeros(yr2005_end - yr2005_start)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, oneYear)
            zone_prices += prices
        zone_prices /= len(node_indices)

        ts = pd.Series(zone_prices, index=ts_2005)
        weekly = ts.resample('W').mean()
        ax.plot(weekly.index, weekly.values, label=zone, linewidth=1.5)

    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Norwegian Zone Prices - 2005 (Weekly Average)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.show()

    # ========== 5. Energy Mix (Nordic countries) ==========
    print('\n5. Energy mix (stacked bar, Nordic countries)...')
    _plot_prefix[0] = 'energy_mix_nordic'
    _plot_counter[0] = 0
    res.plotEnergyMix(areas=ALL_AREAS, timeMaxMin=timeMaxMin, relative=False)

    # ========== 6. Energy Mix relative ==========
    print('\n6. Energy mix relative (Nordic countries)...')
    _plot_prefix[0] = 'energy_mix_relative'
    _plot_counter[0] = 0
    res.plotEnergyMix(areas=ALL_AREAS, timeMaxMin=timeMaxMin, relative=True)

    # ========== 7. Generation per area - Norway (one year) ==========
    print('\n7. Generation in Norway (year 2005)...')
    _plot_prefix[0] = 'generation_NO'
    _plot_counter[0] = 0
    res.plotGenerationPerArea('NO', timeMaxMin=oneYear)

    # ========== 8. Generation per area - all Nordic (one year) ==========
    print('\n8. Generation per Nordic country (year 2005)...')
    _plot_prefix[0] = 'generation_area'
    _plot_counter[0] = 0
    for area in ALL_AREAS:
        print(f'  {area}...')
        res.plotGenerationPerArea(area, timeMaxMin=oneYear)

    # ========== 9. Storage filling - Norway ==========
    print('\n9. Storage filling Norway (full period)...')
    _plot_prefix[0] = 'storage_filling_NO'
    _plot_counter[0] = 0
    try:
        res.plotStoragePerArea('NO', absolute=False, timeMaxMin=timeMaxMin)
    except Exception as e:
        print(f'  Error: {e}')

    # ========== 10. Timeseries colour heatmap ==========
    print('\n10. Timeseries colour heatmap (nodal prices)...')
    _plot_prefix[0] = 'heatmap_price'
    _plot_counter[0] = 0
    try:
        res.plotTimeseriesColour(['NO', 'SE', 'FI', 'DK'], value='nodalprice')
    except Exception as e:
        print(f'  Error: {e}')

    # ========== 11. Demand per area ==========
    print('\n11. Demand in Norway (year 2005)...')
    _plot_prefix[0] = 'demand_NO'
    _plot_counter[0] = 0
    res.plotDemandPerArea(['NO'], timeMaxMin=oneYear)

    # ========== 12. Zone price duration curves ==========
    print('\n12. Zone price duration curves (all 30 years)...')
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
        hours = np.arange(1, len(sorted_prices) + 1)
        pct = hours / len(sorted_prices) * 100
        ax.plot(pct, sorted_prices, label=zone, linewidth=1.2)

    ax.set_xlabel('Duration [%]')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Price Duration Curves - Norwegian Zones (30 years)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0, top=200)
    plt.show()

    # ========== Summary ==========
    print(f'\nAll plots saved to: {PLOT_DIR}')
    print('Done!')
