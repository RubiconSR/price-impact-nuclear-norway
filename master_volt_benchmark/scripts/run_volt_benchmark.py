"""
run_volt_benchmark.py
=====================
Volt-benchmark: 4 × 3 scenariematrise (kjernekraft × havvind) i 2040-systemet.

Følger samme mønster som ../run_nuclear_MD.py:
  - load_grid_data(scenario_name): laster eksisterende nuclear_MD-system,
    skalerer forbruk til Volts 2040-fordeling, fjerner eksisterende OW,
    legger til OW + SMR per scenario.
  - run_simulation(data, sql_file): kaller powergama.LpProblem + .solve.
  - extract_results(): bruker PowerGAMA sine getAverageAreaPrices() m.fl.

Scenariematrise (12 celler):
  Rader (SMR):     N0 (0 GW), N1 (1.5 GW), N3 (4.5 GW), N6 (9 GW)
  Kolonner (OW):   OW0 (0 GW), OW1 (2 GW), OW2 (4 GW)

Volt forbruk 2040: NO1=44, NO2=56, NO3=40, NO4=30, NO5=25 TWh.
All OW på NO2 (Volts plassering). SMR jevnt fordelt NO1-NO5 (paper-konsistent).
"""

import sys
import pathlib
import time
import sqlite3
import numpy as np
import pandas as pd
import powergama

# ============================================================
# Paths
# ============================================================
BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SOURCE_DATA = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data'   # gjenbruk eksisterende
RESULTS_DIR = BASE_DIR / 'master_volt_benchmark' / 'results'

# ============================================================
# Simulation config
# ============================================================
SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')
SOLVER = 'glpk'
LOSS_METHOD = 0

# ============================================================
# Volt 2040: forbruk per sone (TWh)
# ============================================================
VOLT_DEMAND_TWH = {
    'NO1': 44.0, 'NO2': 56.0, 'NO3': 40.0, 'NO4': 30.0, 'NO5': 25.0,
}

# ============================================================
# OW-scenarier (Volts S0/S1/S2). Alt på NO2.
# Følger Volts 0/1/2-metode.
# ============================================================
OW_SCENARIOS = {
    'OW0': 0,       # Volt S0: 0 GW
    'OW1': 2000,    # Volt S1: 1.5 GW SNII + 0.5 GW UN = 2 GW
    'OW2': 4000,    # Volt S2: S1 + 2 GW = 4 GW
}
# OW-tilkobling: NO2_2 (kystpunkt i Stavanger-området, ingen DC-kabel)
# NO2_1 har direkte GB-kabel (1400 MW) → eksporterer mye av OW-strømmen
# NO2_4 har DE+NL-kabler, NO2_5 har Skagerrak. NO2_2 er eneste kystnode
# uten DC-kabel — gir bedre intern norsk fordeling av OW-effekten.
OW_NODE = 'NO2_2'
OW_PROFILE = 'windoff_Sønnavind A'
OW_INFLOW_FAC = 0.8  # samme som setup_nuclear_MD.py

# ============================================================
# SMR-scenarier (Volts 0/1/2-metode, ALT på NO2 — samme plassering
# som Volts havvind-scenarier slik at sammenligningen blir ren)
# N1 = 2.1 GW (7 × 300 MW på NO2_1) — matcher OW1 (2 GW OW på NO2)
# N2 = 3.9 GW (13 × 300 MW på NO2_1) — matcher OW2 (4 GW OW på NO2)
# ============================================================
SMR_SCENARIOS = {
    'N0': {'NO2': 0},
    'N1': {'NO2': 2100},  # 2.1 GW på NO2
    'N2': {'NO2': 3900},  # 3.9 GW på NO2
}
SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10
SMR_FUELCOST = 9.37
# SMR-plassering: NO2_2 (samme node som OW for direkte sammenligning)
SMR_NODES = {'NO1': 'NO1_3', 'NO2': 'NO2_2', 'NO3': 'NO3_1', 'NO4': 'NO4_1', 'NO5': 'NO5_1'}

# Full 4 × 3 matrise
MATRIX = [(s, o) for s in SMR_SCENARIOS for o in OW_SCENARIOS]


