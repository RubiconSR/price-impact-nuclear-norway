"""
Validation of PowerGAMA baseline against historical data.

Part 1: Reservoir filling (NVE API vs PowerGAMA)
Part 2: Power prices (Historical 2024 spot eks mva, EMPS, B&S BM, PowerGAMA R3-R5)
"""

import pathlib
import json
import sqlite3
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import powergama

# ============================================================
# Configuration
# ============================================================
SIM_YEAR_START = 1991
SIM_YEAR_END = 2020
DATE_START = pd.Timestamp(f'{SIM_YEAR_START}-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp(f'{SIM_YEAR_END}-12-31 23:00:00', tz='UTC')

BASE_DIR = pathlib.Path(__file__).parent
SCENARIO_DIR = BASE_DIR / 'scenarios' / 'baseline'
DATA_PATH = SCENARIO_DIR / 'data'
SQL_FILE = SCENARIO_DIR / 'results' / f'powergama_baseline_{SIM_YEAR_START}_{SIM_YEAR_END}.sqlite'
PLOT_DIR = SCENARIO_DIR / 'plots' / 'validation'
PLOT_DIR.mkdir(parents=True, exist_ok=True)

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
ZONE_COLORS = {'NO1': '#1f77b4', 'NO2': '#ff7f0e', 'NO3': '#2ca02c', 'NO4': '#d62728', 'NO5': '#9467bd'}

# Historical reservoir capacities (TWh) - from NVE
HIST_CAPACITY_TWh = {'NO1': 6.00, 'NO2': 34.04, 'NO3': 8.92, 'NO4': 21.08, 'NO5': 17.39}

# PowerGAMA storage capacities (MWh) - from generator.csv
PGAMA_CAPACITY_MWh = {'NO1': 10_760_000, 'NO2': 33_820_000, 'NO3': 8_320_000, 'NO4': 21_060_000, 'NO5': 13_330_000}


# ============================================================
# Part 1: Fetch NVE historical reservoir data
# ============================================================
def fetch_nve_reservoir_data():
    """Fetch weekly reservoir filling from NVE API for 2010-2020."""
    cache_file = PLOT_DIR / 'nve_reservoir_cache.json'

    if cache_file.exists():
        print('  Using cached NVE data...')
        with open(cache_file) as f:
            data = json.load(f)
    else:
        print('  Fetching from NVE API (this may take a moment)...')
        url = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        data = response.json()
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        print(f'  Cached {len(data)} records')

    df = pd.DataFrame(data)

    # Filter: elspot areas (NO1-NO5), years 2010-2020
    mask = (
        (df['omrType'] == 'EL') &
        (df['omrnr'].isin([1, 2, 3, 4, 5])) &
        (df['iso_aar'] >= 2010) &
        (df['iso_aar'] <= 2020)
    )
    df_filtered = df[mask].copy()

    area_map = {1: 'NO1', 2: 'NO2', 3: 'NO3', 4: 'NO4', 5: 'NO5'}
    df_filtered['zone'] = df_filtered['omrnr'].map(area_map)
    df_filtered['filling_pct'] = df_filtered['fyllingsgrad'] * 100  # Convert to %

    return df_filtered


# ============================================================
# Part 1: Extract PowerGAMA simulated reservoir filling
# ============================================================
def load_grid_data():
    """Load grid data (same as run_baseline.py)."""
    system_path = DATA_PATH / 'system'
    data = powergama.GridData()
    data.readGridData(
        nodes=system_path / 'node.csv',
        ac_branches=system_path / 'branch.csv',
        dc_branches=system_path / 'dcbranch.csv',
        generators=system_path / 'generator.csv',
        consumers=system_path / 'consumer.csv',
    )
    profiles = pd.read_csv(DATA_PATH / 'timeseries_profiles.csv', index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    storval = pd.read_csv(DATA_PATH / 'storage' / 'profiles_storval_filling.csv')
    data.storagevalue_filling = storval
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)
    return data


def extract_pgama_storage(data):
    """Extract simulated storage filling from SQLite database per zone."""
    print('  Extracting storage from SQLite...')

    conn = sqlite3.connect(SQL_FILE)

    # Get generator info from Grid_Generators table
    grid_gens = pd.read_sql_query("SELECT indx, node, type FROM Grid_Generators", conn)

    # Get storage capacities from data (generator.csv)
    gen = data.generator.copy()
    gen['zone'] = gen['node'].str.extract(r'(NO\d)')

    # Find Norwegian hydro generators with storage
    no_hydro = gen[(gen['zone'].isin(NO_ZONES)) & (gen['storage_cap'] > 0)]

    # Map generator indices to zones and capacities
    # Res_Storage uses the generator index from Grid_Generators
    zone_gen_indices = {z: [] for z in NO_ZONES}
    zone_capacity = {z: 0.0 for z in NO_ZONES}

    for idx in no_hydro.index:
        zone = no_hydro.loc[idx, 'zone']
        zone_gen_indices[zone].append(idx)
        zone_capacity[zone] += no_hydro.loc[idx, 'storage_cap']

    print(f'  Storage capacities (TWh): { {z: f"{v/1e6:.2f}" for z, v in zone_capacity.items()} }')

    # Build list of all NO hydro gen indices for the SQL query
    all_no_indices = []
    for z in NO_ZONES:
        all_no_indices.extend(zone_gen_indices[z])
    indices_str = ','.join(str(i) for i in all_no_indices)

    # Sample every 168 hours (weekly) to keep query manageable
    num_hours = len(data.timerange)
    week_hours = 168
    sample_times = list(range(0, num_hours, week_hours))
    times_str = ','.join(str(t) for t in sample_times)

    print(f'  Querying {len(sample_times)} weekly samples for {len(all_no_indices)} generators...')

    # Single efficient query
    query = f"""
        SELECT timestep, indx, storage
        FROM Res_Storage
        WHERE indx IN ({indices_str})
        AND timestep IN ({times_str})
    """
    storage_df = pd.read_sql_query(query, conn)
    conn.close()

    print(f'  Got {len(storage_df)} rows')

    # Aggregate per zone per timestep
    timestamps = pd.date_range(start=DATE_START, periods=num_hours, freq='h')

    result = {}
    for zone in NO_ZONES:
        gen_ids = zone_gen_indices[zone]
        cap = zone_capacity[zone]

        zone_data = storage_df[storage_df['indx'].isin(gen_ids)]
        zone_agg = zone_data.groupby('timestep')['storage'].sum().reset_index()
        zone_agg['filling_pct'] = zone_agg['storage'] / cap * 100

        zone_agg['date'] = [timestamps[int(t)] for t in zone_agg['timestep']]
        zone_agg['week'] = zone_agg['date'].dt.isocalendar().week.astype(int)
        zone_agg['year'] = zone_agg['date'].dt.year

        result[zone] = zone_agg
        print(f'  {zone}: avg filling = {zone_agg["filling_pct"].mean():.1f}%')

    return result, zone_capacity


# ============================================================
# Part 1: Create comparison plots
# ============================================================
def plot_reservoir_comparison(nve_data, pgama_data):
    """Plot historical vs simulated seasonal reservoir patterns."""

    # --- Plot 1: Seasonal pattern (weekly average) ---
    fig, axes = plt.subplots(3, 2, figsize=(14, 15))
    axes_flat = axes.flatten()

    for i, zone in enumerate(NO_ZONES):
        ax = axes_flat[i]

        # Historical seasonal pattern
        hist = nve_data[nve_data['zone'] == zone]
        hist_seasonal = hist.groupby('iso_uke')['filling_pct'].agg(['mean', 'min', 'max']).reset_index()

        ax.fill_between(hist_seasonal['iso_uke'], hist_seasonal['min'], hist_seasonal['max'],
                         alpha=0.2, color='blue', label='Historisk min-maks (2010-2020)')
        ax.plot(hist_seasonal['iso_uke'], hist_seasonal['mean'],
                color='blue', linewidth=2, label='Historisk snitt (2010-2020)')

        # Simulated seasonal pattern
        if zone in pgama_data and not pgama_data[zone].empty:
            sim = pgama_data[zone]
            sim_seasonal = sim.groupby('week')['filling_pct'].mean().reset_index()
            ax.plot(sim_seasonal['week'], sim_seasonal['filling_pct'],
                    color='red', linewidth=2, linestyle='--', label='PowerGAMA (1991-2020)')

        ax.set_title(zone, fontsize=14, fontweight='bold')
        ax.set_xlabel('Uke')
        ax.set_ylabel('Fyllingsgrad [%]')
        ax.set_xlim(1, 52)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    # Remove empty subplot
    axes_flat[5].set_visible(False)

    plt.suptitle('Magasinfylling: Historisk (NVE) vs Simulert (PowerGAMA)', fontsize=16, y=1.01)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / 'reservoir_seasonal_comparison.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: reservoir_seasonal_comparison.pdf')

    # --- Plot 2: All zones on one plot ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Historical
    for zone in NO_ZONES:
        hist = nve_data[nve_data['zone'] == zone]
        hist_seasonal = hist.groupby('iso_uke')['filling_pct'].mean()
        ax1.plot(hist_seasonal.index, hist_seasonal.values,
                 color=ZONE_COLORS[zone], linewidth=1.5, label=zone)
    ax1.set_title('Historisk (NVE, 2010-2020)')
    ax1.set_xlabel('Uke')
    ax1.set_ylabel('Fyllingsgrad [%]')
    ax1.set_xlim(1, 52)
    ax1.set_ylim(0, 100)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Simulated
    for zone in NO_ZONES:
        if zone in pgama_data and not pgama_data[zone].empty:
            sim = pgama_data[zone]
            sim_seasonal = sim.groupby('week')['filling_pct'].mean()
            ax2.plot(sim_seasonal.index, sim_seasonal.values,
                     color=ZONE_COLORS[zone], linewidth=1.5, label=zone)
    ax2.set_title('Simulert (PowerGAMA, 1991-2020)')
    ax2.set_xlabel('Uke')
    ax2.set_ylabel('Fyllingsgrad [%]')
    ax2.set_xlim(1, 52)
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.suptitle('Sesongmønster magasinfylling', fontsize=14)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / 'reservoir_seasonal_allzones.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('  Saved: reservoir_seasonal_allzones.pdf')


