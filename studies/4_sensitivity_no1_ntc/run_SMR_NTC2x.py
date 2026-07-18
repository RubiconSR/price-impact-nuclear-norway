"""SMR{1,3,6}_MD with doubled NO1<->NO2 transmission capacity.

Combines the NO1<->NO2 corridor doubling of run_BL_MD_NTC2x.py with the
uniform SMR deployment of run_nuclear_MD.py, so we can report the nuclear
price reductions under a reinforced internal grid (Option C robustness check).
Same GLPK solver and same data as the main MD scenarios; the ONLY changes are
(a) NO1<->NO2 doubled and (b) SMR generators added.

Usage: python run_SMR_NTC2x.py SMR1_MD   (or SMR3_MD / SMR6_MD)
Output: studies/4_sensitivity_no1_ntc/results/powergama_<scen>_NTC2x.sqlite
"""
import sys, pathlib, time
import pandas as pd
import powergama

SIM_YEAR_START, SIM_YEAR_END = 1991, 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
DATA_PATH = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data'
RESULTS_DIR = BASE_DIR / 'studies' / '4_sensitivity_no1_ntc' / 'results'
SOLVER = 'appsi_highs'
LOSS_METHOD = 0

NO1_NO2_BRANCHES = [('NO2_1', 'NO1_3'), ('NO2_1', 'NO1_4'),
                    ('NO1_3', 'NO2_3'), ('NO1_4', 'NO2_3'), ('NO1_5', 'NO2_3')]

# identical to run_nuclear_MD.py
SMR_SCENARIOS = {
    'SMR1_MD': {'NO1': 300,  'NO2': 300,  'NO3': 300,  'NO4': 300,  'NO5': 300},
    'SMR3_MD': {'NO1': 900,  'NO2': 900,  'NO3': 900,  'NO4': 900,  'NO5': 900},
    'SMR6_MD': {'NO1': 1800, 'NO2': 1800, 'NO3': 1800, 'NO4': 1800, 'NO5': 1800},
}
SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10
SMR_FUELCOST = 9.37
SMR_NODES = {'NO1': 'NO1_3', 'NO2': 'NO2_1', 'NO3': 'NO3_1', 'NO4': 'NO4_1', 'NO5': 'NO5_1'}


def load_grid_data(scenario_name):
    system_path = DATA_PATH / 'system'
    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )

    # (a) double NO1<->NO2 capacities
    print('\nDoubling NO1<->NO2 branch capacities:')
    for from_node, to_node in NO1_NO2_BRANCHES:
        mask = (data.branch['node_from'] == from_node) & (data.branch['node_to'] == to_node)
        if not mask.any():
            print(f'  WARNING: branch {from_node}->{to_node} not found'); continue
        before = data.branch.loc[mask, 'capacity'].values[0]
        data.branch.loc[mask, 'capacity'] = before * 2.0
        print(f'  {from_node}->{to_node}: {before:.1f} -> {before*2:.1f} MW')

    profiles = pd.read_csv(DATA_PATH / 'timeseries_profiles.csv', index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    data.storagevalue_filling = pd.read_csv(DATA_PATH / 'storage' / 'profiles_storval_filling.csv')
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # (b) add SMR generators (identical to run_nuclear_MD.py)
    smr_caps = SMR_SCENARIOS[scenario_name]
    new_rows = []
    for zone, cap_mw in smr_caps.items():
        if cap_mw <= 0:
            continue
        n_units = int(cap_mw / SMR_UNIT_MW)
        node = SMR_NODES[zone]
        for i in range(n_units):
            new_rows.append({
                'Kolonne1': data.generator['Kolonne1'].max() + 1 + len(new_rows),
                'node': node, 'desc': f'{node} nuclear SMR unit {i+1}', 'type': 'nuclear',
                'pmax': SMR_UNIT_MW, 'pmin': SMR_UNIT_MW * SMR_PMIN_FRAC, 'fuelcost': SMR_FUELCOST,
                'inflow_fac': 1.0, 'inflow_ref': 'const', 'storage_cap': 0.0, 'storage_price': 1.0,
                'storval_filling_ref': 'const', 'storval_time_ref': 'const', 'storage_ini': 0.0,
                'pump_cap': 0.0, 'pump_efficiency': 0.0, 'pump_deadband': 0.0,
            })
        print(f'  SMR {zone} ({node}): {n_units} x {SMR_UNIT_MW} MW = {cap_mw} MW')
    data.generator = pd.concat([data.generator, pd.DataFrame(new_rows)], ignore_index=True)

    print(f'\nGenerators: {len(data.generator)}  Branches: {len(data.branch)}  '
          f'Hours: {len(data.timerange)}')
    return data


def main():
    scen = sys.argv[1]
    assert scen in SMR_SCENARIOS, f'unknown scenario {scen}'
    sql_file = RESULTS_DIR / f'powergama_{scen}_NTC2x.sqlite'
    print('=' * 70)
    print(f'Study 5 Option C: {scen} with doubled NO1<->NO2 corridor')
    print('=' * 70)
    data = load_grid_data(scen)
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    lp = powergama.LpProblem(grid=data, lossmethod=LOSS_METHOD)
    res = powergama.Results(data, str(sql_file), replace=True)
    print(f'\nSolving with {SOLVER} -> {sql_file}')
    t0 = time.time()
    lp.solve(res, solver=SOLVER)
    print(f'DONE {scen}_NTC2x in {(time.time()-t0)/3600:.2f} h')


if __name__ == '__main__':
    main()
