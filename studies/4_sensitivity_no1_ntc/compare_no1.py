"""Compare BL_MD vs BL_MD_NTC2x — how much of NO1's price anomaly is NTC-driven?

"""

import sqlite3
import pathlib
import time
import pandas as pd
import numpy as np

BASE = pathlib.Path('/Users/siva/Downloads/MT/Nuclear Power Norway Price')

ORIG_SQL = BASE / 'scenarios/nuclear_MD/BL_MD/results/powergama_BL_MD.sqlite'
NEW_SQL = BASE / 'studies/4_sensitivity_no1_ntc/results/powergama_BL_MD_NTC2x.sqlite'
DATA_DIR = BASE / 'scenarios/nuclear_MD/data'

ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

NO1_NO2_BRANCHES_NEW_CAP = {
    'NO2_1→NO1_3':  734.60,
    'NO2_1→NO1_4': 1240.56,
    'NO1_3→NO2_3':  478.06,
    'NO1_4→NO2_3': 1261.55,
    'NO1_5→NO2_3': 1065.24,
}


def extract_metrics(sql_file, label, cap_overrides=None):
    print(f'\n=== {label}: {sql_file.name} ===')
    t0 = time.time()
    conn = sqlite3.connect(str(sql_file))

    nodes = pd.read_sql_query("SELECT indx, id FROM Grid_Nodes", conn)
    nodes['zone'] = nodes['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')

    # Zone prices — simple node-mean per zone (matches paper Fig 3)
    no_nodes = nodes[nodes['zone'].isin(ZONES)]
    no_indx = tuple(int(i) for i in no_nodes['indx'])
    prices = pd.read_sql_query(
        f"SELECT timestep, indx, nodalprice FROM Res_Nodes WHERE indx IN {no_indx}",
        conn,
    )
    prices = prices.merge(no_nodes[['indx', 'zone']], on='indx')
    zone_simple = {
        z: prices[prices['zone'] == z].groupby('timestep')['nodalprice'].mean().mean()
        for z in ZONES
    }

    # NO1 high-price hours
    no1_price_t = prices[prices['zone'] == 'NO1'].groupby('timestep')['nodalprice'].mean()
    n_steps = len(no1_price_t)
    n_high = (no1_price_t > 100).sum()
    n_very_high = (no1_price_t > 200).sum()

    # True Eq. 5 — load-weighted national average across all NO nodes & all timesteps
    cons = pd.read_csv(DATA_DIR / 'system' / 'consumer.csv')
    cons = cons[cons['node'].str.startswith('NO')].copy()
    cons['zone'] = cons['node'].str.extract(r'(NO\d)')

    profile_names = sorted(cons['demand_ref'].unique())
    profiles = pd.read_csv(DATA_DIR / 'timeseries_profiles.csv', usecols=profile_names)

    id_to_indx = dict(zip(nodes['id'], nodes['indx']))
    price_pivot = prices.pivot(index='timestep', columns='indx', values='nodalprice')

    # Aggregate demand per node
    per_node = cons.groupby(['node', 'zone', 'demand_ref'], as_index=False)['demand_avg'].sum()

    zone_num = {z: 0.0 for z in ZONES}
    zone_den = {z: 0.0 for z in ZONES}
    for _, row in per_node.iterrows():
        indx = id_to_indx.get(row['node'])
        if indx is None or indx not in price_pivot.columns:
            continue
        prof = profiles[row['demand_ref']].to_numpy(dtype=np.float64)
        weight = row['demand_avg'] * prof
        node_prices = price_pivot[indx].to_numpy(dtype=np.float64)
        zone_num[row['zone']] += np.sum(node_prices * weight)
        zone_den[row['zone']] += np.sum(weight)

    zone_weighted = {z: zone_num[z] / zone_den[z] for z in ZONES}
    nat_avg_eq5 = sum(zone_num.values()) / sum(zone_den.values())

    # Branch saturation for the 5 NO1↔NO2 branches
    cap = pd.read_sql_query(
        "SELECT indx, fromIndx, toIndx, capacity FROM Grid_Branches",
        conn,
    )
    cap = cap.merge(nodes[['indx', 'id']].rename(columns={'indx': 'fromIndx', 'id': 'from_id'}), on='fromIndx')
    cap = cap.merge(nodes[['indx', 'id']].rename(columns={'indx': 'toIndx', 'id': 'to_id'}), on='toIndx')
    cap['label'] = cap['from_id'] + '→' + cap['to_id']
    no1_no2_mask = cap['label'].isin(NO1_NO2_BRANCHES_NEW_CAP.keys())
    no1_no2 = cap[no1_no2_mask].copy()

    flow_indx = tuple(int(i) for i in no1_no2['indx'])
    flows = pd.read_sql_query(
        f"SELECT timestep, indx, flow FROM Res_Branches WHERE indx IN {flow_indx}",
        conn,
    )
    conn.close()

    sat_rows = []
    for _, br in no1_no2.iterrows():
        f = flows[flows['indx'] == br['indx']]['flow']
        sat99 = (f.abs() >= 0.99 * br['capacity']).sum()
        sat_rows.append({
            'branch': br['label'],
            'capacity_MW': br['capacity'],
            'sat_99pct_hrs': sat99,
            'sat_99pct_share': sat99 / n_steps * 100,
        })
    sat_df = pd.DataFrame(sat_rows)

    print(f'  Timer: {n_steps}')
    print(f'  Sonepris (simpel mean): NO1={zone_simple["NO1"]:.2f}, NO2={zone_simple["NO2"]:.2f}, NO3={zone_simple["NO3"]:.2f}, NO4={zone_simple["NO4"]:.2f}, NO5={zone_simple["NO5"]:.2f}')
    print(f'  Sonepris (last-vektet): NO1={zone_weighted["NO1"]:.2f}, NO2={zone_weighted["NO2"]:.2f}')
    print(f'  Nasjonalt true Eq.5: {nat_avg_eq5:.2f} EUR/MWh')
    print(f'  NO1 timer >100€: {n_high} ({n_high/n_steps*100:.1f}%), >200€: {n_very_high} ({n_very_high/n_steps*100:.1f}%)')
    print(f'  NO1↔NO2 metning:')
    print(sat_df.round(2).to_string(index=False))
    print(f'  [{time.time()-t0:.1f}s]')

    return {
        'label': label,
        'zone_simple': zone_simple,
        'zone_weighted': zone_weighted,
        'nat_eq5': nat_avg_eq5,
        'n_steps': n_steps,
        'n_high_100': n_high,
        'n_high_200': n_very_high,
        'saturation': sat_df,
    }


