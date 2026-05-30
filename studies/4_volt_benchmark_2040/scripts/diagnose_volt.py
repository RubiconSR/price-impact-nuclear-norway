"""
Diagnostikk: hvorfor stiger NO5-prisen når vi legger inn 4 GW OW på NO2?

SQLite-skjema:
  Grid_Nodes(indx, id, area, lat, lon)
  Grid_Branches(indx, fromIndx, toIndx, capacity, reactance, resistance)
  Res_Branches(timestep, indx, flow, loss)
  Res_DcBranches(timestep, indx, flow, cap_sensitivity, loss)
  Grid_Generators(indx, node, type, ...)  -- node er id (string)
  Res_Generators(timestep, indx, output, ...)
"""

import pathlib
import sqlite3
import pandas as pd

BASE_DIR = pathlib.Path(__file__).parent.parent.parent.parent
RESULTS_DIR = BASE_DIR / 'studies' / '4_volt_benchmark_2040' / 'results'
SOURCE_DATA = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data' / 'system'

SCENARIOS = ['N0_OW0', 'N0_OW1', 'N0_OW2', 'N1_OW0', 'N1jevnt_OW0']


def load_grid_meta():
    nodes = pd.read_csv(SOURCE_DATA / 'node.csv')
    branches = pd.read_csv(SOURCE_DATA / 'branch.csv')
    dcbranches = pd.read_csv(SOURCE_DATA / 'dcbranch.csv')
    nodes['zone'] = nodes['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')[0]
    return nodes, branches, dcbranches


def diagnose_no2_1(nodes, branches, dcbranches):
    print('\n=== 1. NO2_1-noden og dens brancher (fra CSV) ===')
    n = nodes[nodes['id'] == 'NO2_1']
    print(n[['id', 'zone', 'lat', 'lon']].to_string(index=False))

    ac_from = branches[branches['node_from'] == 'NO2_1'][['node_from', 'node_to', 'capacity']]
    ac_to = branches[branches['node_to'] == 'NO2_1'][['node_from', 'node_to', 'capacity']]
    dc_from = dcbranches[dcbranches['node_from'] == 'NO2_1'][['node_from', 'node_to', 'capacity']]
    dc_to = dcbranches[dcbranches['node_to'] == 'NO2_1'][['node_from', 'node_to', 'capacity']]
    print('\nAC-brancher fra NO2_1:')
    print(ac_from.to_string(index=False) if len(ac_from) else '  (ingen)')
    print('AC-brancher til NO2_1:')
    print(ac_to.to_string(index=False) if len(ac_to) else '  (ingen)')
    print('DC-brancher fra NO2_1:')
    print(dc_from.to_string(index=False) if len(dc_from) else '  (ingen)')
    print('DC-brancher til NO2_1:')
    print(dc_to.to_string(index=False) if len(dc_to) else '  (ingen)')


def get_node_id_to_indx(sql_file):
    conn = sqlite3.connect(str(sql_file))
    df = pd.read_sql("SELECT indx, id FROM Grid_Nodes", conn)
    conn.close()
    return dict(zip(df['id'], df['indx'])), dict(zip(df['indx'], df['id']))


def branch_flows_for_node(sql_file, node_id):
    """Snittflyt på alle AC- og DC-brancher koblet til node_id."""
    conn = sqlite3.connect(str(sql_file))
    nodes_df = pd.read_sql("SELECT indx, id FROM Grid_Nodes", conn)
    id2 = dict(zip(nodes_df['indx'], nodes_df['id']))
    target = nodes_df.loc[nodes_df['id'] == node_id, 'indx'].iloc[0]

    # AC: Grid_Branches via fromIndx/toIndx
    ac = pd.read_sql(
        f"SELECT b.indx, b.fromIndx, b.toIndx, b.capacity, "
        f"  AVG(r.flow) AS mean_flow "
        f"FROM Grid_Branches b JOIN Res_Branches r ON b.indx=r.indx "
        f"WHERE b.fromIndx={target} OR b.toIndx={target} "
        f"GROUP BY b.indx", conn)
    # Res_DcBranches indeksen er separat — men Grid_Branches inneholder bare AC.
    # DC-grener er ikke i Grid_Branches; vi må mappe via Grid_Nodes-relasjon mot
    # Res_DcBranches.indx, som er indeksen i CSV-filen dcbranch.csv.
    # Sjekk Res_DcBranches
    n_dc = pd.read_sql("SELECT COUNT(DISTINCT indx) AS n FROM Res_DcBranches", conn)
    conn.close()

    ac['from_id'] = ac['fromIndx'].map(id2)
    ac['to_id'] = ac['toIndx'].map(id2)
    return ac, n_dc.iloc[0, 0]


