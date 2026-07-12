"""
Nuclear NTC-border scenario — 30-year simulation (1991-2020) with GLPK solver.

SMR_NTC_border: Nuclear capacity equal to total NTC export capacity from Norway
to foreign countries (9,338 MW), distributed proportionally across zones with
foreign interconnectors, rounded to 300 MW units → 9,300 MW total.

  NO1: 1,800 MW (6 units)  — NTC to SE3: 1,822 MW
  NO2: 5,100 MW (17 units) — NTC to NL/DK/GB/DE: 5,132 MW
  NO3:   900 MW (3 units)  — NTC to SE2: 1,000 MW
  NO4: 1,500 MW (5 units)  — NTC to SE1/SE2/FI: 1,384 MW
  NO5:     0 MW (0 units)  — no foreign NTC

Runs both MD (208 TWh) and IC (230 TWh) demand scenarios.
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

BASE_DIR = pathlib.Path(__file__).parent.parent.parent

SOLVER = 'glpk'
LOSS_METHOD = 0

# SMR unit parameters
SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10  # pmin = 30 MW (dispatchable)
SMR_FUELCOST = 9.37   # EUR/MWh
SMR_AVAIL = 1.0
SMR_RAMP_RATE = 1.0   # No ramp limit

# Node placement: nuclear at actual cable endpoint nodes, proportional to NTC at each node
# NO1: both SE3 cables at NO1_5 (911+911=1822 MW) → 6 units = 1800 MW
# NO2: NSL at NO2_1 (1400), NorNed+NordLink at NO2_4 (700+1400=2100), Skagerrak at NO2_5 (1632)
# NO3: SE2_4 cable at NO3_1 (1000 MW) → 3 units = 900 MW
# NO4: SE1_1+FI_1 at NO4_1 (900+84=984), SE2_1 at NO4_3 (400)
NTC_NODE_MW = [
    # (node, capacity_mw)  — rounded to 300 MW units
    ('NO1_5', 1800),   # 6 units — SE3 cables (1822 MW NTC)
    ('NO2_1', 1500),   # 5 units — North Sea Link (1400 MW NTC)
    ('NO2_4', 2100),   # 7 units — NorNed + NordLink (2100 MW NTC)
    ('NO2_5', 1500),   # 5 units — Skagerrak (1632 MW NTC)
    ('NO3_1',  900),   # 3 units — SE2_4 cable (1000 MW NTC)
    ('NO4_1', 1200),   # 4 units — SE1_1 + FI_1 (984 MW NTC)
    ('NO4_3',  300),   # 1 unit  — SE2_1 (400 MW NTC)
]
NTC_TOTAL = sum(mw for _, mw in NTC_NODE_MW)  # 9300 MW

# Scenario definitions: {scenario_name: (demand_label, scenario_dir, demand_twh)}
SCENARIOS = {
    'SMR_NTC_MD': ('MD', 'nuclear_MD', 208),
    'SMR_NTC_IC': ('IC', 'nuclear_IC', 230),
}

# Foreign interconnectors for saturation analysis
# (name, type, no_node, foreign_node, capacity_mw, no_zone)
FOREIGN_INTERCONNECTORS = [
    ('NO1-SE3_5', 'AC', 'NO1_5', 'SE3_5', 911, 'NO1'),
    ('NO1-SE3_7', 'AC', 'NO1_5', 'SE3_7', 911, 'NO1'),
    ('NorNed', 'DC', 'NO2_4', 'NL', 700, 'NO2'),
    ('Skagerrak', 'DC', 'NO2_5', 'DK1_1', 1632, 'NO2'),
    ('North Sea Link', 'DC', 'NO2_1', 'GB', 1400, 'NO2'),
    ('NordLink', 'DC', 'NO2_4', 'DE', 1400, 'NO2'),
    ('NO3-SE2_4', 'AC', 'NO3_1', 'SE2_4', 1000, 'NO3'),
    ('NO4-SE1_1', 'AC', 'NO4_1', 'SE1_1', 900, 'NO4'),
    ('NO4-SE2_1', 'AC', 'NO4_3', 'SE2_1', 400, 'NO4'),
    ('NO4-FI_1', 'AC', 'NO4_1', 'FI_1', 84, 'NO4'),
]


# ============================================================
# Load grid data
# ============================================================
def load_grid_data(scenario_name):
    """Load grid data and add NTC-proportional SMR generators."""
    demand_label, sc_dir, demand_twh = SCENARIOS[scenario_name]
    scenario_dir = BASE_DIR / 'scenarios' / sc_dir
    data_path = scenario_dir / 'data'
    system_path = data_path / 'system'

    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )

    # Timeseries profiles
    ts_path = data_path / 'timeseries_profiles.csv'
    if not ts_path.exists() and not ts_path.is_symlink():
        ts_path = BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'timeseries_profiles.csv'
    profiles = pd.read_csv(ts_path, index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]

    storval = pd.read_csv(data_path / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval

    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0

    # Filter out zero-capacity generators
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # Add SMR generators at cable endpoint nodes
    print(f'\nAdding NTC-proportional SMR capacity: {NTC_TOTAL} MW total')
    print(f'  Placed at cable endpoint nodes:')
    new_rows = []
    for node, cap_mw in NTC_NODE_MW:
        n_units = int(cap_mw / SMR_UNIT_MW)
        zone = node[:3]
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
                'ramp_rate': SMR_RAMP_RATE,
            }
            new_rows.append(row)
        print(f'  {node} ({zone}): {n_units} x {SMR_UNIT_MW} MW = {cap_mw} MW')

    new_df = pd.DataFrame(new_rows)
    data.generator = pd.concat([data.generator, new_df], ignore_index=True)

    # Ensure ramp_rate column exists (default 1.0 = no limit for non-nuclear)
    if 'ramp_rate' not in data.generator.columns:
        data.generator['ramp_rate'] = 1.0
    data.generator['ramp_rate'] = data.generator['ramp_rate'].fillna(1.0)

    # Verify demand
    no_cons = data.consumer[data.consumer['node'].str.startswith('NO')]
    total_no_demand_twh = no_cons['demand_avg'].sum() * 8760 / 1e6
    print(f'\nNorwegian demand: {total_no_demand_twh:.1f} TWh/yr (target: {demand_twh} TWh)')

    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)
    print(f'Nodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}')
    print(f'Simulation: {num_hours} hours ({num_years:.1f} years)')

    return data, data_path


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
# Extract results
# ============================================================
def extract_results(data, res, scenario_name, sql_file, data_path):
    """Extract prices, generation, CF, net export, and cable saturation."""
    demand_label, sc_dir, demand_twh = SCENARIOS[scenario_name]
    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)

    conn = sqlite3.connect(sql_file)
    nodes_db = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices_db = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    generators_db = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_output_db = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)

    # ---- Volume-weighted zone prices ----
    node_ids = nodes_db['id'].tolist()
    consumers = pd.read_csv(data_path / 'system' / 'consumer.csv')
    profiles = pd.read_csv(
        data_path / 'timeseries_profiles.csv' if (data_path / 'timeseries_profiles.csv').exists()
        else BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'timeseries_profiles.csv',
        index_col=0, parse_dates=True
    ).reset_index()
    profiles['const'] = 1
    T = min(len(profiles), num_hours)

    no_node_map = {}
    for i, nid in enumerate(node_ids):
        zone = nid[:3] if nid[:2] == 'NO' else None
        if zone in no_zones:
            no_node_map[i] = zone

    node_demand = {}
    for ni, zone in no_node_map.items():
        nid = node_ids[ni]
        cons = consumers[consumers['node'] == nid]
        if cons.empty:
            continue
        d = np.zeros(T)
        for _, c in cons.iterrows():
            prof = c['demand_ref']
            if prof in profiles.columns:
                d += c['demand_avg'] * profiles[prof].values[:T]
            else:
                d += c['demand_avg']
        node_demand[ni] = d

    no_indices = sorted(no_node_map.keys())
    placeholders = ','.join('?' * len(no_indices))
    rows = conn.execute(
        f"SELECT timestep, indx, nodalprice FROM Res_Nodes "
        f"WHERE indx IN ({placeholders}) ORDER BY timestep, indx",
        no_indices).fetchall()

    node_prices = {ni: np.zeros(T) for ni in no_indices}
    for ts, indx, price in rows:
        if indx in node_prices and ts < T:
            node_prices[indx][ts] = price

    zone_prices = {}
    for zone in no_zones:
        sum_pd, sum_d = 0.0, 0.0
        for ni, z in no_node_map.items():
            if z != zone or ni not in node_demand or ni not in node_prices:
                continue
            sum_pd += np.sum(node_prices[ni] * node_demand[ni])
            sum_d += np.sum(node_demand[ni])
        zone_prices[zone] = sum_pd / sum_d if sum_d > 0 else 0.0

    national_avg = np.mean(list(zone_prices.values()))

    print(f'\n{"="*70}')
    print(f'{scenario_name} — VOLUME-WEIGHTED ZONE PRICES [EUR/MWh]')
    print(f'{"="*70}')
    for z in no_zones:
        print(f'  {z}: {zone_prices[z]:.2f}')
    print(f'  National avg: {national_avg:.2f}')

    # ---- Generation mix ----
    gen_output_db = gen_output_db.merge(generators_db, on='indx', suffixes=('', '_g'))
    gen_output_db['country'] = gen_output_db['node'].str.extract(r'(NO|SE|FI|DK)')
    no_gen = gen_output_db[gen_output_db['country'] == 'NO']
    gen_by_type = no_gen.groupby('type')['output'].sum() / 1e6  # TWh total

    print(f'\n{"="*70}')
    print(f'{scenario_name} — NORWAY GENERATION MIX [TWh/yr]')
    print(f'{"="*70}')
    for gtype in sorted(gen_by_type.index):
        annual = gen_by_type[gtype] / num_years
        print(f'  {gtype:<15} {annual:>8.2f}')
    total_gen_annual = gen_by_type.sum() / num_years
    print(f'  {"TOTAL":<15} {total_gen_annual:>8.2f}')

    # ---- Nuclear capacity factor ----
    nuc_prod_mwh = no_gen[no_gen['type'] == 'nuclear']['output'].sum()
    nuc_cf = nuc_prod_mwh / (NTC_TOTAL * num_hours)
    nuc_prod_annual = nuc_prod_mwh / 1e6 / num_years

    print(f'\n{"="*70}')
    print(f'{scenario_name} — NUCLEAR METRICS')
    print(f'{"="*70}')
    print(f'  Installed: {NTC_TOTAL} MW')
    print(f'  CF: {nuc_cf:.4f} ({nuc_cf*100:.1f}%)')
    print(f'  Annual production: {nuc_prod_annual:.2f} TWh/yr')

    # ---- Net export ----
    no_cons_csv = consumers[consumers['node'].str.startswith('NO')]
    total_demand_twh = no_cons_csv['demand_avg'].sum() * 8760 / 1e6
    net_export = total_gen_annual - total_demand_twh

    print(f'\n{"="*70}')
    print(f'{scenario_name} — ENERGY BALANCE [TWh/yr]')
    print(f'{"="*70}')
    print(f'  Production: {total_gen_annual:.2f}')
    print(f'  Demand:     {total_demand_twh:.2f}')
    print(f'  Net export: {net_export:+.2f}')

    # ---- Cable saturation analysis ----
    # Uses CSV row indices (not SQL Grid tables) + Res_DcBranches / Res_Branches
    # DC indices from dcbranch.csv, AC indices from branch.csv
    CABLE_MAP = [
        # (name, type, csv_indx, node_from_csv, node_to_csv, capacity, no_zone)
        ('NorNed',          'DC',  3, 'NL',    'NO2_4', 700,  'NO2'),
        ('Skagerrak',       'DC',  8, 'DK1_1', 'NO2_5', 1632, 'NO2'),
        ('North Sea Link',  'DC', 10, 'NO2_1', 'GB',    1400, 'NO2'),
        ('NordLink',        'DC', 11, 'NO2_4', 'DE',    1400, 'NO2'),
        ('NO1-SE3_5',       'AC', 54, 'NO1_5', 'SE3_5', 911,  'NO1'),
        ('NO1-SE3_7',       'AC', 55, 'NO1_5', 'SE3_7', 911,  'NO1'),
        ('NO3-SE2_4',       'AC', 49, 'NO3_1', 'SE2_4', 1000, 'NO3'),
        ('NO4-SE1_1',       'AC', 59, 'NO4_1', 'SE1_1', 900,  'NO4'),
        ('NO4-SE2_1',       'AC', 61, 'NO4_3', 'SE2_1', 400,  'NO4'),
        ('NO4-FI_1',        'AC', 95, 'NO4_1', 'FI_1',  84,   'NO4'),
    ]

    print(f'\n{"="*70}')
    print(f'{scenario_name} — CABLE SATURATION (>95% NTC in export direction)')
    print(f'{"="*70}')

    dc_flows = pd.read_sql_query("SELECT timestep, indx, flow FROM Res_DcBranches", conn)
    ac_flows = pd.read_sql_query("SELECT timestep, indx, flow FROM Res_Branches", conn)

    saturation_results = {}
    print(f'  {"Interconnector":<20} {"NTC":>6} {"Sat%":>6} {"AvgFlow":>8} {"MaxFlow":>8}')
    print(f'  {"-"*50}')

    for name, btype, csv_indx, node_from, node_to, capacity, no_zone in CABLE_MAP:
        if btype == 'DC':
            flows_series = dc_flows[dc_flows['indx'] == csv_indx]['flow'].values
            # Positive flow = node_from -> node_to (CSV order)
            # Export from NO = positive if node_from starts with NO, else negative
            if node_from.startswith('NO'):
                export_flows = flows_series
            else:
                export_flows = -flows_series
        else:
            flows_series = ac_flows[ac_flows['indx'] == csv_indx]['flow'].values
            # All AC foreign links: NO node is node_from, positive = export
            export_flows = flows_series

        threshold = 0.95 * capacity
        n_saturated = np.sum(export_flows > threshold)
        sat_pct = n_saturated / len(export_flows) * 100 if len(export_flows) > 0 else 0
        avg_flow = np.mean(export_flows) if len(export_flows) > 0 else 0
        max_flow = np.max(export_flows) if len(export_flows) > 0 else 0

        saturation_results[name] = {
            'capacity': capacity,
            'saturation_pct': sat_pct,
            'avg_export_flow': avg_flow,
            'max_export_flow': max_flow,
            'zone': no_zone,
        }
        print(f'  {name:<20} {capacity:>6} {sat_pct:>5.1f}% {avg_flow:>8.1f} {max_flow:>8.1f}')

    conn.close()

    return {
        'zone_prices': zone_prices,
        'national_avg': national_avg,
        'gen_by_type': gen_by_type / num_years,  # TWh/yr
        'nuc_cf': nuc_cf,
        'nuc_prod_annual': nuc_prod_annual,
        'net_export': net_export,
        'saturation': saturation_results,
        'total_gen_annual': total_gen_annual,
        'total_demand_twh': total_demand_twh,
    }


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) > 1:
        scenarios_to_run = sys.argv[1:]
    else:
        scenarios_to_run = ['SMR_NTC_MD', 'SMR_NTC_IC']

    all_results = {}

    for scenario in scenarios_to_run:
        if scenario not in SCENARIOS:
            print(f'Unknown scenario: {scenario}')
            continue

        demand_label, sc_dir, demand_twh = SCENARIOS[scenario]
        scenario_dir = BASE_DIR / 'scenarios' / sc_dir
        sql_file = scenario_dir / scenario / 'results' / f'powergama_{scenario}.sqlite'

        print('\n' + '#' * 70)
        print(f'# {scenario}')
        print(f'# SMR (NTC at cable nodes): {NTC_NODE_MW}')
        print(f'# Total SMR: {NTC_TOTAL} MW')
        print(f'# Demand: {demand_twh} TWh')
        print('#' * 70)

        data, data_path = load_grid_data(scenario)
        res = run_simulation(data, sql_file)
        results = extract_results(data, res, scenario, sql_file, data_path)
        all_results[scenario] = results

        print(f'\nResults saved to: {sql_file}')

    # Summary
    if len(all_results) > 1:
        print('\n' + '=' * 90)
        print('SUMMARY — SMR_NTC_border SCENARIOS')
        print('=' * 90)
        no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

        print(f'\n{"Metric":<30} {"SMR_NTC_MD":>15} {"SMR_NTC_IC":>15}')
        print('-' * 62)
        for z in no_zones:
            md = all_results.get('SMR_NTC_MD', {}).get('zone_prices', {}).get(z, 0)
            ic = all_results.get('SMR_NTC_IC', {}).get('zone_prices', {}).get(z, 0)
            print(f'{z + " price [EUR/MWh]":<30} {md:>15.2f} {ic:>15.2f}')

        for key, label in [('national_avg', 'National avg [EUR/MWh]'),
                           ('nuc_cf', 'Nuclear CF'),
                           ('nuc_prod_annual', 'Nuclear prod [TWh/yr]'),
                           ('net_export', 'Net export [TWh/yr]')]:
            md = all_results.get('SMR_NTC_MD', {}).get(key, 0)
            ic = all_results.get('SMR_NTC_IC', {}).get(key, 0)
            if key == 'nuc_cf':
                print(f'{label:<30} {md*100:>14.1f}% {ic*100:>14.1f}%')
            else:
                print(f'{label:<30} {md:>15.2f} {ic:>15.2f}')
