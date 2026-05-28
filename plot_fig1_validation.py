"""
Fig. 1 — Validation: PowerGAMA R3 (2020) vs Historical 2024 vs Hjelmeland EMPS.
Volume-weighted zone prices (Hjelmeland Eq. 5): Σ(p_t × d_t) / Σ(d_t).
Only Norwegian bidding zones.
"""

import pathlib
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import powergama

BASE_DIR = pathlib.Path(__file__).parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SYSTEM_PATH = DATA_PATH / 'system'

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

# Historical 2024 spot prices eks mva [EUR/MWh]
HIST_2024 = {'NO1': 42.0, 'NO2': 50.0, 'NO3': 28.0, 'NO4': 23.0, 'NO5': 41.0}

# Hjelmeland EMPS Baseline B (approx. from Figure 10)
HJEL_B = {'NO1': 55.0, 'NO2': 55.0, 'NO3': 28.0, 'NO4': 16.0, 'NO5': 50.0}


def load_grid(date_start, date_end):
    """Load grid data with R3 storage_price override."""
    data = powergama.GridData()
    data.readGridData(
        nodes=SYSTEM_PATH / 'node.csv',
        ac_branches=SYSTEM_PATH / 'branch.csv',
        dc_branches=SYSTEM_PATH / 'dcbranch.csv',
        generators=SYSTEM_PATH / 'generator.csv',
        consumers=SYSTEM_PATH / 'consumer.csv',
    )
    profiles = pd.read_csv(DATA_PATH / 'timeseries_profiles.csv',
                           index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= date_start) & (profiles.index <= date_end)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    data.storagevalue_filling = pd.read_csv(DATA_PATH / 'storage' / 'profiles_storval_filling.csv')
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # Override to R3 storage_price
    R3_SP = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}
    for zone, sp in R3_SP.items():
        mask = data.generator['node'].str.startswith(zone) & (data.generator['type'] == 'hydro')
        data.generator.loc[mask, 'storage_price'] = sp

    return data


def get_zone_prices_volume_weighted(res, db_path):
    """Volume-weighted zone price (Hjelmeland Eq. 5): Σ(p_t × d_t) / Σ(d_t).

    For each zone: weight each hour's price by actual demand at that hour,
    where demand_node_t = demand_avg × profile[demand_ref][t].
    """
    node_ids = res.grid.node['id'].tolist()
    node_zones = res.grid.node['zone'].tolist()
    consumers = res.grid.consumer
    profiles = res.grid.profiles
    T = len(res.timerange)

    # Build node index → zone mapping for NO zones only
    node_to_zone = {}
    for i, (nid, z) in enumerate(zip(node_ids, node_zones)):
        if z in NO_ZONES:
            node_to_zone[i] = z

    # Build hourly demand per node: demand_avg * profile_value
    # Group consumers by node
    node_demand_ts = {}  # node_idx -> array of hourly demand
    for node_idx, zone in node_to_zone.items():
        nid = node_ids[node_idx]
        cons = consumers[consumers['node'] == nid]
        if cons.empty:
            continue
        demand_ts = np.zeros(T)
        for _, c in cons.iterrows():
            prof_ref = c['demand_ref']
            davg = c['demand_avg']
            if prof_ref in profiles.columns:
                demand_ts += davg * profiles[prof_ref].values[:T]
            else:
                demand_ts += davg
        node_demand_ts[node_idx] = demand_ts

    # Extract hourly nodal prices from SQLite
    con = sqlite3.connect(str(db_path))
    no_node_indices = sorted(node_to_zone.keys())
    placeholders = ','.join('?' * len(no_node_indices))
    query = (f"SELECT timestep, indx, nodalprice FROM Res_Nodes "
             f"WHERE indx IN ({placeholders}) ORDER BY timestep, indx")
    rows = con.execute(query, no_node_indices).fetchall()
    con.close()

    # Organize prices: node_idx -> array
    node_prices = {ni: np.zeros(T) for ni in no_node_indices}
    for timestep, indx, price in rows:
        if indx in node_prices and timestep < T:
            node_prices[indx][timestep] = price

    # Volume-weighted average per zone
    zone_prices = {}
    for zone in NO_ZONES:
        sum_pd = 0.0  # Σ(price × demand)
        sum_d = 0.0   # Σ(demand)
        for node_idx, z in node_to_zone.items():
            if z != zone:
                continue
            if node_idx not in node_demand_ts or node_idx not in node_prices:
                continue
            d = node_demand_ts[node_idx]
            p = node_prices[node_idx]
            sum_pd += np.sum(p * d)
            sum_d += np.sum(d)
        if sum_d > 0:
            zone_prices[zone] = sum_pd / sum_d
        else:
            zone_prices[zone] = 0.0
    return zone_prices


