"""
Setup 2050 Medium Demand (MD) system data for nuclear scenarios.

Scales baseline system to NVE B2050 targets:
  Hydro (incl RoR): 42.6 GW
  Wind onshore:      8.2 GW
  Wind offshore:     3.6 GW  (added at NO2 + NO5 using Sønnavind/Vestavind profiles)
  Solar:            11.3 GW
  Demand:          208 TWh (proportional scaling across NO1-NO5)

Uses R3 calibrated storage_price values.
"""

import pandas as pd
import numpy as np
import pathlib

BASE_DIR = pathlib.Path(__file__).parent
BASELINE_SYS = BASE_DIR / 'scenarios' / 'baseline' / 'data' / 'system'
MD_SYS = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data' / 'system'

# ============================================================
# Targets
# ============================================================
TARGET_HYDRO_GW = 42.6  # hydro + ror combined
TARGET_WINDON_GW = 8.2
TARGET_WINDOFF_GW = 3.6
TARGET_SOLAR_GW = 11.3
TARGET_DEMAND_TWH = 208.0

# R3 calibrated storage prices
R3_SP = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}

# ============================================================
# Load baseline
# ============================================================
gen = pd.read_csv(BASELINE_SYS / 'generator.csv')
con = pd.read_csv(BASELINE_SYS / 'consumer.csv')

