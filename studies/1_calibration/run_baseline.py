"""
Baseline simulation (B-case) for master thesis:
"The Price Impact of Nuclear Energy on the Norwegian Electricity Market"

Replicates the baseline case from Hjelmeland et al. using PowerGAMA.
Simulates the Nordic power system over 30 weather years (1991-2020).
"""

import pathlib
import time
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
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_baseline_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'

SOLVER = 'glpk'  # GNU Linear Programming Kit
LOSS_METHOD = 0  # 0=no losses

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

    # Load 30-year hourly profiles (wind, solar, hydro inflow, load)
    profiles = pd.read_csv(
        DATA_PATH / 'timeseries_profiles.csv',
        index_col=0,
        parse_dates=True,
    )
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]

    # Load hydro storage filling reference values
    storval = pd.read_csv(DATA_PATH / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval

    # Set simulation timerange (hourly steps)
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0

    # Remove zero-capacity generators
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
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('BASELINE CASE - Nordic Power System')
    print('=' * 60)

    data = load_grid_data()
    res = run_simulation(data)

    print('\nBaseline simulation complete.')
    print(f'Results saved to: {SQL_FILE}')
