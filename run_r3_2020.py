"""
R3 single-year validation — Weather year 2020 vs historical 2024 spot prices (eks mva).

E&A Section 6.3 used weather year 2020 as representative for 2024.
generator.csv has R6 storage_price values; this script overrides to R3 values.
storage_ini = 0.6 in generator.csv matches NVE January 2024 filling (~60%).

storage_price R3: NO1=13.0, NO2=17.0, NO3=9.5, NO4=14.0, NO5=17.0
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
SIM_YEAR = 2020  # Leap year: 8784 hours
DATE_START = pd.Timestamp(f'{SIM_YEAR}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_r3_{SIM_YEAR}.sqlite'

SOLVER = 'glpk'
LOSS_METHOD = 0

# R3 storage_price values (override R6 values in generator.csv)
R3_SP = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}

# Historical 2024 spot prices eks mva [EUR/MWh]
HIST_2024 = {'NO1': 42.0, 'NO2': 50.0, 'NO3': 28.0, 'NO4': 23.0, 'NO5': 41.0}


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

    # Override storage_price from R6 → R3 values
    print('\nOverriding storage_price to R3 values:')
    for zone, sp in R3_SP.items():
        mask = data.generator['node'].str.startswith(zone) & (data.generator['type'] == 'hydro')
        n_changed = mask.sum()
        data.generator.loc[mask, 'storage_price'] = sp
        print(f'  {zone}: storage_price = {sp} ({n_changed} generators)')

    # Verify override
    print('\nVerification — storage_price per zone (hydro only):')
    hydro = data.generator[data.generator['type'] == 'hydro'].copy()
    hydro['zone'] = hydro['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
    for zone in ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']:
        sp_vals = hydro.loc[hydro['zone'] == zone, 'storage_price'].unique()
        print(f'  {zone}: {sp_vals}')

    num_hours = len(data.timerange)
    print(f'\nNodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}')
    print(f'Branches: {len(data.branch)}')
    print(f'Simulation: {num_hours} hours (year {SIM_YEAR}, {"leap" if num_hours == 8784 else "normal"})')

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
    """Extract average zone prices and compare to 2024 historical."""
    conn = sqlite3.connect(SQL_FILE)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    conn.close()

    prices = prices.merge(nodes, on='indx')
    prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

    print('\n' + '=' * 70)
    print(f'R3 ZONE PRICES [EUR/MWh] — Weather year {SIM_YEAR} vs Hist 2024 eks mva')
    print('=' * 70)
    print(f'{"Zone":<8} {"R3-2020":>10} {"Hist 2024":>12} {"Deviation":>12} {"Dev %":>10}')
    print('-' * 56)

    zone_prices = {}
    for zone in no_zones:
        zone_data = prices[prices['zone'] == zone]
        avg = zone_data.groupby('timestep')['nodalprice'].mean().mean()
        zone_prices[zone] = avg
        h = HIST_2024[zone]
        dev = avg - h
        dev_pct = dev / h * 100
        print(f'{zone:<8} {avg:>10.2f} {h:>12.1f} {dev:>+12.2f} {dev_pct:>+10.1f}%')

    avg_r3 = np.mean(list(zone_prices.values()))
    avg_h = np.mean(list(HIST_2024.values()))
    print('-' * 56)
    print(f'{"Avg":<8} {avg_r3:>10.2f} {avg_h:>12.1f} {avg_r3-avg_h:>+12.2f} {(avg_r3-avg_h)/avg_h*100:>+10.1f}%')

    # Price ranking
    sorted_prices = sorted(zone_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'\nR3-2020 ranking:  {" > ".join(f"{z} ({v:.1f})" for z, v in sorted_prices)}')
    print(f'Target ranking:   NO2 > NO1 > NO5 > NO3 > NO4')

    return zone_prices


# ============================================================
# Energy balance and generation mix
# ============================================================
def extract_energy_balance():
    """Extract energy balance and generation mix from results."""
    conn = sqlite3.connect(SQL_FILE)
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_output = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()

    # Merge generator info
    gen_output = gen_output.merge(generators, on='indx', suffixes=('', '_gen'))

    # Zone and country from node
    gen_output['zone'] = gen_output['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
    gen_output['country'] = gen_output['node'].str.extract(r'(NO|SE|FI|DK)')

    # Total generation by type (Norway only)
    no_gen = gen_output[gen_output['country'] == 'NO']
    gen_by_type = no_gen.groupby('type')['output'].sum() / 1e6  # MWh -> TWh

    print('\n' + '=' * 70)
    print(f'NORWAY GENERATION MIX — Weather year {SIM_YEAR}')
    print('=' * 70)
    print(f'{"Type":<20} {"TWh":>10}')
    print('-' * 32)
    for gtype in sorted(gen_by_type.index):
        print(f'{gtype:<20} {gen_by_type[gtype]:>10.2f}')
    total_gen = gen_by_type.sum()
    print('-' * 32)
    print(f'{"TOTAL":<20} {total_gen:>10.2f}')

    # Total generation by type and zone (Norway)
    gen_zone_type = no_gen.groupby(['zone', 'type'])['output'].sum() / 1e6
    print(f'\n{"Zone":<8} {"Hydro":>10} {"RoR":>10} {"Wind":>10} {"Thermal":>10} {"Other":>10} {"Total":>10}')
    print('-' * 70)
    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    hydro_types = ['hydro']
    ror_types = ['ror']
    wind_types = ['wind_on', 'wind_off']
    thermal_types = ['fossil_gas']
    for zone in no_zones:
        zone_gen = gen_zone_type.get(zone, pd.Series(dtype=float))
        h = sum(zone_gen.get(t, 0) for t in hydro_types)
        r = sum(zone_gen.get(t, 0) for t in ror_types)
        w = sum(zone_gen.get(t, 0) for t in wind_types)
        th = sum(zone_gen.get(t, 0) for t in thermal_types)
        other = sum(v for k, v in zone_gen.items() if k not in hydro_types + ror_types + wind_types + thermal_types)
        zt = h + r + w + th + other
        print(f'{zone:<8} {h:>10.2f} {r:>10.2f} {w:>10.2f} {th:>10.2f} {other:>10.2f} {zt:>10.2f}')

    # Total consumption — read from consumer.csv since Grid_Consumers is empty
    consumer_csv = DATA_PATH / 'system' / 'consumer.csv'
    consumers = pd.read_csv(consumer_csv)
    no_consumers = consumers[consumers['node'].str.startswith('NO')]
    num_hours = len(gen_output['timestep'].unique())
    total_demand = no_consumers['demand_avg'].sum() * num_hours / 1e6  # TWh

    print(f'\nNorway total demand (approx): {total_demand:.2f} TWh')
    print(f'Norway total generation:      {total_gen:.2f} TWh')
    print(f'Net export (gen - demand):    {total_gen - total_demand:.2f} TWh')

    return gen_by_type


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 70)
    print(f'R3 VALIDATION — Weather year {SIM_YEAR} vs Historical 2024 eks mva')
    print(f'Solver: {SOLVER}')
    print(f'storage_price R3: {R3_SP}')
    print('=' * 70)

    data = load_grid_data()
    res = run_simulation(data)
    zone_prices = extract_prices()
    gen_mix = extract_energy_balance()

    print(f'\nResults saved to: {SQL_FILE}')