def print_reservoir_table(nve_data, pgama_data):
    """Print average filling table."""
    print('\n' + '=' * 70)
    print('GJENNOMSNITTLIG FYLLINGSGRAD [%]')
    print('=' * 70)
    print(f'{"Sone":<8} {"Historisk (NVE)":<18} {"PowerGAMA":<15} {"Avvik":<10} {"Kapasitet hist.":<15} {"Kapasitet sim.":<15}')
    print('-' * 80)

    for zone in NO_ZONES:
        hist = nve_data[nve_data['zone'] == zone]['filling_pct'].mean()
        hist_cap = HIST_CAPACITY_TWh.get(zone, 0)
        sim_cap = PGAMA_CAPACITY_MWh.get(zone, 0) / 1e6  # Convert to TWh

        if zone in pgama_data and not pgama_data[zone].empty:
            sim = pgama_data[zone]['filling_pct'].mean()
            diff = sim - hist
            print(f'{zone:<8} {hist:>8.1f}%          {sim:>8.1f}%       {diff:>+6.1f}%    {hist_cap:>8.2f} TWh     {sim_cap:>8.2f} TWh')
        else:
            print(f'{zone:<8} {hist:>8.1f}%          {"N/A":>8s}        {"N/A":>6s}    {hist_cap:>8.2f} TWh     {sim_cap:>8.2f} TWh')


