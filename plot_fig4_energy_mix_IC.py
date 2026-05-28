"""
Fig. 4 -- Energy mix comparison for IC Nuclear Scenarios.
Uses PowerGAMA Results.getEnergyMix() for data extraction.
Custom matplotlib stacked bar chart combining all 4 scenarios.

Output: IEEE/Fig4_comparison_energy_mix_IC.pdf and .png
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
BASE_DIR = pathlib.Path(__file__).parent
IC_DIR = BASE_DIR / 'scenarios' / 'nuclear_IC'
DATA_PATH = IC_DIR / 'data'
SYSTEM_PATH = DATA_PATH / 'system'

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

SCENARIOS = ['BL_IC', 'SMR1_IC', 'SMR3_IC', 'SMR6_IC']
SC_LABELS = {
    'BL_IC': 'BL (0 GW)',
    'SMR1_IC': 'SMR1 (1.5 GW)',
    'SMR3_IC': 'SMR3 (4.5 GW)',
    'SMR6_IC': 'SMR6 (9.0 GW)',
}

# SMR configuration (must match run_nuclear_IC.py)
SMR_UNIT_MW = 300
SMR_PMIN_FRAC = 0.10
SMR_FUELCOST = 9.37
SMR_SCENARIOS = {
    'BL_IC':   {'NO1': 0,    'NO2': 0,    'NO3': 0,    'NO4': 0,    'NO5': 0},
    'SMR1_IC': {'NO1': 300,  'NO2': 300,  'NO3': 300,  'NO4': 300,  'NO5': 300},
    'SMR3_IC': {'NO1': 900,  'NO2': 900,  'NO3': 900,  'NO4': 900,  'NO5': 900},
    'SMR6_IC': {'NO1': 1800, 'NO2': 1800, 'NO3': 1800, 'NO4': 1800, 'NO5': 1800},
}
SMR_NODES = {'NO1': 'NO1_3', 'NO2': 'NO2_1', 'NO3': 'NO3_1', 'NO4': 'NO4_1', 'NO5': 'NO5_1'}

# Generation type order and styling
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

DEMAND_TWH = 230.0


# ============================================================
# Load grid data for a given scenario
# ============================================================
def load_grid_and_results(scenario_name):
    """Load PowerGAMA GridData + Results for the given IC scenario."""
    print(f'  Loading grid data for {scenario_name}...')

    data = powergama.GridData()
    data.readGridData(
        nodes=SYSTEM_PATH / 'node.csv',
        ac_branches=SYSTEM_PATH / 'branch.csv',
        dc_branches=SYSTEM_PATH / 'dcbranch.csv',
        generators=SYSTEM_PATH / 'generator.csv',
        consumers=SYSTEM_PATH / 'consumer.csv',
    )

    # Timeseries profiles
    profiles = pd.read_csv(
        DATA_PATH / 'timeseries_profiles.csv',
        index_col=0, parse_dates=True,
    )
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    data.storagevalue_filling = pd.read_csv(
        DATA_PATH / 'storage' / 'profiles_storval_filling.csv'
    )
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0

    # Filter out zero-capacity generators
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    # Add SMR generators (must match run_nuclear_IC.py)
    smr_caps = SMR_SCENARIOS[scenario_name]
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
        new_df = pd.DataFrame(new_rows)
        data.generator = pd.concat([data.generator, new_df], ignore_index=True)
        print(f'    Added {len(new_rows)} SMR generators ({total_smr} MW)')

    # Open results database (read-only)
    sql_file = IC_DIR / scenario_name / 'results' / f'powergama_{scenario_name}.sqlite'
    print(f'    Opening results: {sql_file.name}')
    res = powergama.Results(data, str(sql_file), replace=False)

    return data, res


# ============================================================
# Extract Norwegian energy mix using PowerGAMA getEnergyMix
# ============================================================
def get_norway_energy_mix(res):
    """
    Use PowerGAMA Results.getEnergyMix() to get energy per area per type,
    then extract Norway ('NO') row and convert to TWh/yr.

    getEnergyMix() returns a DataFrame indexed by area (country level:
    'NO', 'SE', 'FI', 'DK', ...) with generator types as columns.
    Values are total MWh over the entire simulation period.
    """
    dfplot = res.getEnergyMix()

    # Extract Norway row (area='NO')
    no_row = dfplot.loc['NO'].fillna(0)

    # Convert MWh -> TWh/yr
    num_hours = len(res.grid.timerange)
    num_years = num_hours / (365.2425 * 24)
    total_twh = no_row / 1e6 / num_years

    return total_twh


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('Fig. 4 -- IC Energy Mix Comparison (PowerGAMA getEnergyMix)')
    print('=' * 60)

    # Extract data for all scenarios
    all_gen = {}
    for sc in SCENARIOS:
        print(f'\n--- {sc} ---')
        data, res = load_grid_and_results(sc)
        gen_twh = get_norway_energy_mix(res)
        all_gen[sc] = gen_twh
        print(f'    Total Norway: {gen_twh.sum():.1f} TWh/yr')
        for gtype in GEN_ORDER:
            val = gen_twh.get(gtype, 0)
            if not np.isnan(val) and val > 0.01:
                print(f'      {GEN_LABELS.get(gtype, gtype):18s}: {val:.1f} TWh')

    # ============================================================
    # Plot: Stacked bar chart, 4 scenarios side by side
    # ============================================================
    print('\nGenerating figure...')

    fig, ax = plt.subplots(figsize=(10, 7))

    x = np.arange(len(SCENARIOS))
    width = 0.6
    bottom = np.zeros(len(SCENARIOS))

    # Track which types actually have data (for legend)
    plotted_types = []

    for gtype in GEN_ORDER:
        vals = np.array([float(all_gen[sc].get(gtype, 0)) for sc in SCENARIOS])
        vals = np.nan_to_num(vals, nan=0.0)
        if vals.max() > 0.01:
            ax.bar(x, vals, width, bottom=bottom,
                   label=GEN_LABELS.get(gtype, gtype),
                   color=GEN_COLORS.get(gtype, '#999'),
                   edgecolor='white', linewidth=0.3)
            plotted_types.append(gtype)
            bottom += vals

    # Total TWh labels on top of each bar
    for i, sc in enumerate(SCENARIOS):
        ax.text(i, bottom[i] + 2, f'{bottom[i]:.0f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('TWh/yr', fontsize=12)
    ax.set_title(
        f'Norway Generation Mix \u2014 IC Nuclear Scenarios (annual avg, {DEMAND_TWH:.0f} TWh)',
        fontsize=12,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([SC_LABELS[sc] for sc in SCENARIOS], fontsize=10)
    ax.grid(True, axis='y', alpha=0.3)

    # Set y-axis limit with room for the total labels
    y_max = max(bottom) * 1.12
    ax.set_ylim(0, y_max)

    # Legend: place outside the plot on the right to avoid overlapping bars
    # Reverse order so it matches visual stacking (top type first)
    handles, labels = ax.get_legend_handles_labels()
    handles.reverse()
    labels.reverse()
    ax.legend(handles, labels,
              loc='upper left',
              bbox_to_anchor=(1.02, 1.0),
              borderaxespad=0,
              fontsize=9,
              frameon=True,
              edgecolor='0.8')

    fig.tight_layout()

    # Save
    out_dir = BASE_DIR / 'IEEE'
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / 'Fig4_comparison_energy_mix_IC.pdf',
                dpi=300, bbox_inches='tight')
    fig.savefig(out_dir / 'Fig4_comparison_energy_mix_IC.png',
                dpi=300, bbox_inches='tight')
    plt.close()

    print(f'\nSaved:')
    print(f'  IEEE/Fig4_comparison_energy_mix_IC.pdf')
    print(f'  IEEE/Fig4_comparison_energy_mix_IC.png')

    # ============================================================
    # Plot 2: Delta from baseline — change in TWh per source
    # ============================================================
    print('\nGenerating delta figure...')

    delta_scenarios = ['SMR1_IC', 'SMR3_IC', 'SMR6_IC']
    delta_labels = ['SMR1\n(1.5 GW)', 'SMR3\n(4.5 GW)', 'SMR6\n(9.0 GW)']
    bl = all_gen['BL_IC']

    # Types to show (skip types with negligible change)
    delta_types = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear', 'fossil_gas', 'biomass']

    fig2, ax2 = plt.subplots(figsize=(10, 6))

    x2 = np.arange(len(delta_scenarios))
    n_types = len(delta_types)
    bar_width = 0.8 / n_types

    for j, gtype in enumerate(delta_types):
        bl_val = float(bl.get(gtype, 0))
        if np.isnan(bl_val):
            bl_val = 0.0
        deltas = []
        for sc in delta_scenarios:
            sc_val = float(all_gen[sc].get(gtype, 0))
            if np.isnan(sc_val):
                sc_val = 0.0
            deltas.append(sc_val - bl_val)

        offset = (j - n_types / 2 + 0.5) * bar_width
        bars = ax2.bar(x2 + offset, deltas, bar_width,
                       label=GEN_LABELS.get(gtype, gtype),
                       color=GEN_COLORS.get(gtype, '#999'),
                       edgecolor='black', linewidth=0.3)

        # Value labels on bars with significant change
        for k, (bar, d) in enumerate(zip(bars, deltas)):
            if abs(d) > 0.3:
                va = 'bottom' if d >= 0 else 'top'
                y_off = 0.3 if d >= 0 else -0.3
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + y_off if d >= 0 else d - 0.3,
                         f'{d:+.1f}', ha='center', va=va, fontsize=6.5,
                         fontweight='bold')

    ax2.axhline(y=0, color='black', linewidth=0.8)
    ax2.set_ylabel('\u0394 TWh/yr (vs Baseline)', fontsize=11)
    ax2.set_title('Change in Generation Mix vs Baseline \u2014 IC Scenarios', fontsize=12)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(delta_labels, fontsize=10)
    ax2.grid(axis='y', alpha=0.3)
    ax2.legend(fontsize=8, loc='upper left', bbox_to_anchor=(1.02, 1.0),
               borderaxespad=0, frameon=True, edgecolor='0.8')

    fig2.tight_layout()
    fig2.savefig(out_dir / 'Fig4b_delta_energy_mix_IC.pdf', dpi=300, bbox_inches='tight')
    fig2.savefig(out_dir / 'Fig4b_delta_energy_mix_IC.png', dpi=300, bbox_inches='tight')
    plt.close()

    print(f'  IEEE/Fig4b_delta_energy_mix_IC.pdf')
    print(f'  IEEE/Fig4b_delta_energy_mix_IC.png')
    print('Done.')