# ============================================================
# Load + modify grid data
# ============================================================
def load_grid_data(smr_key, ow_key):
    """Last 2050-MD baseline, skaler forbruk til Volt 2040, legg til OW + SMR."""
    sysp = SOURCE_DATA / 'system'

    data = powergama.GridData()
    data.readGridData(
        nodes=sysp / 'node.csv',
        ac_branches=sysp / 'branch.csv',
        dc_branches=sysp / 'dcbranch.csv',
        generators=sysp / 'generator.csv',
        consumers=sysp / 'consumer.csv',
    )

    profiles = pd.read_csv(SOURCE_DATA / 'timeseries_profiles.csv',
                           index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]

    storval = pd.read_csv(SOURCE_DATA / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval

    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0

    # Filter zero-cap (samme som run_nuclear_MD.py)
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # --- 1. Skaler norsk forbruk til Volt 2040 ---
    data.consumer['zone'] = data.consumer['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')[0]
    print('\n=== Forbruksskalering: 2050-MD → Volt 2040 ===')
    for zone, target_twh in VOLT_DEMAND_TWH.items():
        mask = data.consumer['zone'] == zone
        cur_mw = data.consumer.loc[mask, 'demand_avg'].sum()
        cur_twh = cur_mw * 8760 / 1e6
        target_mw_total = target_twh * 1e6 / 8760
        sf = target_mw_total / cur_mw if cur_mw > 0 else 0
        data.consumer.loc[mask, 'demand_avg'] *= sf
        print(f'  {zone}: {cur_twh:5.1f} → {target_twh:4.1f} TWh  (sf={sf:.4f})')
    data.consumer = data.consumer.drop(columns=['zone'])

    # --- 2. Fjern eksisterende offshore vind (V0-baseline) ---
    no_off_mask = (data.generator['type'] == 'wind_off') & \
                  data.generator['node'].str.startswith('NO')
    n_removed = no_off_mask.sum()
    cap_removed = data.generator.loc[no_off_mask, 'pmax'].sum()
    data.generator = data.generator[~no_off_mask].reset_index(drop=True)
    print(f'\nFjernet eksisterende OW: {n_removed} gen., {cap_removed:.0f} MW')

    # --- 3. Legg til OW per scenario (alt på NO2) ---
    ow_cap = OW_SCENARIOS[ow_key]
    if ow_cap > 0:
        next_id = data.generator['Kolonne1'].max() + 1
        ow_row = {
            'Kolonne1': next_id,
            'node': OW_NODE,
            'desc': f'{OW_NODE} wind_off Volt {ow_key}',
            'type': 'wind_off',
            'pmax': float(ow_cap),
            'pmin': 0.0,
            'fuelcost': 0.015,
            'inflow_fac': OW_INFLOW_FAC,
            'inflow_ref': OW_PROFILE,
            'storage_cap': 0.0,
            'storage_price': 1.0,
            'storval_filling_ref': 'const',
            'storval_time_ref': 'const',
            'storage_ini': 0.6,
            'pump_cap': 0.0,
            'pump_efficiency': 0.0,
            'pump_deadband': 0.0,
        }
        data.generator = pd.concat(
            [data.generator, pd.DataFrame([ow_row])], ignore_index=True
        )
        print(f'Lagt til OW: {ow_cap} MW @ {OW_NODE} ({OW_PROFILE})')
    else:
        print('OW: 0 MW (V0-baseline)')

    # --- 4. Legg til SMR per scenario (samme mønster som run_nuclear_MD.py) ---
    smr_caps = SMR_SCENARIOS[smr_key]
    total_smr = sum(smr_caps.values())
    if total_smr > 0:
        new_rows = []
        for zone, cap_mw in smr_caps.items():
            if cap_mw <= 0:
                continue
            n_units = int(cap_mw / SMR_UNIT_MW)
            node = SMR_NODES[zone]
            for i in range(n_units):
                new_rows.append({
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
                })
        data.generator = pd.concat(
            [data.generator, pd.DataFrame(new_rows)], ignore_index=True
        )
        print(f'Lagt til SMR: {total_smr} MW totalt ({len(new_rows)} enheter)')
    else:
        print('SMR: 0 MW')

    print(f'\nNoder: {len(data.node)}, generatorer: {len(data.generator)}, '
          f'AC-grener: {len(data.branch)}, DC-grener: {len(data.dcbranch)}')
    print(f'Simulering: {len(data.timerange)} timer '
          f'({len(data.timerange)/8766:.1f} år)')
    return data


# ============================================================
# Run + extract (uendret mønster fra run_nuclear_MD.py)
# ============================================================
def run_simulation(data, sql_file, name):
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    lp = powergama.LpProblem(grid=data, lossmethod=LOSS_METHOD)
    res = powergama.Results(data, sql_file, replace=True)
    # Unik solver-logfil per scenario så parallelle kjøringer ikke kolliderer
    solve_args = {
        'tee': False,
        'keepfiles': False,
        'symbolic_solver_labels': True,
        'logfile': str(sql_file.parent / f'lpsolver_log_{name}.txt'),
    }
    print(f'\nStarter simulering med {SOLVER}...')
    start = time.time()
    lp.solve(res, solver=SOLVER, solve_args=solve_args)
    elapsed = time.time() - start
    print(f'Ferdig på {elapsed/60:.1f} min')
    return res


def extract_results(data, res, name, sql_file):
    """Bruk NordicNuclearAnalysis sin getZonePricesVolumeWeightedFromDB
    (Hjelmeland Eq. 5) — samme som paperet. PowerGAMA sin
    getAreaPricesAverage opererer på `area`-kolonnen som er landkode (NO),
    ikke sone (NO1-NO5)."""
    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

    # Importer NordicNuclearAnalysis-funksjonen
    nna_funcs = pathlib.Path(__file__).parent.parent.parent / 'NordicNuclearAnalysis NY'
    sys.path.insert(0, str(nna_funcs))
    from functions.database_functions import getZonePricesVolumeWeightedFromDB
    from powergama.database import Database

    db = Database(str(sql_file))
    timerange = [0, len(data.timerange)]
    zone_prices = getZonePricesVolumeWeightedFromDB(
        data, db, timeMaxMin=timerange, zones=no_zones
    )
    print(f'\n=== {name} — volumvektet sonepris (EUR/MWh, 30-år snitt) ===')
    for z in no_zones:
        print(f'  {z}: {zone_prices[z]:.2f}')
    nat_avg = sum(zone_prices.values()) / len(zone_prices)
    print(f'  NO snitt: {nat_avg:.2f}')
    return zone_prices


# ============================================================
# Main
# ============================================================
def main():
    if len(sys.argv) > 1:
        # Kjør én celle: python run_volt_benchmark.py N0 OW0
        smr_key, ow_key = sys.argv[1], sys.argv[2]
        cells = [(smr_key, ow_key)]
    else:
        cells = MATRIX

    for smr_key, ow_key in cells:
        name = f'{smr_key}_{ow_key}'
        sql_file = RESULTS_DIR / f'{name}.sqlite'
        print(f'\n{"="*70}\nSCENARIO {name}\n{"="*70}')
        data = load_grid_data(smr_key, ow_key)
        res = run_simulation(data, sql_file, name)
        extract_results(data, res, name, sql_file)


if __name__ == '__main__':
    main()
