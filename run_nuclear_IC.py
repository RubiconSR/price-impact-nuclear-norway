"""
Nuclear IC scenarios — 30-year simulation (1991-2020) with GLPK solver.

IC = Increased Consumption: MD + 22 TWh baseload (502.2 MW per NO zone).
Total Norwegian demand: 230 TWh (208 + 22).

Scenarios:
  BL_IC:   No nuclear
  SMR1_IC: 1500 MW (300 MW x 5 zones)
  SMR3_IC: 4500 MW (900 MW x 5 zones)
  SMR6_IC: 9000 MW (1800 MW x 5 zones)

SMR parameters: 300 MW unit, pmin=30 MW (10%), fuelcost=9.37 EUR/MWh, const profile.
R3 calibrated storage_price. 2050 IC system (42.6 GW hydro, 8.2 GW wind_on,
3.6 GW wind_off, 11.3 GW solar, 230 TWh demand).
"""

import sys
import os
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
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'nuclear_IC'
DATA_PATH = SCENARIO_DIR / 'data'
RESULTS_DIR = SCENARIO_DIR  # Each scenario has its own subfolder

# Timeseries profiles path (symlink or direct reference)
TIMESERIES_PATH = DATA_PATH / 'timeseries_profiles.csv'
TIMESERIES_FALLBACK = BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'timeseries_profiles.csv'

SOLVER = 'glpk'
LOSS_METHOD = 0

# SMR configuration per zone [MW]
SMR_SCENARIOS = {
    'BL_IC':   {'NO1': 0,    'NO2': 0,    'NO3': 0,    'NO4': 0,    'NO5': 0},
    'SMR1_IC': {'NO1': 300,  'NO2': 300,  'NO3': 300,  'NO4': 300,  'NO5': 300},
    'SMR3_IC': {'NO1': 900,  'NO2': 900,  'NO3': 900,  'NO4': 900,  'NO5': 900},
    'SMR6_IC': {'NO1': 1800, 'NO2': 1800, 'NO3': 1800, 'NO4': 1800, 'NO5': 1800},
}

# SMR unit parameters
SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10
SMR_FUELCOST = 9.37  # EUR/MWh

# Node placement for SMR (one node per zone)
SMR_NODES = {'NO1': 'NO1_3', 'NO2': 'NO2_1', 'NO3': 'NO3_1', 'NO4': 'NO4_1', 'NO5': 'NO5_1'}

# IC extra demand per zone
IC_EXTRA_MW = 502.2  # 22 TWh / 8760 h / 5 zones


# ============================================================
# Ensure timeseries symlink exists
# ============================================================
def ensure_timeseries():
    """Create timeseries symlink if it doesn't exist."""
    if TIMESERIES_PATH.exists() or TIMESERIES_PATH.is_symlink():
        return TIMESERIES_PATH
    # Try to create symlink
    try:
        os.symlink(TIMESERIES_FALLBACK, TIMESERIES_PATH)
        print(f'Created symlink: {TIMESERIES_PATH} -> {TIMESERIES_FALLBACK}')
        return TIMESERIES_PATH
    except OSError:
        print(f'Could not create symlink, using direct path: {TIMESERIES_FALLBACK}')
        return TIMESERIES_FALLBACK