gen['zone'] = gen['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
gen['country'] = gen['node'].str.extract(r'(NO|SE|FI|DK)')

# ============================================================
# Scale Norwegian generators to 2050 targets
# ============================================================
no_mask = gen['country'] == 'NO'

# Current Norwegian capacity
cur_hydro = gen.loc[no_mask & (gen['type'] == 'hydro'), 'pmax'].sum()
cur_ror = gen.loc[no_mask & (gen['type'] == 'ror'), 'pmax'].sum()
cur_hydro_total = cur_hydro + cur_ror
cur_windon = gen.loc[no_mask & (gen['type'] == 'wind_on'), 'pmax'].sum()
cur_windoff = gen.loc[no_mask & (gen['type'] == 'wind_off'), 'pmax'].sum()
cur_solar = gen.loc[no_mask & (gen['type'] == 'solar'), 'pmax'].sum()

print('=== Current Norwegian capacity (MW) ===')
print(f'  Hydro (regulated): {cur_hydro:.1f}')
print(f'  RoR:               {cur_ror:.1f}')
print(f'  Hydro+RoR total:   {cur_hydro_total:.1f}')
print(f'  Wind onshore:      {cur_windon:.1f}')
print(f'  Wind offshore:     {cur_windoff:.1f}')
print(f'  Solar:             {cur_solar:.1f}')

# Scale factors
sf_hydro = (TARGET_HYDRO_GW * 1000) / cur_hydro_total
sf_windon = (TARGET_WINDON_GW * 1000) / cur_windon
sf_solar = (TARGET_SOLAR_GW * 1000) / cur_solar

print(f'\n=== Scale factors ===')
print(f'  Hydro+RoR: {sf_hydro:.4f} ({cur_hydro_total:.0f} → {TARGET_HYDRO_GW*1000:.0f} MW)')
print(f'  Wind on:   {sf_windon:.4f} ({cur_windon:.0f} → {TARGET_WINDON_GW*1000:.0f} MW)')
print(f'  Solar:     {sf_solar:.4f} ({cur_solar:.0f} → {TARGET_SOLAR_GW*1000:.0f} MW)')

# Apply scaling to pmax
for idx in gen.index:
    if gen.loc[idx, 'country'] != 'NO':
        continue
    t = gen.loc[idx, 'type']
    if t == 'hydro':
        gen.loc[idx, 'pmax'] *= sf_hydro
        gen.loc[idx, 'storage_cap'] *= sf_hydro  # scale reservoir proportionally
    elif t == 'ror':
        gen.loc[idx, 'pmax'] *= sf_hydro
    elif t == 'wind_on':
        gen.loc[idx, 'pmax'] *= sf_windon
    elif t == 'solar':
        gen.loc[idx, 'pmax'] *= sf_solar

# ============================================================
# Add offshore wind (3.6 GW) at NO2 and NO5
# ============================================================
# Distribution: 2.0 GW at NO2_1, 1.6 GW at NO5_1
# Profiles: Sønnavind A (southern coast → NO2), Vestavind A (western coast → NO5)
# Remove existing tiny Norwegian wind_off (6 MW) — will be replaced
gen = gen[~(no_mask & (gen['type'] == 'wind_off'))].copy()

# Add new offshore wind generators
windoff_template = {
    'desc': '', 'pmin': 0.0, 'fuelcost': 0.015, 'inflow_fac': 0.8,
    'storage_cap': 0.0, 'storage_price': 1.0, 'storval_filling_ref': 'const',
    'storval_time_ref': 'const', 'storage_ini': 0.6, 'pump_cap': 0.0,
    'pump_efficiency': 0.0, 'pump_deadband': 0.0, 'gen_lat': np.nan,
    'gen_lon': np.nan, 'year': np.nan, 'status': 'created', 'source': 'MD_2050',
}

new_windoff = []
# NO2: 2000 MW at NO2_1 using Sønnavind A
row = windoff_template.copy()
row.update({
    'Kolonne1': gen['Kolonne1'].max() + 1,
    'node': 'NO2_1', 'desc': 'NO2_1 wind_off MD2050',
    'type': 'wind_off', 'pmax': 2000.0,
    'inflow_ref': 'windoff_Sønnavind A',
    'zone': 'NO2', 'country': 'NO',
})
new_windoff.append(row)

# NO5: 1600 MW at NO5_1 using Vestavind A
row = windoff_template.copy()
row.update({
    'Kolonne1': gen['Kolonne1'].max() + 2,
    'node': 'NO5_1', 'desc': 'NO5_1 wind_off MD2050',
    'type': 'wind_off', 'pmax': 1600.0,
    'inflow_ref': 'windoff_Vestavind A',
    'zone': 'NO5', 'country': 'NO',
})
new_windoff.append(row)

gen = pd.concat([gen, pd.DataFrame(new_windoff)], ignore_index=True)

# ============================================================
# Override storage_price to R3 values
# ============================================================
for zone, sp in R3_SP.items():
    mask = gen['node'].str.startswith(zone) & (gen['type'] == 'hydro')
    gen.loc[mask, 'storage_price'] = sp

# ============================================================
# Verify final Norwegian capacity
# ============================================================
gen_no = gen[gen['country'] == 'NO']
print(f'\n=== 2050 MD Norwegian capacity (MW) ===')
for t in ['hydro', 'ror', 'wind_on', 'wind_off', 'solar', 'fossil_gas', 'biomass']:
    cap = gen_no.loc[gen_no['type'] == t, 'pmax'].sum()
    print(f'  {t:<15} {cap:>10.1f} MW  ({cap/1000:.2f} GW)')
total = gen_no['pmax'].sum()
print(f'  {"TOTAL":<15} {total:>10.1f} MW  ({total/1000:.2f} GW)')

# ============================================================
# Scale demand to 208 TWh
# ============================================================
con['zone'] = con['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')
con['country'] = con['node'].str.extract(r'(NO|SE|FI|DK)')

cur_demand_avg = con.loc[con['country'] == 'NO', 'demand_avg'].sum()
cur_demand_twh = cur_demand_avg * 8760 / 1e6
sf_demand = TARGET_DEMAND_TWH / cur_demand_twh

print(f'\n=== Demand scaling ===')
print(f'  Current: {cur_demand_avg:.1f} MW avg → {cur_demand_twh:.2f} TWh/yr')
print(f'  Target:  {TARGET_DEMAND_TWH:.0f} TWh/yr')
print(f'  Scale:   {sf_demand:.4f}')

con.loc[con['country'] == 'NO', 'demand_avg'] *= sf_demand

# Verify per zone
print(f'\n=== 2050 MD demand per zone ===')
for zone in ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']:
    zd = con.loc[con['zone'] == zone, 'demand_avg'].sum()
    print(f'  {zone}: {zd:.1f} MW avg → {zd*8760/1e6:.2f} TWh/yr')
total_d = con.loc[con['country'] == 'NO', 'demand_avg'].sum()
print(f'  Total: {total_d:.1f} MW avg → {total_d*8760/1e6:.2f} TWh/yr')

# ============================================================
# Save
# ============================================================
# Drop helper columns before saving
gen_save = gen.drop(columns=['zone', 'country'], errors='ignore')
con_save = con.drop(columns=['zone', 'country'], errors='ignore')

gen_save.to_csv(MD_SYS / 'generator.csv', index=False)
con_save.to_csv(MD_SYS / 'consumer.csv', index=False)

print(f'\nSaved: {MD_SYS / "generator.csv"}')
print(f'Saved: {MD_SYS / "consumer.csv"}')
print('\nSetup complete.')
