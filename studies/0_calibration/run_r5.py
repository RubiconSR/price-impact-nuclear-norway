"""
R5 simulation — Single weather year 2010 for rapid calibration.

Changes from R3:
- Branch: R3 configuration (6 northern lines with increased capacity)
- storage_price: NO1=11.5, NO2=17.0, NO3=9.5, NO4=17.5, NO5=21.0
"""

import pathlib
import time
import sqlite3
import numpy as np
import pandas as pd
import powergama

# ============================================================
# Configuration
# ============================================================
SIM_YEAR = 2010
DATE_START = pd.Timestamp(f'{SIM_YEAR}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_r5_{SIM_YEAR}.sqlite'

SOLVER = 'glpk'
LOSS_METHOD = 0

# ============================================================
# Load grid data
# ============================================================
def load_grid_data():
    """Load and configure the Nordic power system grid data."""
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

    num_hours = len(data.timerange)
    print(f'Nodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}')
    print(f'Branches: {len(data.branch)}')
    print(f'Simulation: {num_hours} hours (year {SIM_YEAR})')

    return data


# ============================================================
# Run simulation
# ============================================================
def run_simulation(data):
    """Solve the LP market clearing problem."""
    SQL_FILE.parent.mkdir(parents=True, exist_ok=True)

    lp = powergama.LpProblem(grid=data, lossmethod=LOSS_METHOD)
    res = powergama.Results(data, SQL_FILE, replace=True)

    print(f'\nStarting simulation with {SOLVER} solver...')
    start = time.time()
    lp.solve(res, solver=SOLVER)
    elapsed = time.time() - start
    print(f'Simulation completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)')

    return res


# ============================================================
# Extract zone prices
# ============================================================
def extract_prices():
    """Extract average zone prices from results."""
    conn = sqlite3.connect(SQL_FILE)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    conn.close()

    prices = prices.merge(nodes, on='indx')
    prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    hist_target = {'NO1': 53.2, 'NO2': 63.6, 'NO3': 35.6, 'NO4': 23.6, 'NO5': 51.9}

    print('\n' + '=' * 70)
    print(f'R5 ZONE PRICES [EUR/MWh] — Weather year {SIM_YEAR}')
    print('=' * 70)
    print(f'{"Zone":<8} {"R5":>10} {"Hist target":>14} {"Deviation":>12} {"Dev %":>10}')
    print('-' * 56)

    zone_prices = {}
    for zone in no_zones:
        zone_data = prices[prices['zone'] == zone]
        avg = zone_data.groupby('timestep')['nodalprice'].mean().mean()
        zone_prices[zone] = avg
        h = hist_target[zone]
        dev = avg - h
        dev_pct = dev / h * 100
        print(f'{zone:<8} {avg:>10.2f} {h:>14.1f} {dev:>+12.2f} {dev_pct:>+10.1f}%')

    avg_r5 = np.mean(list(zone_prices.values()))
    avg_h = np.mean(list(hist_target.values()))
    print('-' * 56)
    print(f'{"Avg":<8} {avg_r5:>10.2f} {avg_h:>14.1f} {avg_r5-avg_h:>+12.2f} {(avg_r5-avg_h)/avg_h*100:>+10.1f}%')

    # Price ranking
    sorted_prices = sorted(zone_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'\nR5 ranking:     {" > ".join(f"{z} ({v:.1f})" for z, v in sorted_prices)}')
    print(f'Target ranking: NO2 > NO1 > NO5 > NO3 > NO4')

    return zone_prices


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print(f'R5 CASE — Weather year {SIM_YEAR} calibration run')
    print('=' * 60)

    data = load_grid_data()
    res = run_simulation(data)
    zone_prices = extract_prices()

    print(f'\nResults saved to: {SQL_FILE}')
