"""
Generate plots for all Nuclear MD scenarios from SQLite results directly.

Per-scenario plots (saved to scenarios/nuclear_MD/<scenario>/plots/):
  1. zone_prices_NO.pdf           — Bar chart: zone prices NO1-NO5
  2. price_duration_curves.pdf    — Price duration curves NO1-NO5
  3. energy_mix_NO.pdf            — Stacked bar: Norwegian generation mix
  4. storage_filling_NO.pdf       — Monthly reservoir filling (seasonal)

Cross-scenario comparisons (saved to scenarios/nuclear_MD/plots/):
  5. comparison_zone_prices.pdf   — Grouped bar: zone prices all scenarios
  6. comparison_energy_mix.pdf    — Stacked bar: generation mix all scenarios
  7. comparison_price_reduction.pdf — Price reduction vs baseline
  8. comparison_summary.pdf       — Summary table
"""

import pathlib
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# Configuration
# ============================================================
BASE_DIR = pathlib.Path(__file__).parent
MD_DIR = BASE_DIR / 'scenarios' / 'nuclear_MD'

SCENARIOS = ['BL_MD', 'SMR1_MD', 'SMR3_MD', 'SMR6_MD']
SMR_MW = {'BL_MD': 0, 'SMR1_MD': 1500, 'SMR3_MD': 4500, 'SMR6_MD': 9000}
NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

ZONE_COLORS = {'NO1': '#1f77b4', 'NO2': '#ff7f0e', 'NO3': '#2ca02c',
               'NO4': '#d62728', 'NO5': '#9467bd'}

GEN_COLORS = {
    'hydro': '#1f77b4', 'ror': '#6baed6', 'wind_on': '#2ca02c',
    'wind_off': '#98df8a', 'solar': '#ffbb33', 'nuclear': '#e31a1c',
    'fossil_gas': '#7f7f7f', 'biomass': '#8c564b',
}
GEN_LABELS = {
    'hydro': 'Hydro (reg.)', 'ror': 'Run-of-river', 'wind_on': 'Wind onshore',
    'wind_off': 'Wind offshore', 'solar': 'Solar', 'nuclear': 'Nuclear (SMR)',
    'fossil_gas': 'Gas', 'biomass': 'Biomass',
}
GEN_ORDER = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear', 'fossil_gas', 'biomass']

SC_COLORS = {'BL_MD': '#1f77b4', 'SMR1_MD': '#ff7f0e', 'SMR3_MD': '#2ca02c', 'SMR6_MD': '#e31a1c'}
SC_LABELS = {'BL_MD': 'BL (0 GW)', 'SMR1_MD': 'SMR1 (1.5 GW)',
             'SMR3_MD': 'SMR3 (4.5 GW)', 'SMR6_MD': 'SMR6 (9.0 GW)'}


def sql_path(scenario):
    return MD_DIR / scenario / 'results' / f'powergama_{scenario}.sqlite'


# ============================================================
# Data extraction
# ============================================================
def get_zone_prices(scenario):
    """Volume-weighted zone price (Hjelmeland Eq. 5): Σ(p_t × d_t) / Σ(d_t)."""
    db = sql_path(scenario)
    conn = sqlite3.connect(db)
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    node_ids = nodes['id'].tolist()
    node_zones = [nid[:3] if nid[:2] == 'NO' else nid[:3] for nid in node_ids]

    # Load consumer data and profiles
    consumers = pd.read_csv(MD_DIR / 'data' / 'system' / 'consumer.csv')
    profiles = pd.read_csv(MD_DIR / 'data' / 'timeseries_profiles.csv',
                           index_col=0, parse_dates=True).reset_index()
    T = len(profiles)

    # Build node → zone for NO only
    no_node_map = {}  # indx -> zone
    for i, (nid, z) in enumerate(zip(node_ids, node_zones)):
        if z in NO_ZONES:
            no_node_map[i] = z

    # Build hourly demand per node
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

    # Extract hourly prices for NO nodes
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

    # Volume-weighted per zone
    zone_prices = {}
    for zone in NO_ZONES:
        sum_pd, sum_d = 0.0, 0.0
        for ni, z in no_node_map.items():
            if z != zone or ni not in node_demand or ni not in node_prices:
                continue
            sum_pd += np.sum(node_prices[ni] * node_demand[ni])
            sum_d += np.sum(node_demand[ni])
        zone_prices[zone] = sum_pd / sum_d if sum_d > 0 else 0.0
    return zone_prices