def dc_flows_for_node(sql_file, node_id, dcbranches_csv):
    """DC-flyt — må mappe via dcbranch.csv-rekkefølge."""
    conn = sqlite3.connect(str(sql_file))
    dc = pd.read_sql(
        "SELECT indx, AVG(flow) as mean_flow FROM Res_DcBranches GROUP BY indx",
        conn)
    conn.close()
    # PowerGAMA bruker DataFrame.index for indx; etter pmax>0-filtreringen
    # i load_grid_data er det reset_index()-en som gjelder.
    # Men dcbranch.csv har ikke pmax-filtrering — alle DC-grener er aktive.
    df = dcbranches_csv.reset_index().rename(columns={'index': 'csv_idx'})
    # indx i Res_DcBranches matcher rekkefølgen etter at GridData har lest CSV
    df['indx'] = df['csv_idx']
    df = df.merge(dc, on='indx')
    df_node = df[(df['node_from'] == node_id) | (df['node_to'] == node_id)]
    return df_node[['node_from', 'node_to', 'capacity', 'mean_flow']]


def compare_node_flows(scenarios, node_id, dcbranches_csv):
    print(f'\n=== 2. AC-brancheflyt for {node_id} (snitt MW, +ve = ut av {node_id}) ===')

    by_branch = {}
    n_dc_each = {}
    for s in scenarios:
        sql = RESULTS_DIR / f'{s}.sqlite'
        if not sql.exists():
            continue
        ac, n_dc = branch_flows_for_node(sql, node_id)
        n_dc_each[s] = n_dc
        for _, row in ac.iterrows():
            if row['from_id'] == node_id:
                other = row['to_id']
                sign = +1
            else:
                other = row['from_id']
                sign = -1
            key = ('AC', other, row['capacity'])
            by_branch.setdefault(key, {})[s] = sign * row['mean_flow']

    print(f'  {"line":<10} {"to/from":<10} {"cap":>8}', end='')
    for s in scenarios:
        print(f' {s:>14}', end='')
    print()
    for (kind, other, cap), vals in sorted(by_branch.items(), key=lambda x: x[0][1]):
        print(f'  {kind:<10} {other:<10} {cap:>8.0f}', end='')
        for s in scenarios:
            v = vals.get(s, 0)
            print(f' {v:>+14.1f}', end='')
        print()

    print(f'\n=== 2b. DC-flyt for {node_id} (snitt MW, +ve = ut av {node_id}) ===')
    by_dc = {}
    for s in scenarios:
        sql = RESULTS_DIR / f'{s}.sqlite'
        if not sql.exists():
            continue
        dc = dc_flows_for_node(sql, node_id, dcbranches_csv)
        for _, row in dc.iterrows():
            if row['node_from'] == node_id:
                other = row['node_to']
                sign = +1
            else:
                other = row['node_from']
                sign = -1
            key = (other, row['capacity'])
            by_dc.setdefault(key, {})[s] = sign * row['mean_flow']

    print(f'  {"":<10} {"to/from":<10} {"cap":>8}', end='')
    for s in scenarios:
        print(f' {s:>14}', end='')
    print()
    for (other, cap), vals in sorted(by_dc.items(), key=lambda x: x[0][0]):
        print(f'  {"DC":<10} {other:<10} {cap:>8.0f}', end='')
        for s in scenarios:
            v = vals.get(s, 0)
            print(f' {v:>+14.1f}', end='')
        print()


def gen_production_by_zone_type(sql_file):
    """TWh/år per zone × type, snittet over 30 år."""
    conn = sqlite3.connect(str(sql_file))
    gens = pd.read_sql("SELECT indx, node, type FROM Grid_Generators", conn)
    out = pd.read_sql(
        "SELECT indx, SUM(output) AS total_mwh FROM Res_Generators GROUP BY indx",
        conn)
    conn.close()
    df = gens.merge(out, on='indx')
    df['zone'] = df['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')[0]
    df['twh_per_year'] = df['total_mwh'] / 30 / 1e6
    return df.groupby(['zone', 'type'])['twh_per_year'].sum().unstack(fill_value=0)


def compare_production(scenarios, zones, types):
    print(f'\n=== 3. Norsk produksjon per sone × type (TWh/år snitt over 30 år) ===')
    for s in scenarios:
        sql = RESULTS_DIR / f'{s}.sqlite'
        if not sql.exists():
            continue
        pivot = gen_production_by_zone_type(sql)
        sub = pivot.loc[pivot.index.intersection(zones), [c for c in types if c in pivot.columns]]
        sub['SUM'] = sub.sum(axis=1)
        sub.loc['NORGE'] = sub.sum(axis=0)
        print(f'\n--- {s} ---')
        print(sub.round(2).to_string())


