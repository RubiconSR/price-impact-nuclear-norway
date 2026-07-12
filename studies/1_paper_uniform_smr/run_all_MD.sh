#!/bin/bash
# Run all 4 MD nuclear scenarios sequentially
cd "/Users/siva/Downloads/MT/Nuclear Power Norway Price"
source venv/bin/activate

echo "=== Starting all MD scenarios at $(date) ==="

for scenario in BL_MD SMR1_MD SMR3_MD SMR6_MD; do
    echo ""
    echo "=========================================="
    echo "Starting $scenario at $(date)"
    echo "=========================================="
    python run_nuclear_MD.py $scenario 2>&1 | tee "run_${scenario}.log"
    echo "$scenario completed at $(date)"
done

echo ""
echo "=== All scenarios complete at $(date) ==="

# Run final summary
python -c "
import sqlite3, numpy as np, pandas as pd

results_dir = 'scenarios/nuclear_MD/results'
scenarios = ['BL_MD', 'SMR1_MD', 'SMR3_MD', 'SMR6_MD']
no_zones = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']

all_prices = {}
all_gen = {}

for sc in scenarios:
    path = f'{results_dir}/powergama_{sc}.sqlite'
    try:
        conn = sqlite3.connect(path)
        nodes = pd.read_sql_query('SELECT indx, id FROM Grid_Nodes', conn)
        prices = pd.read_sql_query('SELECT timestep, indx, nodalprice FROM Res_Nodes', conn)
        generators = pd.read_sql_query('SELECT indx, node, type FROM Grid_Generators', conn)
        gen_out = pd.read_sql_query('SELECT timestep, indx, output FROM Res_Generators', conn)
        conn.close()

        prices = prices.merge(nodes, on='indx')
        prices['zone'] = prices['id'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
        zp = {}
        for z in no_zones:
            zp[z] = prices[prices['zone']==z].groupby('timestep')['nodalprice'].mean().mean()
        all_prices[sc] = zp

        gen_out = gen_out.merge(generators, on='indx')
        gen_out['country'] = gen_out['node'].str.extract(r'(NO|SE|FI|DK)')
        no = gen_out[gen_out['country']=='NO']
        all_gen[sc] = no.groupby('type')['output'].sum() / 1e6
    except Exception as e:
        print(f'Error with {sc}: {e}')

num_years = 30.0

print()
print('=' * 90)
print('FINAL SUMMARY — MD NUCLEAR SCENARIOS (30-year average)')
print('=' * 90)

# Prices
print()
print('ZONE PRICES [EUR/MWh]:')
header = f\"{'Zone':<8}\"
for sc in scenarios:
    header += f' {sc:>12}'
header += '  BL→SMR6 Δ'
print(header)
print('-' * (8 + 13*len(scenarios) + 12))
for z in no_zones:
    row = f'{z:<8}'
    for sc in scenarios:
        row += f' {all_prices[sc][z]:>12.2f}'
    delta = all_prices['SMR6_MD'][z] - all_prices['BL_MD'][z]
    pct = delta / all_prices['BL_MD'][z] * 100
    row += f'  {delta:>+.1f} ({pct:>+.0f}%)'
    print(row)

# Generation mix
print()
print('ANNUAL GENERATION MIX [TWh/yr]:')
types_order = ['hydro','ror','wind_on','wind_off','solar','nuclear','fossil_gas','biomass']
header = f\"{'Type':<15}\"
for sc in scenarios:
    header += f' {sc:>12}'
print(header)
print('-' * (15 + 13*len(scenarios)))
for t in types_order:
    row = f'{t:<15}'
    for sc in scenarios:
        v = all_gen[sc].get(t, 0) / num_years
        row += f' {v:>12.2f}'
    print(row)
print('-' * (15 + 13*len(scenarios)))
row = f\"{'TOTAL':<15}\"
for sc in scenarios:
    v = all_gen[sc].sum() / num_years
    row += f' {v:>12.2f}'
print(row)

print()
print('Done.')
" 2>&1 | tee run_MD_summary.log