def get_zone_price_timeseries(scenario):
    conn = sqlite3.connect(sql_path(scenario))
    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    prices = pd.read_sql_query("SELECT timestep, indx, nodalprice FROM Res_Nodes", conn)
    conn.close()
    prices = prices.merge(nodes, on='indx')
    prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
    return pd.DataFrame({z: prices[prices['zone'] == z].groupby('timestep')['nodalprice'].mean().values
                         for z in NO_ZONES})


def get_generation_mix(scenario):
    conn = sqlite3.connect(sql_path(scenario))
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_out = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()
    num_years = gen_out['timestep'].nunique() / (365.2425 * 24)
    gen_out = gen_out.merge(generators, on='indx', suffixes=('', '_g'))
    gen_out['country'] = gen_out['node'].str.extract(r'(NO|SE|FI|DK)')
    no = gen_out[gen_out['country'] == 'NO']
    return no.groupby('type')['output'].sum() / 1e6 / num_years  # TWh/yr


def get_zone_generation(scenario):
    conn = sqlite3.connect(sql_path(scenario))
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    gen_out = pd.read_sql_query("SELECT timestep, indx, output FROM Res_Generators", conn)
    conn.close()
    num_years = gen_out['timestep'].nunique() / (365.2425 * 24)
    gen_out = gen_out.merge(generators, on='indx', suffixes=('', '_g'))
    gen_out['zone'] = gen_out['node'].str.extract(r'(NO\d)')
    no = gen_out[gen_out['zone'].notna()]
    return no.groupby(['zone', 'type'])['output'].sum() / 1e6 / num_years


def get_storage_monthly(scenario):
    """Get monthly average reservoir filling per zone."""
    conn = sqlite3.connect(sql_path(scenario))
    generators = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)
    storage = pd.read_sql_query("SELECT timestep, indx, storage FROM Res_Storage", conn)
    conn.close()

    # Get storage_cap from generator CSV
    gen_csv = pd.read_csv(MD_DIR / 'data' / 'system' / 'generator.csv')
    gen_csv = gen_csv[gen_csv['pmax'] > 0].reset_index(drop=True)

    hydro_gens = generators[generators['type'] == 'hydro'].copy()
    hydro_gens['zone'] = hydro_gens['node'].str.extract(r'(NO\d)')
    no_hydro = hydro_gens[hydro_gens['zone'].notna()]
    no_hydro = no_hydro.merge(gen_csv[['node', 'type', 'storage_cap']].drop_duplicates(),
                               on=['node', 'type'], how='left')

    storage_no = storage[storage['indx'].isin(no_hydro['indx'])].merge(
        no_hydro[['indx', 'zone', 'storage_cap']], on='indx')
    storage_no['filling'] = storage_no['storage'] / storage_no['storage_cap']

    # Build month mapping for 30 years (1991-2020)
    hours = pd.date_range('1991-01-01', periods=storage['timestep'].max() + 1, freq='h')
    ts_map = pd.DataFrame({'timestep': range(len(hours)), 'month': hours.month})
    storage_no = storage_no.merge(ts_map, on='timestep')

    # Weighted average by storage_cap
    result = {}
    for zone in NO_ZONES:
        zs = storage_no[storage_no['zone'] == zone]
        monthly = zs.groupby('month').apply(
            lambda g: np.average(g['filling'], weights=g['storage_cap']) if len(g) > 0 else np.nan
        )
        result[zone] = monthly
    return pd.DataFrame(result)


