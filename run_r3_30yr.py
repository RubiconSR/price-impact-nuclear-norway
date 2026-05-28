"""
R3 30-year baseline simulation — Proper comparison with Hjelmeland B.

Uses R3 storage_price calibration (best match to hist. 2024):
  NO1=13.0, NO2=17.0, NO3=9.5, NO4=14.0, NO5=17.0

generator.csv has R6 values; this script overrides to R3 in-memory.
GLPK solver for consistency with other 30-year runs.
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

BASE_DIR = pathlib.Path(__file__).parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_r3_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'

SOLVER = 'glpk'
LOSS_METHOD = 0

# R3 storage_price values (override R6 values in generator.csv)
R3_SP = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}

# Hjelmeland B approximate prices (from Figure 10)
HJEL_B = {'NO1': 55, 'NO2': 55, 'NO3': 28, 'NO4': 16, 'NO5': 50}

# Historical 2024 spot prices eks mva [EUR/MWh]
HIST_2024 = {'NO1': 42.0, 'NO2': 50.0, 'NO3': 28.0, 'NO4': 23.0, 'NO5': 41.0}

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']


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

    # Override storage_price from R6 → R3 values
    print('\nOverriding storage_price to R3 values:')
    for zone, sp in R3_SP.items():
        mask = data.generator['node'].str.startswith(zone) & (data.generator['type'] == 'hydro')
        n_changed = mask.sum()
        data.generator.loc[mask, 'storage_price'] = sp
        print(f'  {zone}: storage_price = {sp} ({n_changed} generators)')

    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)
    print(f'\nNodes: {len(data.node)}')
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
    print(f'Simulation completed in {elapsed:.1f} seconds ({elapsed/60:.1f} min, {elapsed/3600:.1f} hr)')

    return res


# ============================================================
# Extract results
# ============================================================
def extract_results():
    conn = sqlite3.connect(SQL_FILE)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_out = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()

    num_hours = prices['timestep'].nunique()
    num_years = num_hours / (365.2425 * 24)

    # --- Zone prices ---
    prices = prices.merge(nodes, on='indx')
    prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    print('\n' + '=' * 90)
    print(f'R3 30-YEAR ZONE PRICES [EUR/MWh] — {SIM_YEAR_START}-{SIM_YEAR_END}')
    print('=' * 90)
    print(f'{"Zone":<6} {"R3 30yr":>10} {"Hjel. B":>10} {"Avvik":>10} {"Avvik%":>8} {"Hist24":>10} {"vs Hist":>10}')
    print('-' * 68)

    zone_prices = {}
    for z in NO_ZONES:
        zp = prices[prices['zone'] == z].groupby('timestep')['nodalprice'].mean()
        avg = zp.mean()
        zone_prices[z] = avg
        h = HJEL_B[z]
        hist = HIST_2024[z]
        print(f'{z:<6} {avg:>10.2f} {h:>10.1f} {avg-h:>+10.2f} {(avg-h)/h*100:>+7.0f}% {hist:>10.1f} {avg-hist:>+10.2f}')

    avg_r3 = np.mean(list(zone_prices.values()))
    avg_h = np.mean(list(HJEL_B.values()))
    avg_hist = np.mean(list(HIST_2024.values()))
    print('-' * 68)
    print(f'{"Avg":<6} {avg_r3:>10.2f} {avg_h:>10.1f} {avg_r3-avg_h:>+10.2f} {(avg_r3-avg_h)/avg_h*100:>+7.0f}% {avg_hist:>10.1f} {avg_r3-avg_hist:>+10.2f}')

    # Price ranking
    sorted_p = sorted(zone_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'\nR3 ranking:        {" > ".join(f"{z} ({v:.1f})" for z, v in sorted_p)}')
    print(f'Hjelmeland:        NO1 ≈ NO2 > NO5 > NO3 > NO4')
    print(f'Target (hist):     NO2 > NO1 > NO5 > NO3 > NO4')

    # Price volatility
    print(f'\nPrice std.dev [EUR/MWh]:')
    for z in NO_ZONES:
        zp = prices[prices['zone'] == z].groupby('timestep')['nodalprice'].mean()
        print(f'  {z}: std={zp.std():.1f}, median={zp.median():.1f}, P10={zp.quantile(0.1):.1f}, P90={zp.quantile(0.9):.1f}')

    # --- Generation mix ---
    gen_out = gen_out.merge(generators, on='indx', suffixes=('', '_g'))
    gen_out['country'] = gen_out['node'].str.extract(r'(NO|SE|FI|DK)')
    gen_out['zone'] = gen_out['node'].str.extract(r'(NO\d)')

    no_gen = gen_out[gen_out['country'] == 'NO']
    gen_by_type = no_gen.groupby('type')['output'].sum() / 1e6 / num_years

    print(f'\n{"="*70}')
    print(f'NORWAY GENERATION MIX [TWh/yr] — R3 30-year average')
    print(f'{"="*70}')
    total_gen = 0
    for gtype in ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'fossil_gas', 'biomass']:
        val = gen_by_type.get(gtype, 0)
        total_gen += val
        print(f'  {gtype:15s}: {val:8.2f} TWh/yr')
    print(f'  {"TOTAL":15s}: {total_gen:8.2f} TWh/yr')

    # Per zone
    zone_type_gen = no_gen.groupby(['zone', 'type'])['output'].sum() / 1e6 / num_years
    print(f'\nGeneration per zone [TWh/yr]:')
    for z in NO_ZONES:
        parts = []
        z_total = 0
        for gtype in ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'fossil_gas', 'biomass']:
            v = zone_type_gen.get((z, gtype), 0)
            z_total += v
            if v > 0.01:
                parts.append(f'{gtype}={v:.1f}')
        print(f'  {z}: {z_total:.1f} TWh ({", ".join(parts)})')

    # Demand
    cons = pd.read_csv(DATA_PATH / 'system' / 'consumer.csv')
    no_cons = cons[cons['node'].str.startswith('NO')]
    total_demand = no_cons['demand_avg'].sum() * 8760 / 1e6
    print(f'\nNorway demand:      {total_demand:.1f} TWh/yr')
    print(f'Norway generation:  {total_gen:.1f} TWh/yr')
    print(f'Net export:         {total_gen - total_demand:+.1f} TWh/yr')

    # --- Seasonal prices ---
    hours = pd.date_range(f'{SIM_YEAR_START}-01-01', periods=num_hours, freq='h')
    ts_map = pd.DataFrame({'timestep': range(len(hours)), 'month': hours.month})
    prices_s = prices.merge(ts_map, on='timestep')
    prices_s['season'] = prices_s['month'].map({
        12: 'Winter', 1: 'Winter', 2: 'Winter',
        3: 'Spring', 4: 'Spring', 5: 'Spring',
        6: 'Summer', 7: 'Summer', 8: 'Summer',
        9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
    })
    print(f'\nSeasonal prices [EUR/MWh]:')
    for season in ['Winter', 'Spring', 'Summer', 'Autumn']:
        sp = prices_s[prices_s['season'] == season]
        row = f'  {season:8s}:'
        for z in NO_ZONES:
            zsp = sp[sp['zone'] == z].groupby('timestep')['nodalprice'].mean()
            row += f'  {z}={zsp.mean():.1f}'
        print(row)

    # --- Monthly reservoir filling ---
    try:
        conn2 = sqlite3.connect(SQL_FILE)
        storage = pd.read_sql_query("SELECT timestep, indx, storage FROM Res_Storage", conn2)
        conn2.close()

        gen_csv = pd.read_csv(DATA_PATH / 'system' / 'generator.csv')
        gen_csv = gen_csv[gen_csv['pmax'] > 0].reset_index(drop=True)

        hydro_gens = generators[generators['type'] == 'hydro'].copy()
        hydro_gens['zone'] = hydro_gens['node'].str.extract(r'(NO\d)')
        no_hydro = hydro_gens[hydro_gens['zone'].notna()]
        no_hydro = no_hydro.merge(gen_csv[['node', 'type', 'storage_cap']].drop_duplicates(),
                                   on=['node', 'type'], how='left')

        storage_no = storage[storage['indx'].isin(no_hydro['indx'])].merge(
            no_hydro[['indx', 'zone', 'storage_cap']], on='indx')
        storage_no['filling'] = storage_no['storage'] / storage_no['storage_cap']
        storage_no = storage_no.merge(ts_map, on='timestep')

        print(f'\nMonthly reservoir filling (Norway total, capacity-weighted):')
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for m in range(1, 13):
            ms = storage_no[storage_no['month'] == m]
            if len(ms) > 0:
                fill = np.average(ms['filling'], weights=ms['storage_cap'])
                print(f'  {months[m-1]}: {fill:.3f} ({fill*100:.1f}%)')

        print(f'\nReservoir filling per zone:')
        print(f'{"Zone":<6}', end='')
        for m in months:
            print(f' {m:>5}', end='')
        print()
        for z in NO_ZONES:
            print(f'{z:<6}', end='')
            for m in range(1, 13):
                ms = storage_no[(storage_no['month'] == m) & (storage_no['zone'] == z)]
                if len(ms) > 0:
                    fill = np.average(ms['filling'], weights=ms['storage_cap'])
                    print(f' {fill:>5.2f}', end='')
                else:
                    print(f' {"N/A":>5}', end='')
            print()
    except Exception as e:
        print(f'\nStorage extraction failed: {e}')

    return zone_prices


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 70)
    print('R3 BASELINE — 30-year simulation (1991-2020)')
    print(f'Solver: {SOLVER}')
    print(f'storage_price R3: {R3_SP}')
    print('=' * 70)

    data = load_grid_data()
    res = run_simulation(data)
    zone_prices = extract_results()

    print(f'\nResults saved to: {SQL_FILE}')
