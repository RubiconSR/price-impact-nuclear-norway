"""
PowerGAMA-plot for ferdige scenarier.

Begrenset til ÉTT værår (2010 = år 20 i sekvensen 1991-2020) for å
unngå å lese hele 5 GB SQLite-en. Bruker timeMaxMin-parameter på
alle plot.

Bruk:
    python plot_results.py            # alle ferdige scenarier
    python plot_results.py N0_OW0     # ett scenario
"""

import sys
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import powergama

BASE_DIR = pathlib.Path(__file__).parent.parent.parent
SOURCE_DATA = BASE_DIR / 'scenarios' / 'nuclear_MD' / 'data'
RESULTS_DIR = BASE_DIR / 'master_volt_benchmark' / 'results'
PLOTS_DIR = BASE_DIR / 'master_volt_benchmark' / 'plots'

DATE_START = pd.Timestamp('1991-01-01 00:00:00', tz='UTC')
DATE_END = pd.Timestamp('2020-12-31 23:00:00', tz='UTC')

VOLT_DEMAND_TWH = {'NO1': 44.0, 'NO2': 56.0, 'NO3': 40.0, 'NO4': 30.0, 'NO5': 25.0}

# Værår 2010 = år 20 i sekvensen
ONE_YEAR = [19 * 8760, 20 * 8760]


def load_data():
    sysp = SOURCE_DATA / 'system'
    data = powergama.GridData()
    data.readGridData(
        nodes=sysp / 'node.csv',
        ac_branches=sysp / 'branch.csv',
        dc_branches=sysp / 'dcbranch.csv',
        generators=sysp / 'generator.csv',
        consumers=sysp / 'consumer.csv',
    )
    profiles = pd.read_csv(SOURCE_DATA / 'timeseries_profiles.csv',
                           index_col=0, parse_dates=True)
    profiles['const'] = 1
    profiles = profiles[(profiles.index >= DATE_START) & (profiles.index <= DATE_END)]
    data.profiles = profiles.reset_index()
    data.storagevalue_time = data.profiles[['const']]
    data.storagevalue_filling = pd.read_csv(
        SOURCE_DATA / 'storage' / 'profiles_storval_filling.csv'
    )
    data.timerange = list(range(data.profiles.shape[0]))
    data.timeDelta = 1.0
    data.generator = data.generator[data.generator['pmax'] > 0].reset_index(drop=True)

    data.consumer['zone'] = data.consumer['node'].str.extract(
        r'(NO\d|SE\d|FI|DK\d)'
    )[0]
    for zone, twh in VOLT_DEMAND_TWH.items():
        m = data.consumer['zone'] == zone
        cur = data.consumer.loc[m, 'demand_avg'].sum()
        if cur > 0:
            data.consumer.loc[m, 'demand_avg'] *= (twh * 1e6 / 8760) / cur
    data.consumer = data.consumer.drop(columns=['zone'])
    return data


def make_plots(name, data):
    """plotAreaPrice — den eneste PowerGAMA-plotten som er raskt
    nok for 5 GB SQLite-er. Andre plot (plotEnergyMix, plotStoragePerArea)
    leser hele tabellen og henger på 30-årsdata."""
    sql = RESULTS_DIR / f'{name}.sqlite'
    if not sql.exists():
        return

    out = PLOTS_DIR / name
    out.mkdir(parents=True, exist_ok=True)

    res = powergama.Results(data, str(sql), replace=False)
    print(f'\n[{name}] -> {out.relative_to(BASE_DIR)}/')

    try:
        plt.figure(figsize=(14, 4))
        res.plotAreaPrice(areas=['NO'], timeMaxMin=ONE_YEAR, showTitle=False)
        plt.title(f'{name} — nodalpris NO (værår 2010)')
        plt.ylabel('EUR/MWh')
        plt.tight_layout()
        plt.savefig(out / 'areaprice_NO_2010.png', dpi=120)
        plt.close()
        print('  plotAreaPrice ✓')
    except Exception as e:
        print(f'  plotAreaPrice ✗ {e}')


def main():
    if len(sys.argv) > 1:
        scenarios = sys.argv[1:]
    else:
        scenarios = sorted(p.stem for p in RESULTS_DIR.glob('*.sqlite'))

    if not scenarios:
        print('Ingen scenarier funnet')
        return

    data = load_data()
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    for name in scenarios:
        make_plots(name, data)


if __name__ == '__main__':
    main()
