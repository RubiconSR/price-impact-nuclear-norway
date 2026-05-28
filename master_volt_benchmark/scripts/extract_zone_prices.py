"""
Hent ut volumvektet sonepris (Hjelmeland Eq. 5) fra et eksisterende
PowerGAMA SQLite-resultat. Bruker NordicNuclearAnalysis sin
getZonePricesVolumeWeightedFromDB.

Bruk:
    python extract_zone_prices.py N0_OW0
    python extract_zone_prices.py N1_OW0
    python extract_zone_prices.py            # alle ferdige scenarier
"""

import sys
import pathlib
import pandas as pd
import powergama
from powergama.database import Database

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SOURCE_DATA = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data'
RESULTS_DIR = BASE_DIR / 'master_volt_benchmark' / 'results'

# NordicNuclearAnalysis-funksjon
sys.path.insert(0, str(BASE_DIR / 'NordicNuclearAnalysis NY'))
from functions.database_functions import getZonePricesVolumeWeightedFromDB

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']


def load_grid_for_extraction():
    """Last grid-data (samme som run_volt_benchmark.py for konsistente vekter)."""
    sysp = SOURCE_DATA / 'system'
    data = powergama.GridData()
    data.readGridData(
        nodes=sysp / 'node.csv',
        ac_branches=sysp / 'branch.csv',
        dc_branches=sysp / 'dcbranch.csv',
        generators=sysp / 'generator.csv',
        consumers=sysp / 'consumer.csv',
    )
    # Forbruksskalering må samsvare med simuleringen for korrekte vekter
    VOLT = {'NO1': 44.0, 'NO2': 56.0, 'NO3': 40.0, 'NO4': 30.0, 'NO5': 25.0}
    data.consumer['zone'] = data.consumer['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')[0]
    for zone, t in VOLT.items():
        m = data.consumer['zone'] == zone
        cur = data.consumer.loc[m, 'demand_avg'].sum()
        if cur > 0:
            data.consumer.loc[m, 'demand_avg'] *= (t * 1e6 / 8760) / cur
    data.consumer = data.consumer.drop(columns=['zone'])
    return data


def extract(name, data):
    sql_file = RESULTS_DIR / f'{name}.sqlite'
    if not sql_file.exists():
        print(f'  {name}: ikke funnet')
        return None

    db = Database(str(sql_file))
    # Antall timesteps fra Res_Nodes
    import sqlite3
    conn = sqlite3.connect(str(sql_file))
    n_steps = conn.execute("SELECT COUNT(DISTINCT timestep) FROM Res_Nodes").fetchone()[0]
    conn.close()

    zone_prices = getZonePricesVolumeWeightedFromDB(
        data, db, timeMaxMin=[0, n_steps], zones=NO_ZONES
    )
    print(f'\n=== {name} — volumvektet sonepris (EUR/MWh, {n_steps/8766:.1f} år) ===')
    for z in NO_ZONES:
        print(f'  {z}: {zone_prices[z]:.2f}')
    nat_avg = sum(zone_prices.values()) / len(zone_prices)
    print(f'  NO snitt: {nat_avg:.2f}')
    return zone_prices


def main():
    if len(sys.argv) > 1:
        scenarios = sys.argv[1:]
    else:
        scenarios = sorted(p.stem for p in RESULTS_DIR.glob('*.sqlite'))

    if not scenarios:
        print('Ingen scenarier å hente ut')
        return

    data = load_grid_for_extraction()
    results = {}
    for name in scenarios:
        zp = extract(name, data)
        if zp is not None:
            results[name] = zp

    if len(results) > 1:
        print('\n\n=== Sammendrag ===')
        df = pd.DataFrame(results).T
        df['NO_snitt'] = df.mean(axis=1)
        print(df.round(2).to_string())


if __name__ == '__main__':
    main()