# --- Load R3 single-year 2020 results ---
print('Loading R3 single-year 2020...')
db_2020 = SCENARIO_DIR / 'results' / 'powergama_r3_2020.sqlite'
data_2020 = load_grid(
    pd.Timestamp('2020-01-01', tz='UTC'),
    pd.Timestamp('2020-12-31 23:00:00', tz='UTC'),
)
res_2020 = powergama.Results(data_2020, db_2020, replace=False)
prices_2020 = get_zone_prices_volume_weighted(res_2020, db_2020)
print('R3 2020 prices (volume-weighted):', {z: f'{v:.1f}' for z, v in prices_2020.items()})

# --- Load R3 30-year results ---
print('Loading R3 30-year...')
db_30yr = SCENARIO_DIR / 'results' / 'powergama_r3_1991_2020.sqlite'
data_30yr = load_grid(
    pd.Timestamp('1991-01-01', tz='UTC'),
    pd.Timestamp('2020-12-31 23:00:00', tz='UTC'),
)
res_30yr = powergama.Results(data_30yr, db_30yr, replace=False)
prices_30yr = get_zone_prices_volume_weighted(res_30yr, db_30yr)
print('R3 30yr prices (volume-weighted):', {z: f'{v:.1f}' for z, v in prices_30yr.items()})

# --- Plot ---
x = np.arange(len(NO_ZONES))
width = 0.22

fig, ax = plt.subplots(figsize=(8, 5))

bars1 = ax.bar(x - 1.5*width, [HIST_2024[z] for z in NO_ZONES], width,
               label='Historical 2024 (spot eks mva)', color='#2ca02c',
               edgecolor='black', linewidth=0.5)
bars2 = ax.bar(x - 0.5*width, [prices_2020[z] for z in NO_ZONES], width,
               label='PowerGAMA R3 (weather yr 2020)', color='#1f77b4',
               edgecolor='black', linewidth=0.5)
bars3 = ax.bar(x + 0.5*width, [prices_30yr[z] for z in NO_ZONES], width,
               label='PowerGAMA R3 (30-yr avg)', color='#aec7e8',
               edgecolor='black', linewidth=0.5)
bars4 = ax.bar(x + 1.5*width, [HJEL_B[z] for z in NO_ZONES], width,
               label='Hjelmeland EMPS Baseline', color='#ff7f0e',
               edgecolor='black', linewidth=0.5)

for bars in [bars1, bars2, bars3, bars4]:
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=7)

ax.set_xlabel('Price Zone', fontsize=11)
ax.set_ylabel('Volume-Weighted Price [EUR/MWh]', fontsize=11)
ax.set_title('Baseline Price Validation — Norwegian Bidding Zones', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(NO_ZONES, fontsize=11)
ax.legend(fontsize=8.5, loc='upper right')
ax.set_ylim(0, 75)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
out_dir = BASE_DIR / 'IEEE'
out_dir.mkdir(exist_ok=True)
plt.savefig(out_dir / 'Fig1_validation_prices.pdf', dpi=300, bbox_inches='tight')
plt.savefig(out_dir / 'Fig1_validation_prices.png', dpi=300, bbox_inches='tight')
print('Saved: IEEE/Fig1_validation_prices.pdf and .png')