def net_export(scenarios, branches_csv, dcbranches_csv):
    """Netto eksport = sum av flyt på alle grener som krysser NO-grensen."""
    print(f'\n=== 4. Norsk nettoeksport via alle grenser (TWh/år) ===')
    no_zones = {'NO1', 'NO2', 'NO3', 'NO4', 'NO5'}

    # Identifiser kryss-grenser i CSV-ene
    def zone_of(node_id):
        m = pd.Series([node_id]).str.extract(r'(NO\d|SE\d|FI|DK\d)')[0].iloc[0]
        return m

    ac_cross = branches_csv[
        branches_csv['node_from'].map(zone_of).isin(no_zones) !=
        branches_csv['node_to'].map(zone_of).isin(no_zones)
    ].reset_index().rename(columns={'index': 'csv_idx'})

    dc_cross = dcbranches_csv[
        dcbranches_csv['node_from'].map(zone_of).isin(no_zones) !=
        dcbranches_csv['node_to'].map(zone_of).isin(no_zones)
    ].reset_index().rename(columns={'index': 'csv_idx'})

    print(f'  {len(ac_cross)} AC-kryssgrener, {len(dc_cross)} DC-kryssgrener')

    for s in scenarios:
        sql = RESULTS_DIR / f'{s}.sqlite'
        if not sql.exists():
            continue
        conn = sqlite3.connect(str(sql))
        # AC: indx fra Grid_Branches stemmer med csv_idx (begge er rekkefølge-baserte)
        # men siden Grid_Branches innehar fromIndx, må vi heller bruke Grid_Branches
        # joine med Grid_Nodes og se hvilke som krysser
        nodes_df = pd.read_sql("SELECT indx, id FROM Grid_Nodes", conn)
        id_of = dict(zip(nodes_df['indx'], nodes_df['id']))
        ac_db = pd.read_sql(
            "SELECT b.indx, b.fromIndx, b.toIndx, AVG(r.flow) AS mean_flow "
            "FROM Grid_Branches b JOIN Res_Branches r ON b.indx=r.indx "
            "GROUP BY b.indx", conn)
        ac_db['from_id'] = ac_db['fromIndx'].map(id_of)
        ac_db['to_id'] = ac_db['toIndx'].map(id_of)
        ac_db['from_no'] = ac_db['from_id'].map(zone_of).isin(no_zones)
        ac_db['to_no'] = ac_db['to_id'].map(zone_of).isin(no_zones)
        ac_db['cross'] = ac_db['from_no'] != ac_db['to_no']
        ac_cross_db = ac_db[ac_db['cross']].copy()
        ac_cross_db['export_mw'] = ac_cross_db.apply(
            lambda r: r['mean_flow'] if r['from_no'] else -r['mean_flow'], axis=1)

        # DC: rekkefølge stemmer med dcbranch.csv-indeks i memory etter readGridData
        dc_db = pd.read_sql(
            "SELECT indx, AVG(flow) AS mean_flow FROM Res_DcBranches GROUP BY indx",
            conn)
        conn.close()
        dc_csv = dcbranches_csv.reset_index().rename(columns={'index': 'indx'})
        dc_db = dc_db.merge(dc_csv[['indx', 'node_from', 'node_to']], on='indx')
        dc_db['from_no'] = dc_db['node_from'].map(zone_of).isin(no_zones)
        dc_db['to_no'] = dc_db['node_to'].map(zone_of).isin(no_zones)
        dc_db['cross'] = dc_db['from_no'] != dc_db['to_no']
        dc_cross_db = dc_db[dc_db['cross']].copy()
        dc_cross_db['export_mw'] = dc_cross_db.apply(
            lambda r: r['mean_flow'] if r['from_no'] else -r['mean_flow'], axis=1)

        ac_export = ac_cross_db['export_mw'].sum() * 8760 / 1e6
        dc_export = dc_cross_db['export_mw'].sum() * 8760 / 1e6
        total = ac_export + dc_export
        print(f'  {s:<14} AC {ac_export:+6.2f}  DC {dc_export:+6.2f}  '
              f'TOTAL {total:+6.2f} TWh/år')


def main():
    nodes, branches, dcbranches = load_grid_meta()
    diagnose_no2_1(nodes, branches, dcbranches)
    compare_node_flows(SCENARIOS, 'NO2_1', dcbranches)

    no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
    types = ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'nuclear']
    compare_production(SCENARIOS, no_zones, types)

    net_export(SCENARIOS, branches, dcbranches)


if __name__ == '__main__':
    main()
