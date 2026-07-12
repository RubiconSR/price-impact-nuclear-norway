"""
Energy mix (MD) and Capacity Factor comparison (MD + IC) for Norway.
Uses PowerGAMA Results.getEnergyMix() for data extraction.

Output:
  IEEE/Fig5_comparison_energy_mix_MD.pdf/.png
  IEEE/Fig6_capacity_factor.pdf/.png
"""

import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import powergama

# ============================================================
# Configuration
# ============================================================
BASE_DIR = pathlib.Path(__file__).parent.parent.parent

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

# SMR configuration (must match run_nuclear_MD.py / run_nuclear_IC.py)
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

SC_LABELS = {
    'BL': 'BL (0 GW)', 'SMR1': 'SMR1 (1.5 GW)',
    'SMR3': 'SMR3 (4.5 GW)', 'SMR6': 'SMR6 (9.0 GW)',
}

GEN_ORDER = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear', 'fossil_gas', 'biomass']
GEN_LABELS = {
    'hydro': 'Hydro (reg.)', 'ror': 'Run-of-river', 'wind_on': 'Wind onshore',
    'wind_off': 'Wind offshore', 'solar': 'Solar', 'nuclear': 'Nuclear (SMR)',
    'fossil_gas': 'Gas', 'biomass': 'Biomass',
}
GEN_COLORS = {
    'hydro': '#1f77b4', 'ror': '#6baed6', 'wind_on': '#2ca02c',
    'wind_off': '#98df8a', 'solar': '#ffbb33', 'nuclear': '#e31a1c',
    'fossil_gas': '#7f7f7f', 'biomass': '#8c564b',
}


# ============================================================
# Load grid data + results
# ============================================================
def load_scenario(demand_label, smr_label):
    """Load PowerGAMA GridData + Results for a given scenario."""
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

    # Add SMR generators
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

    # Find results file
    sql_file = scenario_dir / scenario_name / 'results' / f'powergama_{scenario_name}.sqlite'
    if not sql_file.exists():
        sql_file = scenario_dir / 'results' / f'powergama_{scenario_name}.sqlite'

    res = powergama.Results(data, str(sql_file), replace=False)
    return data, res