# ============================================================
# Load grid data
# ============================================================
def load_grid_data(scenario_name):
    """Load grid data and add SMR generators for the given scenario."""
    system_path = DATA_PATH / 'system'

    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )

    # Timeseries profiles
    ts_path = ensure_timeseries()
    profiles = pd.read_csv(
        ts_path,
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

    # Filter out zero-capacity generators
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # Verify IC demand
    no_cons = data.consumer[data.consumer['node'].str.startswith('NO')]
    total_no_demand_twh = no_cons['demand_avg'].sum() * 8760 / 1e6
    print(f'\nNorwegian demand: {total_no_demand_twh:.1f} TWh/yr (target: 230 TWh)')
    ic_rows = data.consumer[data.consumer['demand_ref'] == 'load_const']
    if len(ic_rows) > 0:
        ic_demand_twh = ic_rows['demand_avg'].sum() * 8760 / 1e6
        print(f'  IC baseload addition: {ic_demand_twh:.1f} TWh/yr ({len(ic_rows)} consumers)')

    # Add SMR generators
    smr_caps = SMR_SCENARIOS[scenario_name]
    total_smr = sum(smr_caps.values())
    if total_smr > 0:
        print(f'\nAdding SMR capacity: {total_smr} MW total')
        new_rows = []
        for zone, cap_mw in smr_caps.items():
            if cap_mw <= 0:
                continue
            n_units = int(cap_mw / SMR_UNIT_MW)
            node = SMR_NODES[zone]
            for i in range(n_units):
                row = {
                    'Kolonne1': data.generator['Kolonne1'].max() + 1 + len(new_rows),
                    'node': node,
                    'desc': f'{node} nuclear SMR unit {i+1}',
                    'type': 'nuclear',
                    'pmax': SMR_UNIT_MW,
                    'pmin': SMR_UNIT_MW * SMR_PMIN_FRAC,
                    'fuelcost': SMR_FUELCOST,
                    'inflow_fac': 1.0,
                    'inflow_ref': 'const',
                    'storage_cap': 0.0,
                    'storage_price': 1.0,
                    'storval_filling_ref': 'const',
                    'storval_time_ref': 'const',
                    'storage_ini': 0.0,
                    'pump_cap': 0.0,
                    'pump_efficiency': 0.0,
                    'pump_deadband': 0.0,
                }
                new_rows.append(row)
            print(f'  {zone} ({node}): {n_units} x {SMR_UNIT_MW} MW = {cap_mw} MW')

        new_df = pd.DataFrame(new_rows)
        data.generator = pd.concat([data.generator, new_df], ignore_index=True)

    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)
    print(f'\nNodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}')
    print(f'Consumers: {len(data.consumer)}')
    print(f'Branches: {len(data.branch)}')
    print(f'Simulation: {num_hours} hours ({num_years:.1f} years)')

    return data


# ============================================================
# Run simulation
# ============================================================
def run_simulation(data, sql_file):
    """Solve the LP market clearing problem."""
    sql_file.parent.mkdir(parents=True, exist_ok=True)

    lp = powergama.LpProblem(grid=data, lossmethod=LOSS_METHOD)
    res = powergama.Results(data, sql_file, replace=True)

    print(f'\nStarting simulation with {SOLVER} solver...')
    start = time.time()
    lp.solve(res, solver=SOLVER)
    elapsed = time.time() - start
    print(f'Simulation completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)')

    return res


