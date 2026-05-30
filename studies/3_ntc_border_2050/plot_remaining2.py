"""
Generate remaining custom plots.
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


if __name__ == '__main__':
    print('Loading grid data...')
    data = load_grid_data()
    print('Opening results database...')
    res = powergama.Results(data, SQL_FILE, replace=False)

    num_hours = len(data.timerange)
    timeMaxMin = [0, num_hours]
    timestamps = pd.date_range(start=DATE_START, periods=num_hours, freq='h')

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

    # Pre-compute zone prices (reused in multiple plots)
    print('Computing zone prices...')
    zone_prices_dict = {}
    for zone in sorted(zones.keys()):
        node_indices = zones[zone]
        zp = np.zeros(num_hours)
        for ni in node_indices:
            prices = res.getNodalPrices(ni, timeMaxMin)
            zp += prices
        zp /= len(node_indices)
        zone_prices_dict[zone] = zp
        print(f'  {zone}: mean={zp.mean():.2f} EUR/MWh')

    # ========== 1. Price duration curves ==========
    print('\n1. Price duration curves...')
    fig, ax = plt.subplots(figsize=(10, 6))
    for zone in sorted(zone_prices_dict.keys()):
        sorted_prices = np.sort(zone_prices_dict[zone])[::-1]
        pct = np.arange(1, len(sorted_prices) + 1) / len(sorted_prices) * 100
        ax.plot(pct, sorted_prices, label=zone, linewidth=1.2)
    ax.set_xlabel('Duration [%]')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Price Duration Curves - Norwegian Zones (30 years)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0, top=200)
    plt.savefig(PLOT_DIR / 'price_duration_curve_01.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: price_duration_curve_01.pdf')

    # ========== 2. Annual average zone prices ==========
    print('\n2. Annual average zone prices...')
    fig, ax = plt.subplots(figsize=(12, 5))
    for zone in sorted(zone_prices_dict.keys()):
        ts = pd.Series(zone_prices_dict[zone], index=timestamps)
        annual = ts.resample('YE').mean()
        ax.plot(annual.index.year, annual.values, 'o-', label=zone, linewidth=1.5, markersize=4)
    ax.set_xlabel('Year')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Annual Average Zone Prices - Norwegian Zones')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.savefig(PLOT_DIR / 'annual_zone_prices_01.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: annual_zone_prices_01.pdf')

    # ========== 3. Box plot of zone prices ==========
    print('\n3. Box plot of zone prices (monthly)...')
    fig, ax = plt.subplots(figsize=(8, 6))
    price_data = []
    labels = []
    for zone in sorted(zone_prices_dict.keys()):
        ts = pd.Series(zone_prices_dict[zone], index=timestamps)
        monthly = ts.resample('ME').mean()
        price_data.append(monthly.values)
        labels.append(zone)
    bp = ax.boxplot(price_data, labels=labels, patch_artist=True)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Zone Price Distribution (Monthly Averages, 30 years)')
    ax.grid(True, alpha=0.3, axis='y')
    plt.savefig(PLOT_DIR / 'zone_price_boxplot_01.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: zone_price_boxplot_01.pdf')

    # ========== 4. Seasonal pattern (avg by month of year) ==========
    print('\n4. Seasonal price pattern...')
    fig, ax = plt.subplots(figsize=(10, 5))
    for zone in sorted(zone_prices_dict.keys()):
        ts = pd.Series(zone_prices_dict[zone], index=timestamps)
        seasonal = ts.groupby(ts.index.month).mean()
        ax.plot(seasonal.index, seasonal.values, 'o-', label=zone, linewidth=1.5, markersize=5)
    ax.set_xlabel('Month')
    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title('Seasonal Price Pattern - Norwegian Zones (30-year average)')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.savefig(PLOT_DIR / 'seasonal_price_pattern_01.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: seasonal_price_pattern_01.pdf')

    # ========== 5. Price spread between zones ==========
    print('\n5. Price spread (NO1-NO4, NO5-NO3)...')
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # NO1 vs NO4 spread
    spread_14 = zone_prices_dict['NO1'] - zone_prices_dict['NO4']
    ts_14 = pd.Series(spread_14, index=timestamps)
    monthly_14 = ts_14.resample('ME').mean()
    axes[0].plot(monthly_14.index, monthly_14.values, linewidth=0.8, color='steelblue')
    axes[0].axhline(y=0, color='black', linewidth=0.5, linestyle='--')
    axes[0].set_ylabel('Price Spread [EUR/MWh]')
    axes[0].set_title(f'NO1 - NO4 Price Spread (monthly avg, mean={spread_14.mean():.1f})')
    axes[0].grid(True, alpha=0.3)

    # NO5 vs NO3 spread
    spread_53 = zone_prices_dict['NO5'] - zone_prices_dict['NO3']
    ts_53 = pd.Series(spread_53, index=timestamps)
    monthly_53 = ts_53.resample('ME').mean()
    axes[1].plot(monthly_53.index, monthly_53.values, linewidth=0.8, color='coral')
    axes[1].axhline(y=0, color='black', linewidth=0.5, linestyle='--')
    axes[1].set_ylabel('Price Spread [EUR/MWh]')
    axes[1].set_title(f'NO5 - NO3 Price Spread (monthly avg, mean={spread_53.mean():.1f})')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOT_DIR / 'price_spread_01.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: price_spread_01.pdf')

    print(f'\nAll plots saved to: {PLOT_DIR}')
    print('Done!')