# ============================================================
# Part 2: Price comparison
# ============================================================
def compare_prices():
    """Compare prices: Historical 2024 spot (eks mva), EMPS, B&S BM, PowerGAMA R3/R4/R5."""

    # Historical 2024 annual averages — Nord Pool wholesale spot prices (eks mva)
    # Source: Fortum historiske strømpriser 2024, confirmed by Fornybar Norge
    # Fortum reports consumer prices INKL 25% mva for NO1/NO2/NO3/NO5, eks mva for NO4
    # Original inkl mva: NO1=60.83, NO2=72.74, NO3=40.70, NO4=27.01, NO5=59.34 øre/kWh
    # Corrected eks mva: ÷1.25 for NO1/NO2/NO3/NO5, NO4 unchanged (VAT exempt)
    hist_ore_inkl_mva = {'NO1': 60.83, 'NO2': 72.74, 'NO3': 40.70, 'NO4': 27.01, 'NO5': 59.34}
    hist_ore = {
        'NO1': 60.83 / 1.25,  # 48.66 øre/kWh
        'NO2': 72.74 / 1.25,  # 58.19 øre/kWh
        'NO3': 40.70 / 1.25,  # 32.56 øre/kWh
        'NO4': 27.01,         # 27.01 øre/kWh (NO4 er fritatt for el-mva)
        'NO5': 59.34 / 1.25,  # 47.47 øre/kWh
    }
    EUR_NOK = 11.63  # Norges Bank 2024 annual average
    hist_2024 = {z: v * 10 / EUR_NOK for z, v in hist_ore.items()}
    # NO1=41.8, NO2=50.0, NO3=28.0, NO4=23.2, NO5=40.8 EUR/MWh

    # EMPS (Hjelmeland et al., Figure 10 - baseline, 30 weather years 1991-2020)
    emps_prices = {'NO1': 55, 'NO2': 60, 'NO3': 28, 'NO4': 24, 'NO5': 51}

    # By & Skavlem BM 2024 (approximate, from Figure 6.8a price map, weather year 2020)
    # These are nodal prices from the model, NOT consumer prices — no mva correction needed
    bs_ore = {'NO1': 61, 'NO2': 91, 'NO3': 35, 'NO4': 18, 'NO5': 48}
    bs_prices = {z: v * 10 / EUR_NOK for z, v in bs_ore.items()}

    # PowerGAMA R3 (30 weather years, with 6 manually calibrated northern lines)
    r3_prices = {'NO1': 58.70, 'NO2': 60.81, 'NO3': 39.24, 'NO4': 16.61, 'NO5': 42.58}

    # PowerGAMA R4 (30 weather years, northern lines reverted to BM = EMPS NTC)
    r4_prices = {'NO1': 64.61, 'NO2': 61.70, 'NO3': 62.33, 'NO4': 14.09, 'NO5': 48.76}

    # PowerGAMA R5 (30 weather years, R3 branch config, adjusted storage_price)
    # storage_price: NO1=11.5, NO2=17.0, NO3=9.5, NO4=17.5, NO5=21.0
    r5_prices = {'NO1': 59.67, 'NO2': 61.19, 'NO3': 40.38, 'NO4': 18.22, 'NO5': 45.91}

    # --- Primary comparison: PG 30yr vs EMPS 30yr ---
    print('\n' + '=' * 100)
    print('HOVEDSAMMENLIGNING: PowerGAMA vs EMPS (begge 30 værår 1991-2020) [EUR/MWh]')
    print('=' * 100)
    print(f'{"Sone":<8} {"EMPS":>8} {"PG R3":>8} {"R3-EMPS":>10} {"PG R5":>8} {"R5-EMPS":>10} {"R5-EMPS%":>10}')
    print('-' * 70)

    for zone in NO_ZONES:
        e = emps_prices[zone]
        r3 = r3_prices[zone]
        r5 = r5_prices[zone]
        print(f'{zone:<8} {e:>8.0f} {r3:>8.1f} {r3-e:>+10.1f} {r5:>8.1f} {r5-e:>+10.1f} {(r5-e)/e*100:>+10.1f}%')

    e_avg = np.mean(list(emps_prices.values()))
    r3_avg = np.mean(list(r3_prices.values()))
    r5_avg = np.mean(list(r5_prices.values()))
    print('-' * 70)
    print(f'{"NO snitt":<8} {e_avg:>8.0f} {r3_avg:>8.1f} {r3_avg-e_avg:>+10.1f} {r5_avg:>8.1f} {r5_avg-e_avg:>+10.1f} {(r5_avg-e_avg)/e_avg*100:>+10.1f}%')

    print(f'\nNB: EMPS = Hjelmeland et al. Figure 10, baseline B, 30 værår 1991-2020')
    print(f'    Hist 2024 enkeltår er IKKE sammenlignbart med 30-årssnitt (2024 var vått/billig)')

    # --- Context: 2024 spot prices ---
    print('\n' + '=' * 80)
    print('KONTEKST: Nord Pool spotpriser 2024 (enkeltår, eks 25% mva)')
    print('=' * 80)
    h_avg = np.mean(list(hist_2024.values()))
    print(f'{"Sone":<8} {"Inkl mva":>10} {"Eks mva":>10} {"EUR/MWh":>10}    (EUR/NOK = {EUR_NOK})')
    print('-' * 55)
    for zone in NO_ZONES:
        inkl = hist_ore_inkl_mva[zone]
        eks = hist_ore[zone]
        note = '(fritatt)' if zone == 'NO4' else '(÷1.25)'
        print(f'{zone:<8} {inkl:>8.2f}   {eks:>8.2f}   {hist_2024[zone]:>8.1f}    {note}')
    print('-' * 55)
    print(f'{"NO snitt":<8} {"":>10} {"":>10} {h_avg:>8.1f}')
    print(f'NB: 2024 var et vått år — spotpriser lavere enn 30-årssnitt')

    # --- Calibration history ---
    print('\n' + '=' * 90)
    print('KALIBRERINGSHISTORIKK: storage_price-endringer R3 → R5')
    print('=' * 90)
    sp_r3 = {'NO1': 13.0, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 14.0, 'NO5': 17.0}
    sp_r5 = {'NO1': 11.5, 'NO2': 17.0, 'NO3': 9.5, 'NO4': 17.5, 'NO5': 21.0}
    print(f'{"Sone":<8} {"sp R3":>8} {"sp R5":>8} {"R3":>8} {"R5":>8} {"EMPS":>8} {"R5-EMPS":>10} {"R5-EMPS%":>10}')
    print('-' * 75)
    for zone in NO_ZONES:
        r3 = r3_prices[zone]
        r5 = r5_prices[zone]
        e = emps_prices[zone]
        print(f'{zone:<8} {sp_r3[zone]:>8.1f} {sp_r5[zone]:>8.1f} {r3:>8.1f} {r5:>8.1f} {e:>8.0f} {r5-e:>+10.1f} {(r5-e)/e*100:>+10.1f}%')

    # --- Price ranking analysis ---
    print('\n' + '=' * 70)
    print('PRISREKKEFØLGE-ANALYSE')
    print('=' * 70)

    hist_sorted = sorted(hist_2024.items(), key=lambda x: x[1], reverse=True)
    print(f'Hist 2024 (spot):{" > ".join(f"{z} ({v:.1f})" for z, v in hist_sorted)}')

    emps_sorted = sorted(emps_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'EMPS:            {" > ".join(f"{z} ({v:.1f})" for z, v in emps_sorted)}')

    r3_sorted = sorted(r3_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'PowerGAMA R3:    {" > ".join(f"{z} ({v:.1f})" for z, v in r3_sorted)}')

    r5_sorted = sorted(r5_prices.items(), key=lambda x: x[1], reverse=True)
    print(f'PowerGAMA R5:    {" > ".join(f"{z} ({v:.1f})" for z, v in r5_sorted)}')

    print(f'\nForventet rekkefølge: NO2 > NO1 > NO5 > NO3 > NO4')

    # Spread analysis (EMPS as primary reference)
    print(f'\nPrisspread Sør (NO1/NO2 snitt) vs Nord (NO4):')
    print(f'  EMPS:           {(emps_prices["NO1"] + emps_prices["NO2"]) / 2 - emps_prices["NO4"]:.1f} EUR/MWh')
    print(f'  PowerGAMA R3:   {(r3_prices["NO1"] + r3_prices["NO2"]) / 2 - r3_prices["NO4"]:.1f} EUR/MWh')
    print(f'  PowerGAMA R5:   {(r5_prices["NO1"] + r5_prices["NO2"]) / 2 - r5_prices["NO4"]:.1f} EUR/MWh')

    print(f'\nPrisspread NO3 vs NO1:')
    print(f'  EMPS:           {emps_prices["NO3"] - emps_prices["NO1"]:.1f} EUR/MWh (NO3 {"dyrere" if emps_prices["NO3"] > emps_prices["NO1"] else "billigere"})')
    print(f'  PowerGAMA R3:   {r3_prices["NO3"] - r3_prices["NO1"]:.1f} EUR/MWh (NO3 {"dyrere" if r3_prices["NO3"] > r3_prices["NO1"] else "billigere"})')
    print(f'  PowerGAMA R5:   {r5_prices["NO3"] - r5_prices["NO1"]:.1f} EUR/MWh (NO3 {"dyrere" if r5_prices["NO3"] > r5_prices["NO1"] else "billigere"})')

    # --- Plot: 3-bar comparison (EMPS, R3, R5) — 30yr vs 30yr ---
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(NO_ZONES))
    width = 0.25

    bars1 = ax.bar(x - width, [emps_prices[z] for z in NO_ZONES], width,
                    label='EMPS (Hjelmeland, 30 værår)', color='mediumseagreen')
    bars2 = ax.bar(x, [r3_prices[z] for z in NO_ZONES], width,
                    label='PowerGAMA R3 (30 værår)', color='coral')
    bars3 = ax.bar(x + width, [r5_prices[z] for z in NO_ZONES], width,
                    label='PowerGAMA R5 (30 værår)', color='mediumpurple')

    ax.set_ylabel('Pris [EUR/MWh]')
    ax.set_title('Sonepriser 30-årssnitt: EMPS vs PowerGAMA R3 & R5')
    ax.set_xticks(x)
    ax.set_xticklabels(NO_ZONES)
    ax.legend(fontsize=9, loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.0f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(PLOT_DIR / 'price_comparison_pg_vs_emps.pdf', bbox_inches='tight', dpi=150)
    plt.close()
    print('\n  Saved: price_comparison_pg_vs_emps.pdf')

    return hist_2024, emps_prices, bs_prices, r3_prices, r5_prices


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print('=' * 70)
    print('VALIDERING AV POWERGAMA BASELINE MOT HISTORISKE DATA')
    print('=' * 70)

    # --- Part 1: Reservoir filling ---
    print('\n--- DEL 1: MAGASINFYLLING ---')
    print('Henter historisk data fra NVE...')
    nve_data = fetch_nve_reservoir_data()
    print(f'  NVE data: {len(nve_data)} records ({nve_data["iso_aar"].min()}-{nve_data["iso_aar"].max()})')

    print('\nLaster PowerGAMA grid data...')
    data = load_grid_data()

    print('\nHenter simulert magasinfylling fra SQLite...')
    pgama_data, zone_caps = extract_pgama_storage(data)

    print('\nLager sammenligningsplott...')
    plot_reservoir_comparison(nve_data, pgama_data)
    print_reservoir_table(nve_data, pgama_data)

    # --- Part 2: Power prices ---
    print('\n\n--- DEL 2: KRAFTPRISER (2024-SYSTEMET) ---')
    compare_prices()

    print(f'\nAlle plott lagret i: {PLOT_DIR}')
    print('Ferdig!')
