"""
SMR_NTC_border v2 — Analysis & plots using NordicNuclearAnalysis functions.

Generates plots for NTC_MD and NTC_IC scenarios using the integrated
NNA plotting functions (work_functions, plot_functions, database_functions).
"""

import sys
import pathlib
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import datetime

import powergama
from powergama.database import Database

# Add NNA functions to path — selective imports to avoid missing powergama.GIS
NNA_DIR = pathlib.Path(__file__).parent / 'NordicNuclearAnalysis NY'
sys.path.insert(0, str(NNA_DIR))

# Stub out powergama.GIS before importing NNA (our PowerGAMA build lacks GIS module)
import types
if not hasattr(powergama, 'GIS'):
    gis_stub = types.ModuleType('powergama.GIS')
    gis_stub._pointBetween = lambda *a, **kw: None
    sys.modules['powergama.GIS'] = gis_stub

from functions.work_functions import *
from functions.global_functions import get_hour_range
from functions.database_functions import (
    getNodalPricesFromDB, getStorageFillingInAreaFromDB,
    getStorageFillingInZoneFromDB, collect_flow_data,
    getSystemCostFromDB, getAreaPricesAverageFromDB,
)

# ============================================================
# Configuration
# ============================================================
BASE_DIR = pathlib.Path(__file__).parent.parent.parent
OUT_DIR = BASE_DIR / 'studies' / '2_ntc_border' / 'results'
OUT_DIR.mkdir(exist_ok=True)

SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
TIMEZONE = ZoneInfo("UTC")
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

# Scenarios to analyze
SCENARIOS = {
    'BL_MD':      ('nuclear_MD', 'BL_MD',      208, 0),
    'SMR_NTC_MD': ('nuclear_MD', 'SMR_NTC_MD', 208, 9300),
    'BL_IC':      ('nuclear_IC', 'BL_IC',      230, 0),
    'SMR_NTC_IC': ('nuclear_IC', 'SMR_NTC_IC', 230, 9300),
}

