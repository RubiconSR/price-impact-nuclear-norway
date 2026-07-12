"""BL_MD with doubled NO1↔NO2 transmission capacity.

Identical setup to run_nuclear_MD.py BL_MD case, with one modification:
the 5 AC branches connecting NO1 to NO2 have their capacity doubled
(total 2390 → 4780 MW). All other data is unchanged.

Output: studies/5_sensitivity_no1_ntc/results/powergama_BL_MD_NTC2x.sqlite
"""

import sys
import pathlib
import time
import pandas as pd
import numpy as np
import powergama

SCENARIO_NAME = 'BL_MD_NTC2x'

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
DATA_PATH = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data'
RESULTS_DIR = BASE_DIR / 'studies' / '5_sensitivity_no1_ntc' / 'results'
SQL_FILE = RESULTS_DIR / f'powergama_{SCENARIO_NAME}.sqlite'

SOLVER = 'glpk'
LOSS_METHOD = 0

# NO1↔NO2 branches identified in diagnose_no1.py (Grid_Branches indx)
# Doubled here at load-time on the branch DataFrame
NO1_NO2_BRANCHES = [
    ('NO2_1', 'NO1_3'),
    ('NO2_1', 'NO1_4'),
    ('NO1_3', 'NO2_3'),
    ('NO1_4', 'NO2_3'),
    ('NO1_5', 'NO2_3'),
]


def load_grid_data():
    """Load MD baseline data + double NO1↔NO2 capacities."""
    system_path = DATA_PATH / 'system'

    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )

    # === SENSITIVITY MODIFICATION: double NO1↔NO2 capacities ===
    print('\nModifying NO1↔NO2 branch capacities (2× sensitivity):')
    print(f'{"From":<8} {"To":<8} {"Before [MW]":>12} {"After [MW]":>12}')
    print('-' * 42)
    cap_col = 'capacity'
    for from_node, to_node in NO1_NO2_BRANCHES:
        mask = (data.branch['node_from'] == from_node) & (data.branch['node_to'] == to_node)
        if not mask.any():
            print(f'WARNING: branch {from_node}→{to_node} not found')
            continue
        before = data.branch.loc[mask, cap_col].values[0]
        data.branch.loc[mask, cap_col] = before * 2.0
        after = data.branch.loc[mask, cap_col].values[0]
        print(f'{from_node:<8} {to_node:<8} {before:>12.2f} {after:>12.2f}')
    print('-' * 42)

    # Timeseries profiles
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

    # Filter zero-capacity generators
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    num_hours = len(data.timerange)
    num_years = num_hours / (365.2425 * 24)
    print(f'\nNodes: {len(data.node)}')
    print(f'Generators: {len(data.generator)}  (BL_MD — no SMR added)')
    print(f'Branches: {len(data.branch)}')
    print(f'Simulation: {num_hours} hours ({num_years:.1f} years)')

    return data


def run_simulation(data):
    SQL_FILE.parent.mkdir(parents=True, exist_ok=True)

    lp = powergama.LpProblem(grid=data, lossmethod=LOSS_METHOD)
    res = powergama.Results(data, str(SQL_FILE), replace=True)

    print(f'\nStarting simulation with {SOLVER} solver...')
    print(f'Output: {SQL_FILE}')
    start = time.time()
    lp.solve(res, solver=SOLVER)
    elapsed = time.time() - start
    print(f'\nSimulation completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes, {elapsed/3600:.2f} hours)')


def main():
    print('=' * 70)
    print(f'Study 5 — NO1 NTC sensitivity: {SCENARIO_NAME}')
    print('=' * 70)
    print('Setup identical to BL_MD except: NO1↔NO2 corridor doubled (2390 → 4780 MW)')

    data = load_grid_data()
    run_simulation(data)

    print('\nDone. Run extraction:')
    print(f'  python studies/5_sensitivity_no1_ntc/compare_no1.py')


if __name__ == '__main__':
    main()