def main():
    if not NEW_SQL.exists():
        print(f'NY SQLite ikke ferdig ennå: {NEW_SQL}')
        print(f'Original finnes: {ORIG_SQL.exists()}')
        return

    print('=' * 70)
    print('Sammenligning: BL_MD (original) vs BL_MD_NTC2x (NO1↔NO2 doblet)')
    print('=' * 70)

    orig = extract_metrics(ORIG_SQL, 'ORIGINAL')
    new = extract_metrics(NEW_SQL, '2× NO1↔NO2')

    print('\n\n' + '=' * 70)
    print('SAMMENDRAG — endring fra original til doblet NO1↔NO2')
    print('=' * 70)

    print(f'\nSonepriser (EUR/MWh, simpel mean per sone):')
    print(f'  {"Sone":<6} {"Original":>10} {"2x NTC":>10} {"Δ":>10} {"%-endring":>10}')
    for z in ZONES:
        o, n = orig['zone_simple'][z], new['zone_simple'][z]
        print(f'  {z:<6} {o:>10.2f} {n:>10.2f} {n-o:>10.2f} {(n-o)/o*100:>10.2f}')

    print(f'\nNO1 sonepris (last-vektet): {orig["zone_weighted"]["NO1"]:.2f} → {new["zone_weighted"]["NO1"]:.2f} EUR/MWh '
          f'(Δ {new["zone_weighted"]["NO1"]-orig["zone_weighted"]["NO1"]:+.2f})')

    print(f'\nNasjonalt true Eq. 5 (last-vektet, alle NO-noder, alle timer):')
    print(f'  Original BL_MD: {orig["nat_eq5"]:.2f} EUR/MWh')
    print(f'  2x NO1↔NO2:    {new["nat_eq5"]:.2f} EUR/MWh')
    print(f'  Δ:             {new["nat_eq5"]-orig["nat_eq5"]:+.2f} EUR/MWh ({(new["nat_eq5"]-orig["nat_eq5"])/orig["nat_eq5"]*100:+.2f}%)')

    print(f'\nNO1 høypristimer:')
    print(f'  >100 EUR/MWh: {orig["n_high_100"]:>7} → {new["n_high_100"]:>7} '
          f'(Δ {new["n_high_100"]-orig["n_high_100"]:+}, {(new["n_high_100"]-orig["n_high_100"])/orig["n_high_100"]*100:+.1f}%)')
    print(f'  >200 EUR/MWh: {orig["n_high_200"]:>7} → {new["n_high_200"]:>7} '
          f'(Δ {new["n_high_200"]-orig["n_high_200"]:+}, {(new["n_high_200"]-orig["n_high_200"])/max(orig["n_high_200"],1)*100:+.1f}%)')

    print(f'\nMetning på NO1↔NO2-korridoren (% av tiden ≥99% av kapasitet):')
    merged = orig['saturation'].merge(new['saturation'], on='branch', suffixes=('_orig', '_2x'))
    merged['Δ_pp'] = merged['sat_99pct_share_2x'] - merged['sat_99pct_share_orig']
    print(merged[['branch', 'capacity_MW_orig', 'capacity_MW_2x',
                  'sat_99pct_share_orig', 'sat_99pct_share_2x', 'Δ_pp']].round(2).to_string(index=False))

    # Save
    out = BASE / 'output' / 'figures' / 'no1_ntc_sensitivity_comparison.csv'
    summary_rows = []
    for z in ZONES:
        summary_rows.append({
            'metric': f'zone_simple_{z}',
            'original': orig['zone_simple'][z],
            'NTC2x': new['zone_simple'][z],
            'delta': new['zone_simple'][z] - orig['zone_simple'][z],
        })
    summary_rows.append({'metric': 'NO1_load_weighted',
                         'original': orig['zone_weighted']['NO1'],
                         'NTC2x': new['zone_weighted']['NO1'],
                         'delta': new['zone_weighted']['NO1'] - orig['zone_weighted']['NO1']})
    summary_rows.append({'metric': 'national_true_Eq5',
                         'original': orig['nat_eq5'],
                         'NTC2x': new['nat_eq5'],
                         'delta': new['nat_eq5'] - orig['nat_eq5']})
    summary_rows.append({'metric': 'NO1_hrs_above_100',
                         'original': orig['n_high_100'],
                         'NTC2x': new['n_high_100'],
                         'delta': new['n_high_100'] - orig['n_high_100']})
    summary_rows.append({'metric': 'NO1_hrs_above_200',
                         'original': orig['n_high_200'],
                         'NTC2x': new['n_high_200'],
                         'delta': new['n_high_200'] - orig['n_high_200']})
    pd.DataFrame(summary_rows).round(3).to_csv(out, index=False)
    print(f'\nLagret: {out}')


if __name__ == '__main__':
    main()
