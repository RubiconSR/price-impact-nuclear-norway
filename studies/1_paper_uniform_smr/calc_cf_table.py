"""
Compute capacity factors for all generation types, all scenarios.
Uses PowerGAMA Results.getEnergyMix() for both energy and capacity.
"""

import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import powergama

BASE_DIR = pathlib.Path(__file__).parent.parent.parent

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10
SMR_FUELCOST = 9.37
SMR_NODES = {'NO1': 'NO1_3', 'NO2': 'NO2_1', 'NO3': 'NO3_1', 'NO4': 'NO4_1', 'NO5': 'NO5_1'}
SMR_CAPS = {
    'BL':   {'NO1': 0,    'NO2': 0,    'NO3': 0,    'NO4': 0,    'NO5': 0},
    'SMR1': {'NO1': 300,  'NO2': 300,  'NO3': 300,  'NO4': 300,  'NO5': 300},
    'SMR3': {'NO1': 900,  'NO2': 900,  'NO3': 900,  'NO4': 900,  'NO5': 900},
    'SMR6': {'NO1': 1800, 'NO2': 1800, 'NO3': 1800, 'NO4': 1800, 'NO5': 1800},
}

GEN_ORDER = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear', 'fossil_gas', 'biomass']
GEN_LABELS = {
    'hydro': 'Hydro (reg.)', 'ror': 'Run-of-river', 'wind_on': 'Wind onshore',
    'wind_off': 'Wind offshore', 'solar': 'Solar', 'nuclear': 'Nuclear (SMR)',
    'fossil_gas': 'Gas', 'biomass': 'Biomass',
}


def load_scenario(demand_label, smr_label):
    scenario_name = f'{smr_label}_{demand_label}'
    scenario_dir = BASE_DIR / 'scenarios' / f'nuclear_{demand_label}'
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
    profiles = pd.read_csv(data_path / 'timeseries_profiles.csv',
                           index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    data.storagevalue_filling = pd.read_csv(
        data_path / 'storage' / 'profiles_storval_filling.csv')
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    smr_caps = SMR_CAPS[smr_label]
    total_smr = sum(smr_caps.values())
    if total_smr > 0:
        new_rows = []
        for zone, cap_mw in smr_caps.items():
            if cap_mw <= 0:
                continue
            n_units = int(cap_mw / SMR_UNIT_MW)
            node = SMR_NODES[zone]
            for i in range(n_units):
                row = {
                    'Kolonne1': data.generator['Kolonne1'].max() + 1 + len(new_rows),
                    'node': node, 'desc': f'{node} nuclear SMR {i+1}',
                    'type': 'nuclear', 'pmax': SMR_UNIT_MW,
                    'pmin': SMR_UNIT_MW * SMR_PMIN_FRAC,
                    'fuelcost': SMR_FUELCOST, 'inflow_fac': 1.0,
                    'inflow_ref': 'const', 'storage_cap': 0.0,
                    'storage_price': 1.0, 'storval_filling_ref': 'const',
                    'storval_time_ref': 'const', 'storage_ini': 0.0,
                    'pump_cap': 0.0, 'pump_efficiency': 0.0, 'pump_deadband': 0.0,
                }
                new_rows.append(row)
        data.generator = pd.concat(
            [data.generator, pd.DataFrame(new_rows)], ignore_index=True)

    sql_file = scenario_dir / scenario_name / 'results' / f'powergama_{scenario_name}.sqlite'
    if not sql_file.exists():
        sql_file = scenario_dir / 'results' / f'powergama_{scenario_name}.sqlite'

    res = powergama.Results(data, str(sql_file), replace=False)
    return data, res


if __name__ == '__main__':
    smr_labels = ['BL', 'SMR1', 'SMR3', 'SMR6']

    for demand_label in ['MD', 'IC']:
        print('\n' + '=' * 100)
        print(f'CAPACITY FACTORS — {demand_label} SCENARIOS (Norway only)')
        print('=' * 100)

        # Header
        header = f'{"Type":<18}'
        for sl in smr_labels:
            header += f' {"Cap [GW]":>9} {"Gen [TWh]":>10} {"CF [%]":>8} |'
        print(f'\n{"":18}', end='')
        for sl in smr_labels:
            lbl = f'{sl}_{demand_label}'
            print(f' {lbl:>30} |', end='')
        print()
        print(f'{"Type":<18}', end='')
        for sl in smr_labels:
            print(f' {"Cap[GW]":>9} {"Gen[TWh]":>10} {"CF[%]":>8} |', end='')
        print()
        print('-' * (18 + 4 * 32))

        # Load all scenarios
        all_data = {}
        for sl in smr_labels:
            sc_name = f'{sl}_{demand_label}'
            print(f'Loading {sc_name}...', end=' ', flush=True)
            data, res = load_scenario(demand_label, sl)

            # Get energy (MWh total) and capacity (MW) for Norway
            energy_mix = res.getEnergyMix()
            cap_mix = res.getEnergyMix(variable="capacity")

            no_energy = energy_mix.loc['NO'].fillna(0)
            no_cap = cap_mix.loc['NO'].fillna(0)

            num_hours = len(res.grid.timerange)
            num_years = num_hours / (365.2425 * 24)

            # TWh/yr and GW
            gen_twh = no_energy / 1e6 / num_years
            cap_gw = no_cap / 1e3

            all_data[sl] = {'gen_twh': gen_twh, 'cap_gw': cap_gw, 'num_hours': num_hours}
            print('OK')

        # Print table
        print()
        print(f'{"":18}', end='')
        for sl in smr_labels:
            lbl = f'{sl}_{demand_label}'
            print(f' {lbl:>30} |', end='')
        print()
        print(f'{"Type":<18}', end='')
        for sl in smr_labels:
            print(f' {"Cap[GW]":>9} {"Gen[TWh]":>10} {"CF[%]":>8} |', end='')
        print()
        print('-' * (18 + 4 * 32))

        total_cap = {sl: 0 for sl in smr_labels}
        total_gen = {sl: 0 for sl in smr_labels}

        for gtype in GEN_ORDER:
            label = GEN_LABELS.get(gtype, gtype)
            print(f'{label:<18}', end='')
            for sl in smr_labels:
                cap = float(all_data[sl]['cap_gw'].get(gtype, 0))
                gen = float(all_data[sl]['gen_twh'].get(gtype, 0))
                if cap > 0.001:
                    cf = gen / (cap * 8.760) * 100  # CF = TWh / (GW * 8760h/1000)
                    total_cap[sl] += cap
                    total_gen[sl] += gen
                    print(f' {cap:>9.2f} {gen:>10.1f} {cf:>7.1f}% |', end='')
                else:
                    print(f' {"-":>9} {"-":>10} {"-":>8} |', end='')
            print()

        # Total row
        print('-' * (18 + 4 * 32))
        print(f'{"TOTAL":<18}', end='')
        for sl in smr_labels:
            cap = total_cap[sl]
            gen = total_gen[sl]
            cf = gen / (cap * 8.760) * 100 if cap > 0 else 0
            print(f' {cap:>9.2f} {gen:>10.1f} {cf:>7.1f}% |', end='')
        print()