def get_norway_energy_mix(res):
    """Extract Norway energy mix using PowerGAMA getEnergyMix(), return TWh/yr."""
    dfplot = res.getEnergyMix()
    no_row = dfplot.loc['NO'].fillna(0)
    num_hours = len(res.grid.timerange)
    num_years = num_hours / (365.2425 * 24)
    return no_row / 1e6 / num_years


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    out_dir = BASE_DIR / 'IEEE'
    out_dir.mkdir(exist_ok=True)
    smr_labels = ['BL', 'SMR1', 'SMR3', 'SMR6']

    # ==========================================================
    # 1. Energy mix — MD scenarios
    # ==========================================================
    print('=' * 60)
    print('ENERGY MIX — MD SCENARIOS')
    print('=' * 60)

    md_gen = {}
    for sl in smr_labels:
        sc_name = f'{sl}_MD'
        print(f'\n--- {sc_name} ---')
        data, res = load_scenario('MD', sl)
        gen_twh = get_norway_energy_mix(res)
        md_gen[sl] = gen_twh
        print(f'    Total Norway: {gen_twh.sum():.1f} TWh/yr')
        for gt in GEN_ORDER:
            val = gen_twh.get(gt, 0)
            if not np.isnan(val) and val > 0.01:
                print(f'      {GEN_LABELS.get(gt, gt):18s}: {val:.1f} TWh')

    # Plot MD energy mix
    fig, ax = plt.subplots(figsize=(10, 7))
    x = np.arange(len(smr_labels))
    width = 0.6
    bottom = np.zeros(len(smr_labels))

    for gtype in GEN_ORDER:
        vals = np.array([float(md_gen[sl].get(gtype, 0)) for sl in smr_labels])
        vals = np.nan_to_num(vals, nan=0.0)
        if vals.max() > 0.01:
            ax.bar(x, vals, width, bottom=bottom,
                   label=GEN_LABELS.get(gtype, gtype),
                   color=GEN_COLORS.get(gtype, '#999'),
                   edgecolor='white', linewidth=0.3)
            bottom += vals

    for i, sl in enumerate(smr_labels):
        ax.text(i, bottom[i] + 2, f'{bottom[i]:.0f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('TWh/yr', fontsize=12)
    ax.set_title('Norway Generation Mix \u2014 MD Nuclear Scenarios (annual avg, 208 TWh)',
                 fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels([SC_LABELS[sl] for sl in smr_labels], fontsize=10)
    ax.grid(True, axis='y', alpha=0.3)
    ax.set_ylim(0, max(bottom) * 1.12)

    handles, labels = ax.get_legend_handles_labels()
    handles.reverse()
    labels.reverse()
    ax.legend(handles, labels, loc='upper left', bbox_to_anchor=(1.02, 1.0),
              borderaxespad=0, fontsize=9, frameon=True, edgecolor='0.8')
    fig.tight_layout()
    fig.savefig(out_dir / 'Fig5_comparison_energy_mix_MD.pdf', dpi=300, bbox_inches='tight')
    fig.savefig(out_dir / 'Fig5_comparison_energy_mix_MD.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('\nSaved: IEEE/Fig5_comparison_energy_mix_MD.pdf/.png')

    # ==========================================================
    # 2. Capacity factor comparison — MD + IC
    # ==========================================================
    print('\n' + '=' * 60)
    print('CAPACITY FACTOR — MD + IC')
    print('=' * 60)

    # Nuclear installed capacity per scenario [MW]
    installed_mw = {'SMR1': 1500, 'SMR3': 4500, 'SMR6': 9000}

    # Get nuclear generation from energy mix data already loaded (MD)
    cf_md = {}
    for sl in ['SMR1', 'SMR3', 'SMR6']:
        nuc_twh = float(md_gen[sl].get('nuclear', 0))
        # CF = actual / (installed * 8760 * 0.90 availability)
        # But simulated gen already accounts for availability, so:
        # CF = actual_TWh / (installed_MW * 8760h * num_years / num_years / 1e6)
        # = actual_TWh / (installed_MW * 8760 / 1e6)
        theoretical_twh = installed_mw[sl] * 8760 / 1e6
        cf_md[sl] = nuc_twh / theoretical_twh * 100
        print(f'  {sl}_MD: nuclear={nuc_twh:.1f} TWh/yr, CF={cf_md[sl]:.1f}%')

    # Load IC scenarios for nuclear generation
    print()
    ic_gen = {}
    cf_ic = {}
    for sl in ['SMR1', 'SMR3', 'SMR6']:
        sc_name = f'{sl}_IC'
        print(f'  Loading {sc_name}...')
        data, res = load_scenario('IC', sl)
        gen_twh = get_norway_energy_mix(res)
        ic_gen[sl] = gen_twh
        nuc_twh = float(gen_twh.get('nuclear', 0))
        theoretical_twh = installed_mw[sl] * 8760 / 1e6
        cf_ic[sl] = nuc_twh / theoretical_twh * 100
        print(f'  {sc_name}: nuclear={nuc_twh:.1f} TWh/yr, CF={cf_ic[sl]:.1f}%')

    # Plot CF comparison
    fig, ax = plt.subplots(figsize=(8, 5))

    smr_cf_labels = ['SMR1\n(1.5 GW)', 'SMR3\n(4.5 GW)', 'SMR6\n(9.0 GW)']
    x = np.arange(3)
    width = 0.35

    md_vals = [cf_md['SMR1'], cf_md['SMR3'], cf_md['SMR6']]
    ic_vals = [cf_ic['SMR1'], cf_ic['SMR3'], cf_ic['SMR6']]

    bars_md = ax.bar(x - width/2, md_vals, width, label='Moderate Demand (208 TWh)',
                     color='#1f77b4', edgecolor='black', linewidth=0.5)
    bars_ic = ax.bar(x + width/2, ic_vals, width, label='Increased Consumption (230 TWh)',
                     color='#ff7f0e', edgecolor='black', linewidth=0.5)

    for bars in [bars_md, bars_ic]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

    # Reference line at 90% nominal availability
    ax.axhline(y=90, color='grey', linestyle='--', linewidth=1, alpha=0.7)
    ax.text(2.45, 91, 'Nominal\navailability\n(90%)', fontsize=7, color='grey',
            ha='right', va='bottom')

    ax.set_ylabel('Nuclear Capacity Factor [%]', fontsize=11)
    ax.set_title('Nuclear Capacity Factor \u2014 Price Cannibalization Effect', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(smr_cf_labels, fontsize=10)
    ax.legend(fontsize=9, loc='upper right')
    ax.set_ylim(0, 105)
    ax.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_dir / 'Fig6_capacity_factor.pdf', dpi=300, bbox_inches='tight')
    fig.savefig(out_dir / 'Fig6_capacity_factor.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('\nSaved: IEEE/Fig6_capacity_factor.pdf/.png')

    print('\nDone.')
