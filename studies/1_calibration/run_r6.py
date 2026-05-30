"""
R6 simulation — 30-year run with HiGHS solver.

storage_price: NO1=8.0, NO2=18.5, NO3=7.0, NO4=23.0, NO5=27.0
Branch: R3 configuration
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
SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_r6_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'

SOLVER = 'highs'
LOSS_METHOD = 0

# ============================================================
# Load grid data
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

    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)
    print(f'Nodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}')
    print(f'Branches: {len(data.branch)}')
    print(f'Simulation: {num_hours} hours ({num_years:.1f} years)')

    return data


# ============================================================
# Run simulation
# ============================================================
def run_simulation(data):
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
    conn = sqlite3.connect(SQL_FILE)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    conn.close()

    prices = prices.merge(nodes, on='indx')
    prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    hist_target = {'NO1': 53.2, 'NO2': 63.6, 'NO3': 35.6, 'NO4': 23.6, 'NO5': 51.9}
    r3_prices = {'NO1': 58.70, 'NO2': 60.81, 'NO3': 39.24, 'NO4': 16.61, 'NO5': 42.58}
    r5_prices = {'NO1': 59.67, 'NO2': 61.19, 'NO3': 40.38, 'NO4': 18.22, 'NO5': 45.91}

    print('\n' + '=' * 90)
    print(f'R6 vs R5 vs R3 ZONE PRICES [EUR/MWh] — 30-year average (1991-2020)')
    print('=' * 90)
    print(f'{"Zone":<8} {"R3":>8} {"R5":>8} {"R6":>8} {"Hist":>8} {"R6-Hist":>10} {"R6-Hist%":>10}')
    print('-' * 65)

    zone_prices = {}
    for zone in no_zones:
        zone_data = prices[prices['zone'] == zone]
        avg = zone_data.groupby('timestep')['nodalprice'].mean().mean()
        zone_prices[zone] = avg
        r3 = r3_prices[zone]
        r5 = r5_prices[zone]
        h = hist_target[zone]
        print(f'{zone:<8} {r3:>8.1f} {r5:>8.1f} {avg:>8.2f} {h:>8.1f} {avg-h:>+10.2f} {(avg-h)/h*100:>+10.1f}%')

    r3_avg = np.mean(list(r3_prices.values()))
    r5_avg = np.mean(list(r5_prices.values()))
    r6_avg = np.mean(list(zone_prices.values()))
    h_avg = np.mean(list(hist_target.values()))
    print('-' * 65)
    print(f'{"Avg":<8} {r3_avg:>8.1f} {r5_avg:>8.1f} {r6_avg:>8.2f} {h_avg:>8.1f} {r6_avg-h_avg:>+10.2f} {(r6_avg-h_avg)/h_avg*100:>+10.1f}%')

    sorted_prices = sorted(zone_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'\nR6 ranking:     {" > ".join(f"{z} ({v:.1f})" for z, v in sorted_prices)}')
    print(f'Target ranking: NO2 > NO1 > NO5 > NO3 > NO4')

    # Storage price effect
    print(f'\n{"="*90}')
    print(f'STORAGE_PRICE KALIBRERINGSOVERSIKT')
    print(f'{"="*90}')
    sp_r3 = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}
    sp_r5 = {'NO1': 11.5, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 17.5, 'NO5': 21.0}
    sp_r6 = {'NO1': 8.0, 'NO2': 18.5, 'NO3': 7.0, 'NO4': 23.0, 'NO5': 27.0}
    print(f'{"Zone":<8} {"sp R3":>8} {"sp R5":>8} {"sp R6":>8} {"Pris R3":>10} {"Pris R5":>10} {"Pris R6":>10} {"Hist":>8}')
    print('-' * 80)
    for zone in no_zones:
        print(f'{zone:<8} {sp_r3[zone]:>8.1f} {sp_r5[zone]:>8.1f} {sp_r6[zone]:>8.1f} {r3_prices[zone]:>10.1f} {r5_prices[zone]:>10.1f} {zone_prices[zone]:>10.2f} {hist_target[zone]:>8.1f}')

    return zone_prices


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('R6 CASE — 30-year simulation with HiGHS')
    print('storage_price: NO1=8, NO2=18.5, NO3=7, NO4=23, NO5=27')
    print('=' * 60)

    data = load_grid_data()
    res = run_simulation(data)
    zone_prices = extract_prices()

    print(f'\nResults saved to: {SQL_FILE}')