# Foreign interconnectors for cable saturation
FOREIGN_IC = [
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

# Cross-border connections for NNA flow plots
SELECTED_BRANCHES = [
    ['NO2_1', 'GB'],      # North Sea Link (DC — won't match AC filter, handled separately)
    ['NO1_5', 'SE3_5'],   # NO1-SE3_5
    ['NO1_5', 'SE3_7'],   # NO1-SE3_7
    ['NO3_1', 'SE2_4'],   # NO3-SE2_4
    ['NO4_1', 'SE1_1'],   # NO4-SE1_1
    ['NO4_3', 'SE2_1'],   # NO4-SE2_1
    ['NO4_1', 'FI_1'],    # NO4-FI_1
]


def load_grid_data(sc_dir):
    """Load grid data using our project structure (not NNA version-naming)."""
    data_path = BASE_DIR / 'scenarios' / sc_dir / 'data'
    system_path = data_path / 'system'

    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )

    ts_path = data_path / 'timeseries_profiles.csv'
    if not ts_path.exists():
        ts_path = BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'timeseries_profiles.csv'
    profiles = pd.read_csv(ts_path, index_col=0, parse_dates=True)
    profiles['const'] = 1
    data.profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)].reset_index()
    data.storagevalue_time = data.profiles[['const']]

    storval = pd.read_csv(data_path / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval

    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0

    # Filter zero-cap generators
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    return data


def get_sql_path(sc_dir, sc_name):
    return BASE_DIR / 'scenarios' / sc_dir / sc_name / 'results' / f'powergama_{sc_name}.sqlite'


def get_cable_saturation(db_path):
    """Extract export saturation from Res_DcBranches and Res_Branches."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    dc_flows = pd.read_sql_query("SELECT timestep, indx, flow FROM Res_DcBranches", conn)
    ac_flows = pd.read_sql_query("SELECT timestep, indx, flow FROM Res_Branches", conn)
    conn.close()

    results = {}
    for name, btype, csv_indx, node_from, node_to, capacity, no_zone in FOREIGN_IC:
        if btype == 'DC':
            flows = dc_flows[dc_flows['indx'] == csv_indx]['flow'].values
            export_flows = flows if node_from.startswith('NO') else -flows
        else:
            flows = ac_flows[ac_flows['indx'] == csv_indx]['flow'].values
            export_flows = flows

        threshold = 0.95 * capacity
        n_total = len(export_flows)
        n_saturated = int(np.sum(export_flows > threshold))
        sat_pct = round(n_saturated / n_total * 100, 2) if n_total > 0 else 0
        avg_export = round(float(np.mean(export_flows)), 1) if n_total > 0 else 0

        results[name] = {
            'capacity_mw': capacity,
            'zone': no_zone,
            'saturation_pct': sat_pct,
            'avg_export_mw': avg_export,
        }
    return results


def get_volume_weighted_prices(db_path, data_dir):
    """Volume-weighted zone price (Hjelmeland Eq. 5)."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    node_ids = nodes['id'].tolist()

    consumers = pd.read_csv(data_dir / 'system' / 'consumer.csv')
    ts_path = data_dir / 'timeseries_profiles.csv'
    if not ts_path.exists():
        ts_path = BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'timeseries_profiles.csv'
    profiles = pd.read_csv(ts_path, index_col=0, parse_dates=True).reset_index()
    profiles['const'] = 1
    T = len(profiles)

    no_node_map = {}
    for i, nid in enumerate(node_ids):
        zone = nid[:3] if nid[:2] == 'NO' else None
        if zone in NO_ZONES:
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
    conn.close()

    node_prices = {ni: np.zeros(T) for ni in no_indices}
    for ts, indx, price in rows:
        if indx in node_prices and ts < T:
            node_prices[indx][ts] = price

    zone_prices = {}
    for zone in NO_ZONES:
        sum_pd, sum_d = 0.0, 0.0
        for ni, z in no_node_map.items():
            if z != zone or ni not in node_demand or ni not in node_prices:
                continue
            sum_pd += np.sum(node_prices[ni] * node_demand[ni])
            sum_d += np.sum(node_demand[ni])
        zone_prices[zone] = round(sum_pd / sum_d, 2) if sum_d > 0 else 0.0
    return zone_prices


def get_generation_and_cf(db_path, nuc_mw):
    """Get generation mix and nuclear CF."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_out = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()

    num_hours = gen_out['timestep'].nunique()
    num_years = num_hours / (365.2425 * 24)

    gen_out = gen_out.merge(generators, on='indx', suffixes=('', '_g'))
    gen_out['country'] = gen_out['node'].str.extract(r'(NO|SE|FI|DK)')
    no = gen_out[gen_out['country'] == 'NO']
    gen_mix = no.groupby('type')['output'].sum() / 1e6 / num_years  # TWh/yr

    nuc_cf = None
    if nuc_mw > 0:
        nuc_prod = no[no['type'] == 'nuclear']['output'].sum()
        nuc_cf = nuc_prod / (nuc_mw * num_hours)

    return gen_mix.to_dict(), nuc_cf, num_hours


# ============================================================
# NNA-based plots for individual scenarios
# ============================================================
def plot_nna_scenario(sc_name, sc_dir, sc_sub, out_subdir):
    """Generate NNA plots for a single scenario."""
    db_path = get_sql_path(sc_dir, sc_sub)
    if not db_path.exists():
        print(f'  {sc_name}: SQLite MISSING, skipping NNA plots')
        return

    print(f'\n--- NNA plots for {sc_name} ---')
    data = load_grid_data(sc_dir)
    database = Database(db_path)
    time_max_min = [0, len(data.timerange)]

    plot_dir = out_subdir / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)

    START = {"year": SIM_YEAR_START, "month": 1, "day": 1, "hour": 0}
    END = {"year": SIM_YEAR_END, "month": 12, "day": 31, "hour": 23}
    time_full = get_hour_range(SIM_YEAR_START, SIM_YEAR_END, TIMEZONE, START, END)

    # 1. Zonal prices — all NO zones, duration curve
    print('  Plotting zonal prices...')
    try:
        plot_config_zp = {
            'zones': NO_ZONES,
            'plot_by_year': False,
            'duration_curve': True,
            'save_fig': True,
            'interval': 12,
            'tex_font': False,
        }
        calcPlot_ZonalPrices_FromDB(data, database, time_full, plot_dir, DATE_START, plot_config_zp)
    except Exception as e:
        print(f'    Zonal prices failed: {e}')

    # 2. Production by type (NO area) — full timeline
    print('  Plotting production by type...')
    try:
        # One year example (2010)
        START_1y = {"year": 2010, "month": 1, "day": 1, "hour": 0}
        END_1y = {"year": 2010, "month": 12, "day": 31, "hour": 23}
        time_1y = get_hour_range(SIM_YEAR_START, SIM_YEAR_END, TIMEZONE, START_1y, END_1y)

        plot_config_lg = {
            'area': 'NO',
            'title': f'Production and Price in Norway — {sc_name}',
            'fig_size': (12, 6),
            'plot_full_timeline': True,
            'duration_curve': False,
            'box_in_frame': False,
            'save_fig': True,
            'interval': 1,
        }
        calcPlot_LG_FromDB(data, database, time_1y, plot_dir, DATE_START, plot_config_lg)
    except Exception as e:
        print(f'    Production plot failed: {e}')

    # 3. Storage filling — NO area, year-by-year overlay
    print('  Plotting storage filling...')
    try:
        plot_config_sf = {
            'areas': ['NO'],
            'relative': True,
            'plot_by_year': True,
            'duration_curve': False,
            'save_fig': True,
            'interval': 1,
            'empty_threshold': 1e-6,
            'title': f'Reservoir Filling — {sc_name}',
            'tex_font': False,
            'include_legend': False,
            'fig_size': (10, 5),
        }
        plot_SF_Areas_FromDB(data, database, time_full, plot_dir, DATE_START, plot_config_sf, START, END)
    except Exception as e:
        print(f'    Storage filling failed: {e}')

    # 4. Hydro production, reservoir, inflow — NO, full timeline
    print('  Plotting hydro/reservoir/inflow...')
    try:
        START_hri = {"year": 2010, "month": 1, "day": 1, "hour": 0}
        END_hri = {"year": 2010, "month": 12, "day": 31, "hour": 23}
        time_hri = get_hour_range(SIM_YEAR_START, SIM_YEAR_END, TIMEZONE, START_hri, END_hri)

        plot_config_hri = {
            'area': 'NO',
            'genType': 'hydro',
            'relative_storage': True,
            'plot_full_timeline': True,
            'box_in_frame': False,
            'save_fig': True,
            'interval': 1,
        }
        calcPlot_HRI_FromDB(data, database, time_hri, plot_dir, DATE_START, plot_config_hri)
    except Exception as e:
        print(f'    HRI plot failed: {e}')

    # 5. Cross-border flows — AC branches
    print('  Plotting cross-border flows...')
    try:
        plot_config_flow = {
            'plot_by_year': False,
            'duration_curve': True,
            'duration_relative': True,
            'save_fig': True,
            'interval': 1,
            'check': False,
            'tex_font': False,
        }
        plot_Flow_fromDB(data, database, DATE_START, time_full, plot_dir, plot_config_flow, SELECTED_BRANCHES)
    except Exception as e:
        print(f'    Flow plot failed: {e}')

    print(f'  NNA plots saved to: {plot_dir}')


# ============================================================
# Custom comparison plots
# ============================================================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot_zone_price_comparison(all_results, demand_label, out_dir):
    """Bar chart: zone prices across BL and NTC scenarios."""
    bl_key = f'BL_{demand_label}'
    ntc_key = f'SMR_NTC_{demand_label}'

    if bl_key not in all_results or ntc_key not in all_results:
        return

    bl_prices = all_results[bl_key]['zone_prices']
    ntc_prices = all_results[ntc_key]['zone_prices']

    x = np.arange(len(NO_ZONES))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width/2, [bl_prices[z] for z in NO_ZONES], width, label=f'Baseline ({demand_label})', color='#2196F3')
    bars2 = ax.bar(x + width/2, [ntc_prices[z] for z in NO_ZONES], width, label=f'SMR_NTC ({demand_label})', color='#FF5722')

    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_title(f'Volume-Weighted Zone Prices — {demand_label} Demand')
    ax.set_xticks(x)
    ax.set_xticklabels(NO_ZONES)
    ax.legend()
    ax.bar_label(bars1, fmt='%.0f', fontsize=8)
    ax.bar_label(bars2, fmt='%.0f', fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / f'Fig_NTC_zone_prices_{demand_label}.pdf', dpi=150, bbox_inches='tight')
    fig.savefig(out_dir / f'Fig_NTC_zone_prices_{demand_label}.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved zone price comparison: {demand_label}')


def plot_cable_saturation_comparison(all_results, demand_label, out_dir):
    """Horizontal bar chart: cable saturation BL vs NTC."""
    bl_key = f'BL_{demand_label}'
    ntc_key = f'SMR_NTC_{demand_label}'

    if bl_key not in all_results or ntc_key not in all_results:
        return

    bl_sat = all_results[bl_key]['cable_saturation']
    ntc_sat = all_results[ntc_key]['cable_saturation']

    cable_names = [ic[0] for ic in FOREIGN_IC]
    bl_vals = [bl_sat.get(c, {}).get('saturation_pct', 0) for c in cable_names]
    ntc_vals = [ntc_sat.get(c, {}).get('saturation_pct', 0) for c in cable_names]

    y = np.arange(len(cable_names))
    height = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(y - height/2, bl_vals, height, label=f'Baseline', color='#2196F3', alpha=0.8)
    ax.barh(y + height/2, ntc_vals, height, label=f'SMR_NTC', color='#FF5722', alpha=0.8)

    ax.set_xlabel('Export Saturation [%]')
    ax.set_title(f'Cable Saturation (>95% NTC) — {demand_label} Demand')
    ax.set_yticks(y)
    ax.set_yticklabels(cable_names)
    ax.set_xlim(0, 105)
    ax.legend(loc='lower right')
    ax.axvline(x=95, color='red', linestyle='--', alpha=0.5, label='95% threshold')

    fig.tight_layout()
    fig.savefig(out_dir / f'Fig_NTC_cable_saturation_{demand_label}.pdf', dpi=150, bbox_inches='tight')
    fig.savefig(out_dir / f'Fig_NTC_cable_saturation_{demand_label}.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved cable saturation chart: {demand_label}')


def plot_generation_mix_comparison(all_results, demand_label, out_dir):
    """Stacked bar: generation mix BL vs NTC."""
    bl_key = f'BL_{demand_label}'
    ntc_key = f'SMR_NTC_{demand_label}'

    if bl_key not in all_results or ntc_key not in all_results:
        return

    gen_types = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear', 'fossil_gas', 'biomass']
    colors = {
        'hydro': '#1976D2', 'ror': '#64B5F6', 'wind_on': '#4CAF50', 'wind_off': '#81C784',
        'solar': '#FFC107', 'nuclear': '#FF5722', 'fossil_gas': '#757575', 'biomass': '#8D6E63',
    }

    scenarios = [bl_key, ntc_key]
    labels = ['Baseline', 'SMR_NTC']

    fig, ax = plt.subplots(figsize=(6, 6))
    x = np.arange(len(scenarios))
    bottoms = np.zeros(len(scenarios))

    for gt in gen_types:
        vals = []
        for sc in scenarios:
            vals.append(all_results[sc]['gen_mix'].get(gt, 0))
        ax.bar(x, vals, bottom=bottoms, label=gt, color=colors.get(gt, '#999999'), width=0.5)
        bottoms += vals

    ax.set_ylabel('Generation [TWh/yr]')
    ax.set_title(f'Norway Generation Mix — {demand_label} Demand')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper right', fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / f'Fig_NTC_generation_mix_{demand_label}.pdf', dpi=150, bbox_inches='tight')
    fig.savefig(out_dir / f'Fig_NTC_generation_mix_{demand_label}.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f'  Saved generation mix: {demand_label}')


# ============================================================
# Main
# ============================================================
def main():
    import json

    print('=' * 70)
    print('SMR_NTC_border v2 — Results extraction & plotting')
    print('=' * 70)

    # 1. Extract results for all scenarios
    all_results = {}
    for sc_name, (sc_dir, sc_sub, demand_twh, nuc_mw) in SCENARIOS.items():
        db = get_sql_path(sc_dir, sc_sub)
        data_dir = BASE_DIR / 'scenarios' / sc_dir / 'data'

        if not db.exists():
            print(f'  {sc_name}: MISSING')
            continue

        print(f'\nExtracting {sc_name}...')
        zp = get_volume_weighted_prices(db, data_dir)
        gen_mix, nuc_cf, num_hours = get_generation_and_cf(db, nuc_mw)
        num_years = num_hours / (365.2425 * 24)
        total_gen = sum(gen_mix.values())
        net_export = round(total_gen - demand_twh, 2)
        sat = get_cable_saturation(db)

        all_results[sc_name] = {
            'demand_twh': demand_twh,
            'nuclear_mw': nuc_mw,
            'zone_prices': zp,
            'national_avg_price': round(np.mean(list(zp.values())), 2),
            'gen_mix': {k: round(v, 2) for k, v in gen_mix.items()},
            'total_gen_twh_yr': round(total_gen, 2),
            'net_export_twh_yr': net_export,
            'nuclear_cf': round(nuc_cf, 4) if nuc_cf else None,
            'nuclear_prod_twh_yr': round(gen_mix.get('nuclear', 0), 2),
            'cable_saturation': sat,
        }

        print(f'  Prices: {zp}')
        print(f'  National avg: {all_results[sc_name]["national_avg_price"]} EUR/MWh')
        if nuc_cf:
            print(f'  Nuclear CF: {nuc_cf*100:.1f}%')
        print(f'  Net export: {net_export:+.1f} TWh/yr')

    # 2. Save JSON
    json_path = OUT_DIR / 'results_summary.json'
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f'\nSaved: {json_path}')

    # 3. Save CSV summary
    rows = []
    for sc_name, r in all_results.items():
        row = {
            'scenario': sc_name,
            'demand_twh': r['demand_twh'],
            'nuclear_mw': r['nuclear_mw'],
            'national_avg_price': r['national_avg_price'],
            'nuclear_cf': r.get('nuclear_cf'),
            'nuclear_prod_twh_yr': r.get('nuclear_prod_twh_yr', 0),
            'net_export_twh_yr': r['net_export_twh_yr'],
        }
        for z in NO_ZONES:
            row[f'price_{z}'] = r['zone_prices'].get(z, 0)
        for ic in FOREIGN_IC:
            row[f'sat_{ic[0]}'] = r['cable_saturation'].get(ic[0], {}).get('saturation_pct', 0)
        rows.append(row)
    csv_path = OUT_DIR / 'results_summary.csv'
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f'Saved: {csv_path}')

    # 4. Cable saturation detail CSV
    sat_rows = []
    for sc_name, r in all_results.items():
        for cname, cdata in r['cable_saturation'].items():
            sat_rows.append({'scenario': sc_name, 'interconnector': cname, **cdata})
    sat_csv = OUT_DIR / 'cable_saturation_detail.csv'
    pd.DataFrame(sat_rows).to_csv(sat_csv, index=False)
    print(f'Saved: {sat_csv}')

    # 5. Custom comparison plots
    print('\n--- Custom comparison plots ---')
    for dl in ['MD', 'IC']:
        plot_zone_price_comparison(all_results, dl, OUT_DIR)
        plot_cable_saturation_comparison(all_results, dl, OUT_DIR)
        plot_generation_mix_comparison(all_results, dl, OUT_DIR)

    # 6. Text report
    write_results_report(all_results, OUT_DIR)

    # 7. NNA plots per scenario
    for sc_name, (sc_dir, sc_sub, _, _) in SCENARIOS.items():
        sc_out = OUT_DIR / sc_name
        sc_out.mkdir(exist_ok=True)
        plot_nna_scenario(sc_name, sc_dir, sc_sub, sc_out)

    print(f'\nAll results saved to: {OUT_DIR}')


def write_results_report(all_results, out_dir):
    """Write formatted text report."""
    lines = []
    lines.append('=' * 70)
    lines.append('SMR_NTC_border v2 — RESULTS (corrected node placement)')
    lines.append('=' * 70)
    lines.append('')
    lines.append('Nuclear placed at cable endpoint nodes:')
    lines.append('  NO1_5: 1,800 MW (SE3 cables)')
    lines.append('  NO2_1: 1,500 MW (North Sea Link)')
    lines.append('  NO2_4: 2,100 MW (NorNed + NordLink)')
    lines.append('  NO2_5: 1,500 MW (Skagerrak)')
    lines.append('  NO3_1:   900 MW (SE2_4 cable)')
    lines.append('  NO4_1: 1,200 MW (SE1_1 + FI_1)')
    lines.append('  NO4_3:   300 MW (SE2_1)')
    lines.append('  TOTAL: 9,300 MW (31 units)')
    lines.append('')

    for demand_label in ['MD', 'IC']:
        bl_key = f'BL_{demand_label}'
        ntc_key = f'SMR_NTC_{demand_label}'
        if bl_key not in all_results or ntc_key not in all_results:
            continue

        bl = all_results[bl_key]
        ntc = all_results[ntc_key]

        lines.append('=' * 70)
        lines.append(f'{demand_label} DEMAND ({bl["demand_twh"]} TWh)')
        lines.append('=' * 70)

        lines.append(f'\nZone Prices [EUR/MWh]:')
        lines.append(f'  {"Zone":<6} {"Baseline":>10} {"SMR_NTC":>10} {"Change":>10}')
        for z in NO_ZONES:
            bp = bl['zone_prices'][z]
            np_ = ntc['zone_prices'][z]
            chg = (np_ - bp) / bp * 100
            lines.append(f'  {z:<6} {bp:>10.1f} {np_:>10.1f} {chg:>+9.0f}%')
        lines.append(f'  {"Avg":<6} {bl["national_avg_price"]:>10.1f} {ntc["national_avg_price"]:>10.1f} '
                     f'{(ntc["national_avg_price"]-bl["national_avg_price"])/bl["national_avg_price"]*100:>+9.0f}%')

        lines.append(f'\nNuclear: CF={ntc["nuclear_cf"]*100:.1f}%, '
                     f'prod={ntc["nuclear_prod_twh_yr"]:.1f} TWh/yr')
        lines.append(f'Net export: BL={bl["net_export_twh_yr"]:+.1f}, '
                     f'NTC={ntc["net_export_twh_yr"]:+.1f} TWh/yr')

        lines.append(f'\nCable Saturation:')
        lines.append(f'  {"Interconnector":<20} {"NTC":>6} {"BL":>6} {"NTC":>6} {"Diff":>8}')
        for ic in FOREIGN_IC:
            cname = ic[0]
            cap = ic[5]
            bs = bl['cable_saturation'].get(cname, {}).get('saturation_pct', 0)
            ns = ntc['cable_saturation'].get(cname, {}).get('saturation_pct', 0)
            lines.append(f'  {cname:<20} {cap:>6} {bs:>5.1f}% {ns:>5.1f}% {ns-bs:>+7.1f}pp')
        lines.append('')

    report_path = out_dir / 'RESULTS_REPORT.txt'
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f'Saved: {report_path}')


if __name__ == '__main__':
    main()