# ============================================================
# Extract results using PowerGAMA built-in methods
# ============================================================
def extract_results(data, res, scenario_name, sql_file):
    """Extract prices, generation, filling, and energy balance."""
    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    num_hours = len(data.timerange)

    # --- Zone prices via getAverageAreaPrices() ---
    try:
        area_prices = res.getAverageAreaPrices()
        print(f'\n{"="*70}')
        print(f'{scenario_name} -- ZONE PRICES [EUR/MWh] (30-year average)')
        print(f'{"="*70}')
        for zone in no_zones:
            if zone in area_prices.index:
                print(f'  {zone}: {area_prices[zone]:.2f}')
    except Exception as e:
        print(f'getAverageAreaPrices() failed: {e}')
        area_prices = None

    # Fallback: compute from SQL
    conn = sqlite3.connect(sql_file)
    nodes_db = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices_db = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    generators_db = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_output_db = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()

    prices_db = prices_db.merge(nodes_db, on='indx')
    prices_db['zone'] = prices_db['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    zone_prices = {}
    print(f'\n{"="*70}')
    print(f'{scenario_name} -- ZONE PRICES [EUR/MWh] (30-year average, from SQL)')
    print(f'{"="*70}')
    print(f'{"Zone":<8} {"Price":>10}')
    print('-' * 20)
    for zone in no_zones:
        zp = prices_db[prices_db['zone'] == zone]
        avg = zp.groupby('timestep')['nodalprice'].mean().mean()
        zone_prices[zone] = avg
        print(f'{zone:<8} {avg:>10.2f}')
    avg_all = np.mean(list(zone_prices.values()))
    print('-' * 20)
    print(f'{"Avg":<8} {avg_all:>10.2f}')

    # --- Generation mix ---
    gen_output_db = gen_output_db.merge(generators_db, on='indx', suffixes=('', '_g'))
    gen_output_db['zone'] = gen_output_db['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
    gen_output_db['country'] = gen_output_db['node'].str.extract(r'(NO|SE|FI|DK)')

    no_gen = gen_output_db[gen_output_db['country'] == 'NO']
    gen_by_type = no_gen.groupby('type')['output'].sum() / 1e6  # TWh
    num_years = num_hours / (365.2425 * 24)

    print(f'\n{"="*70}')
    print(f'{scenario_name} -- NORWAY GENERATION MIX (30-year total / annual avg)')
    print(f'{"="*70}')
    print(f'{"Type":<15} {"Total TWh":>12} {"Avg TWh/yr":>12}')
    print('-' * 42)
    for gtype in sorted(gen_by_type.index):
        total = gen_by_type[gtype]
        annual = total / num_years
        print(f'{gtype:<15} {total:>12.2f} {annual:>12.2f}')
    total_gen = gen_by_type.sum()
    print('-' * 42)
    print(f'{"TOTAL":<15} {total_gen:>12.2f} {total_gen/num_years:>12.2f}')

    # --- Capacity factors ---
    print(f'\n{"="*70}')
    print(f'{scenario_name} -- CAPACITY FACTORS')
    print(f'{"="*70}')

    # Hydro CF = production / (42.6 GW x hours)
    hydro_prod_mwh = no_gen[no_gen['type'].isin(['hydro', 'ror'])]['output'].sum()
    hydro_cap_mw = 42600  # target installed
    hydro_cf = hydro_prod_mwh / (hydro_cap_mw * num_hours)
    print(f'  Hydro+RoR CF: {hydro_cf:.4f} ({hydro_cf*100:.1f}%)')

    # Nuclear CF
    smr_total_mw = sum(SMR_SCENARIOS[scenario_name].values())
    if smr_total_mw > 0:
        nuc_prod_mwh = no_gen[no_gen['type'] == 'nuclear']['output'].sum()
        nuc_cf = nuc_prod_mwh / (smr_total_mw * num_hours)
        nuc_prod_twh = nuc_prod_mwh / 1e6
        print(f'  Nuclear CF:   {nuc_cf:.4f} ({nuc_cf*100:.1f}%)')
        print(f'  Nuclear prod: {nuc_prod_twh:.2f} TWh total, {nuc_prod_twh/num_years:.2f} TWh/yr')

    # --- Average filling ---
    print(f'\n{"="*70}')
    print(f'{scenario_name} -- AVERAGE RESERVOIR FILLING')
    print(f'{"="*70}')
    try:
        avg_filling = res.getAverageFilling()
        gen_df = data.generator.copy()
        gen_df['zone'] = gen_df['node'].str.extract(r'(NO\d)')
        hydro_mask = (gen_df['type'] == 'hydro') & gen_df['zone'].notna()
        for zone in no_zones:
            zone_gens = gen_df[hydro_mask & (gen_df['zone'] == zone)].index
            if len(zone_gens) > 0:
                zone_fill = avg_filling[zone_gens].mean()
                print(f'  {zone}: {zone_fill:.3f}')
    except Exception as e:
        print(f'  getAverageFilling() failed: {e}')
        conn = sqlite3.connect(sql_file)
        storage_db = pd.read_sql_query("SELECT timestep, indx, storage FROM Res_Storage", conn)
        conn.close()
        hydro_gens = generators_db[generators_db['type'] == 'hydro'].copy()
        hydro_gens['zone'] = hydro_gens['node'].str.extract(r'(NO\d)')
        gen_csv = pd.read_csv(DATA_PATH / 'system' / 'generator.csv')
        gen_csv = gen_csv[gen_csv['pmax'] > 0].reset_index(drop=True)
        for zone in no_zones:
            zone_hydro = hydro_gens[hydro_gens['zone'] == zone]
            zone_storage = storage_db[storage_db['indx'].isin(zone_hydro['indx'])]
            zone_caps = gen_csv.loc[gen_csv['node'].str.startswith(zone) & (gen_csv['type'] == 'hydro'), 'storage_cap']
            if zone_caps.sum() > 0:
                zone_hydro_merged = zone_hydro.merge(
                    gen_csv[['node', 'type', 'storage_cap']].drop_duplicates(),
                    on=['node', 'type'], how='left'
                )
                total_cap = zone_hydro_merged['storage_cap'].sum()
                if total_cap > 0:
                    weighted_fill = 0
                    for _, gh in zone_hydro_merged.iterrows():
                        gs = zone_storage[zone_storage['indx'] == gh['indx']]['storage'].mean()
                        if gh['storage_cap'] > 0:
                            weighted_fill += (gs / gh['storage_cap']) * (gh['storage_cap'] / total_cap)
                    print(f'  {zone}: {weighted_fill:.3f}')

    # --- Energy balance ---
    print(f'\n{"="*70}')
    print(f'{scenario_name} -- NORWAY ENERGY BALANCE (annual avg)')
    print(f'{"="*70}')
    consumers = pd.read_csv(DATA_PATH / 'system' / 'consumer.csv')
    no_cons = consumers[consumers['node'].str.startswith('NO')]
    total_demand_twh = no_cons['demand_avg'].sum() * 8760 / 1e6
    total_gen_annual = total_gen / num_years

    # Separate MD base demand and IC addition
    md_cons = no_cons[no_cons['demand_ref'] != 'load_const']
    ic_cons = no_cons[no_cons['demand_ref'] == 'load_const']
    md_demand_twh = md_cons['demand_avg'].sum() * 8760 / 1e6
    ic_demand_twh = ic_cons['demand_avg'].sum() * 8760 / 1e6

    print(f'  Production:    {total_gen_annual:.2f} TWh/yr')
    print(f'  Total demand:  {total_demand_twh:.2f} TWh/yr')
    print(f'    MD base:     {md_demand_twh:.2f} TWh/yr')
    print(f'    IC addition: {ic_demand_twh:.2f} TWh/yr')
    print(f'  Net export:    {total_gen_annual - total_demand_twh:.2f} TWh/yr')

    return zone_prices, gen_by_type


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    # Allow specifying which scenario(s) to run via command line
    if len(sys.argv) > 1:
        scenarios_to_run = sys.argv[1:]
    else:
        scenarios_to_run = ['BL_IC', 'SMR1_IC', 'SMR3_IC', 'SMR6_IC']

    all_results = {}

    for scenario in scenarios_to_run:
        if scenario not in SMR_SCENARIOS:
            print(f'Unknown scenario: {scenario}')
            continue

        sql_file = RESULTS_DIR / scenario / 'results' / f'powergama_{scenario}.sqlite'

        print('\n' + '#' * 70)
        print(f'# {scenario}')
        print(f'# SMR: {SMR_SCENARIOS[scenario]}')
        print(f'# Total SMR: {sum(SMR_SCENARIOS[scenario].values())} MW')
        print(f'# Demand: 230 TWh (208 MD + 22 IC baseload)')
        print('#' * 70)

        data = load_grid_data(scenario)
        res = run_simulation(data, sql_file)
        zone_prices, gen_mix = extract_results(data, res, scenario, sql_file)
        all_results[scenario] = {'prices': zone_prices, 'gen_mix': gen_mix}

        print(f'\nResults saved to: {sql_file}')

        # For BL_IC: validate hydro production
        if scenario == 'BL_IC':
            hydro_twh = gen_mix.get('hydro', 0) + gen_mix.get('ror', 0)
            num_hours = len(data.timerange)
            num_years = num_hours / (365.2425 * 24)
            annual_hydro = hydro_twh / num_years
            print(f'\n*** BL_IC VALIDATION ***')
            print(f'Annual hydro+RoR: {annual_hydro:.1f} TWh/yr')
            if 130 <= annual_hydro <= 160:
                print('  -> PASS: within expected range (130-160 TWh)')
            else:
                print(f'  -> WARNING: outside expected range (130-160 TWh)')
                print(f'  -> Consider checking before running nuclear scenarios')

    # Summary comparison if multiple scenarios ran
    if len(all_results) > 1:
        print('\n' + '=' * 90)
        print('SUMMARY COMPARISON -- ALL IC SCENARIOS')
        print('=' * 90)
        no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

        header = f'{"Zone":<8}'
        for s in all_results:
            header += f' {s:>12}'
        print(header)
        print('-' * (8 + 13 * len(all_results)))

        for zone in no_zones:
            row = f'{zone:<8}'
            for s in all_results:
                p = all_results[s]['prices'].get(zone, float('nan'))
                row += f' {p:>12.2f}'
            print(row)

        print('-' * (8 + 13 * len(all_results)))
        row = f'{"Avg":<8}'
        for s in all_results:
            avg = np.mean([all_results[s]['prices'].get(z, 0) for z in no_zones])
            row += f' {avg:>12.2f}'
        print(row)