# ============================================================
# Per-scenario plots
# ============================================================
def plot_per_scenario(scenario):
    plot_dir = MD_DIR / scenario / 'plots'

    print(f'  {scenario}: extracting data...', flush=True)
    zp = get_zone_prices(scenario)
    zts = get_zone_price_timeseries(scenario)
    gen_mix = get_generation_mix(scenario)
    zone_gen = get_zone_generation(scenario)

    # --- 1. Zone prices bar chart ---
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [zp[z] for z in NO_ZONES]
    bars = ax.bar(NO_ZONES, vals, color=[ZONE_COLORS[z] for z in NO_ZONES])
    ax.bar_label(bars, fmt='%.1f', fontsize=10)
    ax.set_ylabel('EUR/MWh')
    ax.set_title(f'{SC_LABELS[scenario]} — Average Zone Prices (30-yr)')
    ax.set_ylim(0, max(vals) * 1.2)
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_dir / 'zone_prices_NO.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'    zone_prices_NO.pdf')

    # --- 2. Price duration curves ---
    fig, ax = plt.subplots(figsize=(10, 6))
    for z in NO_ZONES:
        sorted_p = np.sort(zts[z].values)[::-1]
        pct = np.linspace(0, 100, len(sorted_p))
        ax.plot(pct, sorted_p, label=f'{z} ({zp[z]:.1f})', linewidth=0.8,
                color=ZONE_COLORS[z])
    ax.set_xlabel('Duration (%)')
    ax.set_ylabel('EUR/MWh')
    ax.set_title(f'{SC_LABELS[scenario]} — Price Duration Curves')
    ax.legend(fontsize=9)
    cap = min(500, np.nanpercentile(zts.values.flatten(), 99.5) * 1.3)
    ax.set_ylim(0, cap)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_dir / 'price_duration_curves.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'    price_duration_curves.pdf')

    # --- 3. Energy mix stacked bar (per zone) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(NO_ZONES))
    width = 0.6
    bottom = np.zeros(len(NO_ZONES))
    for gtype in GEN_ORDER:
        vals = []
        for z in NO_ZONES:
            v = zone_gen.get((z, gtype), 0)
            vals.append(v)
        if max(vals) > 0.01:
            ax.bar(x, vals, width, bottom=bottom, label=GEN_LABELS.get(gtype, gtype),
                   color=GEN_COLORS.get(gtype, '#999'))
            bottom += vals

    ax.set_ylabel('TWh/yr')
    ax.set_title(f'{SC_LABELS[scenario]} — Generation Mix per Zone (annual avg)')
    ax.set_xticks(x)
    ax.set_xticklabels(NO_ZONES)
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, axis='y', alpha=0.3)
    # Add totals
    for i, z in enumerate(NO_ZONES):
        ax.text(i, bottom[i] + 0.5, f'{bottom[i]:.0f}', ha='center', fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / 'energy_mix_NO.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'    energy_mix_NO.pdf')

    # --- 4. Seasonal reservoir filling ---
    print(f'  {scenario}: computing storage filling...', flush=True)
    try:
        monthly_fill = get_storage_monthly(scenario)
        fig, ax = plt.subplots(figsize=(10, 5))
        month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Des']
        for z in NO_ZONES:
            ax.plot(range(1, 13), monthly_fill[z].values, 'o-', label=z,
                    color=ZONE_COLORS[z], markersize=4)
        ax.set_xlabel('Month')
        ax.set_ylabel('Filling (fraction)')
        ax.set_title(f'{SC_LABELS[scenario]} — Seasonal Reservoir Filling (30-yr avg)')
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(month_labels)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(plot_dir / 'storage_filling_NO.pdf', dpi=150, bbox_inches='tight')
        plt.close()
        print(f'    storage_filling_NO.pdf')
    except Exception as e:
        print(f'    storage_filling failed: {e}')

    return zp, gen_mix


# ============================================================
# Cross-scenario comparison plots
# ============================================================
def plot_comparisons(all_prices, all_gen):
    comp_dir = MD_DIR / 'plots'
    comp_dir.mkdir(exist_ok=True)

    # --- 5. Comparison zone prices ---
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(NO_ZONES))
    width = 0.18
    for i, sc in enumerate(SCENARIOS):
        vals = [all_prices[sc][z] for z in NO_ZONES]
        bars = ax.bar(x + i * width, vals, width, label=SC_LABELS[sc],
                      color=SC_COLORS[sc], alpha=0.85)
        ax.bar_label(bars, fmt='%.0f', fontsize=7, rotation=90, padding=2)
    ax.set_xlabel('Price Zone')
    ax.set_ylabel('EUR/MWh')
    ax.set_title('Zone Prices — MD Nuclear Scenarios (30-year average)')
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(NO_ZONES)
    ax.legend(loc='upper right')
    ax.set_ylim(0, max(all_prices['BL_MD'].values()) * 1.25)
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(comp_dir / 'comparison_zone_prices.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  comparison_zone_prices.pdf')

    # --- 6. Comparison energy mix ---
    fig, ax = plt.subplots(figsize=(10, 7))
    x = np.arange(len(SCENARIOS))
    width = 0.6
    bottom = np.zeros(len(SCENARIOS))
    for gtype in GEN_ORDER:
        vals = [all_gen[sc].get(gtype, 0) for sc in SCENARIOS]
        if max(vals) > 0.01:
            ax.bar(x, vals, width, bottom=bottom, label=GEN_LABELS.get(gtype, gtype),
                   color=GEN_COLORS.get(gtype, '#999'))
            bottom += vals
    ax.set_ylabel('TWh/yr')
    ax.set_title('Norway Generation Mix — MD Nuclear Scenarios (annual avg)')
    ax.set_xticks(x)
    ax.set_xticklabels([SC_LABELS[sc] for sc in SCENARIOS], fontsize=9)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, axis='y', alpha=0.3)
    for i, sc in enumerate(SCENARIOS):
        ax.text(i, bottom[i] + 1, f'{bottom[i]:.0f}', ha='center', fontsize=9, fontweight='bold')
    fig.tight_layout()
    fig.savefig(comp_dir / 'comparison_energy_mix.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  comparison_energy_mix.pdf')

    # --- 7. Price reduction vs baseline ---
    fig, ax = plt.subplots(figsize=(10, 6))
    smr_sc = ['SMR1_MD', 'SMR3_MD', 'SMR6_MD']
    x = np.arange(len(NO_ZONES))
    width = 0.25
    for i, sc in enumerate(smr_sc):
        reductions = [(all_prices[sc][z] - all_prices['BL_MD'][z]) / all_prices['BL_MD'][z] * 100
                      for z in NO_ZONES]
        bars = ax.bar(x + i * width, reductions, width, label=SC_LABELS[sc],
                      color=SC_COLORS[sc], alpha=0.85)
        ax.bar_label(bars, fmt='%.0f%%', fontsize=7)
    ax.set_xlabel('Price Zone')
    ax.set_ylabel('Price Change vs Baseline (%)')
    ax.set_title('Price Reduction from Nuclear — MD Scenarios')
    ax.set_xticks(x + width)
    ax.set_xticklabels(NO_ZONES)
    ax.legend()
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(comp_dir / 'comparison_price_reduction.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  comparison_price_reduction.pdf')

    # --- 8. Summary table ---
    fig, ax = plt.subplots(figsize=(15, 11))
    ax.axis('off')

    col_labels = [''] + [SC_LABELS[sc] for sc in SCENARIOS] + ['BL → SMR6']
    rows = []

    # Section: Zone prices
    rows.append(['ZONE PRICES [EUR/MWh]'] + [''] * (len(SCENARIOS) + 1))
    for z in NO_ZONES:
        row = [z]
        for sc in SCENARIOS:
            row.append(f'{all_prices[sc][z]:.1f}')
        d = all_prices['SMR6_MD'][z] - all_prices['BL_MD'][z]
        pct = d / all_prices['BL_MD'][z] * 100
        row.append(f'{d:+.1f} ({pct:+.0f}%)')
        rows.append(row)
    # Average
    row = ['Average']
    for sc in SCENARIOS:
        row.append(f'{np.mean([all_prices[sc][z] for z in NO_ZONES]):.1f}')
    bl_avg = np.mean([all_prices['BL_MD'][z] for z in NO_ZONES])
    s6_avg = np.mean([all_prices['SMR6_MD'][z] for z in NO_ZONES])
    row.append(f'{s6_avg - bl_avg:+.1f} ({(s6_avg - bl_avg) / bl_avg * 100:+.0f}%)')
    rows.append(row)

    rows.append([''] * (len(SCENARIOS) + 2))

    # Section: Generation
    rows.append(['GENERATION [TWh/yr]'] + [''] * (len(SCENARIOS) + 1))
    for gtype in GEN_ORDER:
        row = [GEN_LABELS.get(gtype, gtype)]
        for sc in SCENARIOS:
            v = all_gen[sc].get(gtype, 0)
            row.append(f'{v:.1f}' if v >= 0.1 else '—')
        bl_v = all_gen['BL_MD'].get(gtype, 0)
        s6_v = all_gen['SMR6_MD'].get(gtype, 0)
        delta = s6_v - bl_v
        row.append(f'{delta:+.1f}' if abs(delta) >= 0.1 else '—')
        rows.append(row)
    # Total
    row = ['TOTAL']
    for sc in SCENARIOS:
        row.append(f'{sum(all_gen[sc].get(t, 0) for t in GEN_ORDER):.1f}')
    bl_t = sum(all_gen['BL_MD'].get(t, 0) for t in GEN_ORDER)
    s6_t = sum(all_gen['SMR6_MD'].get(t, 0) for t in GEN_ORDER)
    row.append(f'{s6_t - bl_t:+.1f}')
    rows.append(row)

    rows.append([''] * (len(SCENARIOS) + 2))

    # Section: Key metrics
    rows.append(['KEY METRICS'] + [''] * (len(SCENARIOS) + 1))
    # Nuclear CF
    row = ['Nuclear CF']
    for sc in SCENARIOS:
        if SMR_MW[sc] > 0:
            nuc = all_gen[sc].get('nuclear', 0)
            cf = nuc * 1e6 / (SMR_MW[sc] * 8760)
            row.append(f'{cf:.0%}')
        else:
            row.append('—')
    row.append('')
    rows.append(row)
    # Hydro+RoR
    row = ['Hydro+RoR']
    for sc in SCENARIOS:
        h = all_gen[sc].get('hydro', 0) + all_gen[sc].get('ror', 0)
        row.append(f'{h:.1f} TWh')
    bl_h = all_gen['BL_MD'].get('hydro', 0) + all_gen['BL_MD'].get('ror', 0)
    s6_h = all_gen['SMR6_MD'].get('hydro', 0) + all_gen['SMR6_MD'].get('ror', 0)
    row.append(f'{s6_h - bl_h:+.1f}')
    rows.append(row)
    # Net export
    row = ['Net export']
    for sc in SCENARIOS:
        total = sum(all_gen[sc].get(t, 0) for t in GEN_ORDER)
        row.append(f'{total - 208:+.1f} TWh')
    row.append('')
    rows.append(row)

    table = ax.table(cellText=rows, colLabels=col_labels,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.5)

    # Style headers
    for j in range(len(col_labels)):
        table[0, j].set_facecolor('#4472C4')
        table[0, j].set_text_props(color='white', fontweight='bold')
    # Style section rows
    for i, row in enumerate(rows, start=1):
        if row[0] in ['ZONE PRICES [EUR/MWh]', 'GENERATION [TWh/yr]', 'KEY METRICS']:
            for j in range(len(col_labels)):
                table[i, j].set_facecolor('#D6E4F0')
                table[i, j].set_text_props(fontweight='bold')

    ax.set_title('Nuclear MD Scenarios — Summary (30-year average, 1991-2020)',
                 fontsize=14, fontweight='bold', pad=20)
    fig.tight_layout()
    fig.savefig(comp_dir / 'comparison_summary.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  comparison_summary.pdf')

    # --- 9. Reservoir filling comparison ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    month_labels = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

    # Left: all zones for BL_MD
    ax = axes[0]
    try:
        mf = get_storage_monthly('BL_MD')
        for z in NO_ZONES:
            ax.plot(range(1, 13), mf[z].values, 'o-', label=z,
                    color=ZONE_COLORS[z], markersize=4)
        ax.set_title('BL_MD — Reservoir Filling by Zone')
    except Exception as e:
        ax.text(0.5, 0.5, f'Error: {e}', ha='center', transform=ax.transAxes)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel('Filling (fraction)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Right: national average for all scenarios
    ax = axes[1]
    for sc in SCENARIOS:
        try:
            mf = get_storage_monthly(sc)
            national = mf.mean(axis=1)
            ax.plot(range(1, 13), national.values, 'o-', label=SC_LABELS[sc],
                    color=SC_COLORS[sc], markersize=4)
        except Exception as e:
            pass
    ax.set_title('Reservoir Filling — Scenario Comparison (Norway avg)')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(comp_dir / 'comparison_storage_filling.pdf', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  comparison_storage_filling.pdf')


# ============================================================
# Console summary
# ============================================================
def print_summary(all_prices, all_gen):
    print('\n' + '=' * 95)
    print('SAMLET SAMMENLIGNING — MD KJERNEKRAFT-SCENARIER (30-års gjennomsnitt)')
    print('=' * 95)

    print(f'\nSONEPRISER [EUR/MWh]:')
    header = f'{"Sone":<8}'
    for sc in SCENARIOS:
        header += f' {SC_LABELS[sc]:>14}'
    header += f' {"BL→SMR6":>16}'
    print(header)
    print('-' * (8 + 15 * len(SCENARIOS) + 17))

    for z in NO_ZONES:
        row = f'{z:<8}'
        for sc in SCENARIOS:
            row += f' {all_prices[sc][z]:>14.2f}'
        d = all_prices['SMR6_MD'][z] - all_prices['BL_MD'][z]
        pct = d / all_prices['BL_MD'][z] * 100
        row += f'  {d:>+6.1f} ({pct:>+4.0f}%)'
        print(row)

    row = f'{"Avg":<8}'
    for sc in SCENARIOS:
        row += f' {np.mean([all_prices[sc][z] for z in NO_ZONES]):>14.2f}'
    bl_a = np.mean([all_prices['BL_MD'][z] for z in NO_ZONES])
    s6_a = np.mean([all_prices['SMR6_MD'][z] for z in NO_ZONES])
    row += f'  {s6_a - bl_a:>+6.1f} ({(s6_a - bl_a) / bl_a * 100:>+4.0f}%)'
    print(row)

    print(f'\nGENERASJONSMIKS NORGE [TWh/yr]:')
    header = f'{"Type":<18}'
    for sc in SCENARIOS:
        header += f' {SC_LABELS[sc]:>14}'
    header += f' {"BL→SMR6":>14}'
    print(header)
    print('-' * (18 + 15 * len(SCENARIOS) + 15))

    for gtype in GEN_ORDER:
        row = f'{GEN_LABELS.get(gtype, gtype):<18}'
        for sc in SCENARIOS:
            v = all_gen[sc].get(gtype, 0)
            row += f' {v:>14.2f}' if v >= 0.01 else f' {"—":>14}'
        d = all_gen['SMR6_MD'].get(gtype, 0) - all_gen['BL_MD'].get(gtype, 0)
        row += f' {d:>+14.2f}' if abs(d) >= 0.01 else f' {"—":>14}'
        print(row)

    print('-' * (18 + 15 * len(SCENARIOS) + 15))
    row = f'{"TOTAL":<18}'
    for sc in SCENARIOS:
        row += f' {sum(all_gen[sc].get(t, 0) for t in GEN_ORDER):>14.2f}'
    d = sum(all_gen['SMR6_MD'].get(t, 0) for t in GEN_ORDER) - sum(all_gen['BL_MD'].get(t, 0) for t in GEN_ORDER)
    row += f' {d:>+14.2f}'
    print(row)

    print(f'\nNØKKELTALL:')
    print(f'{"Metrikk":<22}', end='')
    for sc in SCENARIOS:
        print(f' {SC_LABELS[sc]:>14}', end='')
    print()
    print('-' * (22 + 15 * len(SCENARIOS)))

    print(f'{"Nuclear CF":<22}', end='')
    for sc in SCENARIOS:
        if SMR_MW[sc] > 0:
            nuc = all_gen[sc].get('nuclear', 0)
            print(f' {nuc * 1e6 / (SMR_MW[sc] * 8760):>13.0%}', end='')
        else:
            print(f' {"—":>14}', end='')
    print()

    print(f'{"Hydro+RoR TWh/yr":<22}', end='')
    for sc in SCENARIOS:
        h = all_gen[sc].get('hydro', 0) + all_gen[sc].get('ror', 0)
        print(f' {h:>14.1f}', end='')
    print()

    print(f'{"Netto eksport TWh":<22}', end='')
    for sc in SCENARIOS:
        total = sum(all_gen[sc].get(t, 0) for t in GEN_ORDER)
        print(f' {total - 208:>+14.1f}', end='')
    print()


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('GENERATING PLOTS FOR NUCLEAR MD SCENARIOS')
    print('=' * 60)

    all_prices = {}
    all_gen = {}

    # Allow specifying scenarios via command line
    import sys
    if len(sys.argv) > 1:
        run_scenarios = sys.argv[1:]
    else:
        run_scenarios = SCENARIOS

    for sc in run_scenarios:
        print(f'\n--- {sc} ---')
        try:
            zp, gm = plot_per_scenario(sc)
            all_prices[sc] = zp
            all_gen[sc] = gm
        except Exception as e:
            print(f'  SKIPPED {sc}: {e}')

    if len(all_prices) == len(SCENARIOS):
        print(f'\n--- CROSS-SCENARIO COMPARISONS ---')
        plot_comparisons(all_prices, all_gen)
        print_summary(all_prices, all_gen)
    elif len(all_prices) >= 2:
        print(f'\n  Skipping comparisons — not all scenarios available ({list(all_prices.keys())})')
        print(f'  Run with all 4 scenarios to generate comparison plots.')

    print(f'\nAll plots saved.')
