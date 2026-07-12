"""
Generate PowerGAMA figures for the thesis from the finished SQLite results.

Produces, per study group:
  1. Zone-price grouped bar charts (NO1-NO5) vs nuclear scale  [headline]
  2. System maps coloured by average nodal price (price geography)
  3. plotAreaPrice time series (PowerGAMA-native) for one weather year
  4. Reservoir filling over 30 years (hydraulic substitution)

Zone prices are volume-weighted (Hjelmeland Eq. 5) via the
NordicNuclearAnalysis getZonePricesVolumeWeightedFromDB function and are
cached to thesis/figures/_zone_prices_cache.csv so re-runs are instant.

Usage:
    python studies/generate_thesis_figures.py            # everything
    python studies/generate_thesis_figures.py zonebars   # one section
    python studies/generate_thesis_figures.py maps timeseries
"""

import sys
import pathlib
import sqlite3
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import powergama
from powergama.database import Database

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'NordicNuclearAnalysis NY'))
from functions.database_functions import getZonePricesVolumeWeightedFromDB

OUT = BASE / 'thesis' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / '_zone_prices_cache.csv'

NO_ZONES = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
ONE_YEAR = [19 * 8760, 20 * 8760]          # weather year 2010 (year 20 of 30)
VOLT_DEMAND = {'NO1': 44., 'NO2': 56., 'NO3': 40., 'NO4': 30., 'NO5': 25.}

MD_DATA = BASE / 'scenarios' / 'nuclear_MD' / 'data'
IC_DATA = BASE / 'scenarios' / 'nuclear_IC' / 'data'


def sqlpath(*parts):
    return BASE.joinpath(*parts)


# (group, scenario, sqlite-path, label, data_dir, demand_override)
STUDIES = {
    'MD': dict(data=MD_DATA, demand=None, title='2050 Moderate Demand (208 TWh)', scen=[
        ('BL_MD',   sqlpath('scenarios', 'nuclear_MD', 'BL_MD', 'results', 'powergama_BL_MD.sqlite'),     'Baseline'),
        ('SMR1_MD', sqlpath('scenarios', 'nuclear_MD', 'SMR1_MD', 'results', 'powergama_SMR1_MD.sqlite'), '1.5 GW SMR'),
        ('SMR3_MD', sqlpath('scenarios', 'nuclear_MD', 'SMR3_MD', 'results', 'powergama_SMR3_MD.sqlite'), '4.5 GW SMR'),
        ('SMR6_MD', sqlpath('scenarios', 'nuclear_MD', 'SMR6_MD', 'results', 'powergama_SMR6_MD.sqlite'), '9.0 GW SMR'),
    ]),
    'IC': dict(data=IC_DATA, demand=None, title='2050 Increased Consumption (230 TWh)', scen=[
        ('BL_IC',   sqlpath('scenarios', 'nuclear_IC', 'BL_IC', 'results', 'powergama_BL_IC.sqlite'),     'Baseline'),
        ('SMR1_IC', sqlpath('scenarios', 'nuclear_IC', 'SMR1_IC', 'results', 'powergama_SMR1_IC.sqlite'), '1.5 GW SMR'),
        ('SMR3_IC', sqlpath('scenarios', 'nuclear_IC', 'SMR3_IC', 'results', 'powergama_SMR3_IC.sqlite'), '4.5 GW SMR'),
        ('SMR6_IC', sqlpath('scenarios', 'nuclear_IC', 'SMR6_IC', 'results', 'powergama_SMR6_IC.sqlite'), '9.0 GW SMR'),
    ]),
    'NTC': dict(data=MD_DATA, demand=None, title='2050 NTC Border Placement', scen=[
        ('BL_MD',       sqlpath('scenarios', 'nuclear_MD', 'BL_MD', 'results', 'powergama_BL_MD.sqlite'),             'Baseline MD'),
        ('SMR_NTC_MD',  sqlpath('scenarios', 'nuclear_MD', 'SMR_NTC_MD', 'results', 'powergama_SMR_NTC_MD.sqlite'),   '9.3 GW @ cables (MD)'),
        ('SMR_NTC_IC',  sqlpath('scenarios', 'nuclear_IC', 'SMR_NTC_IC', 'results', 'powergama_SMR_NTC_IC.sqlite'),   '9.3 GW @ cables (IC)'),
    ]),
    'VOLT': dict(data=MD_DATA, demand=VOLT_DEMAND, title='2040 Volt Benchmark', scen=[
        ('N0_OW0',      sqlpath('studies', '3_volt_benchmark', 'results', 'N0_OW0.sqlite'),      'V0 baseline'),
        ('N0_OW1',      sqlpath('studies', '3_volt_benchmark', 'results', 'N0_OW1.sqlite'),      '2 GW OW (S1)'),
        ('N0_OW2',      sqlpath('studies', '3_volt_benchmark', 'results', 'N0_OW2.sqlite'),      '4 GW OW (S2)'),
        ('N1_OW0',      sqlpath('studies', '3_volt_benchmark', 'results', 'N1_OW0.sqlite'),      '2.1 GW SMR @ NO2'),
        ('N2_OW0',      sqlpath('studies', '3_volt_benchmark', 'results', 'N2_OW0.sqlite'),      '3.9 GW SMR @ NO2'),
        ('N1jevnt_OW0', sqlpath('studies', '3_volt_benchmark', 'results', 'N1jevnt_OW0.sqlite'), '2.1 GW SMR (uniform)'),
    ]),
}

_grid_cache = {}


def load_grid(data_dir, demand=None):
    key = (str(data_dir), tuple(sorted((demand or {}).items())))
    if key in _grid_cache:
        return _grid_cache[key]
    sysp = data_dir / 'system'
    d = powergama.GridData()
    d.readGridData(nodes=sysp / 'node.csv', ac_branches=sysp / 'branch.csv',
                   dc_branches=sysp / 'dcbranch.csv', generators=sysp / 'generator.csv',
                   consumers=sysp / 'consumer.csv')
    prof = pd.read_csv(data_dir / 'timeseries_profiles.csv', index_col=0, parse_dates=True)
    prof['const'] = 1
    d.profiles = prof.reset_index()
    d.storagevalue_time = d.profiles[['const']]
    d.storagevalue_filling = pd.read_csv(data_dir / 'storage' / 'profiles_storval_filling.csv')
    d.timerange = list(range(d.profiles.shape[0]))
    d.timeDelta = 1.0
    d.generator = d.generator[d.generator['pmax'] > 0].reset_index(drop=True)
    if demand:
        d.consumer['zone'] = d.consumer['node'].str.extract(r'(NO\d|SE\d|FI|DK\d)')[0]
        for z, t in demand.items():
            m = d.consumer['zone'] == z
            cur = d.consumer.loc[m, 'demand_avg'].sum()
            if cur > 0:
                d.consumer.loc[m, 'demand_avg'] *= (t * 1e6 / 8760) / cur
        d.consumer = d.consumer.drop(columns=['zone'])
    _grid_cache[key] = d
    return d


def nsteps(sql):
    c = sqlite3.connect(str(sql))
    n = c.execute("SELECT COUNT(DISTINCT timestep) FROM Res_Nodes").fetchone()[0]
    c.close()
    return n


# ----------------------------------------------------------------------
# Zone prices (cached)
# ----------------------------------------------------------------------
def get_zone_prices():
    if CACHE.exists():
        df = pd.read_csv(CACHE, index_col=0)
        cached = set(df.index)
    else:
        df = pd.DataFrame(columns=NO_ZONES)
        cached = set()

    for g, cfg in STUDIES.items():
        data = None
        for name, sql, _ in cfg['scen']:
            tag = f'{g}:{name}'
            if tag in cached or not sql.exists():
                continue
            if data is None:
                data = load_grid(cfg['data'], cfg['demand'])
            t = time.time()
            db = Database(str(sql))
            zp = getZonePricesVolumeWeightedFromDB(data, db, timeMaxMin=[0, nsteps(sql)], zones=NO_ZONES)
            df.loc[tag] = [zp[z] for z in NO_ZONES]
            print(f'  zone prices {tag}: {time.time()-t:.0f}s  '
                  f'NO-avg {np.mean([zp[z] for z in NO_ZONES]):.1f} EUR/MWh')
            df.to_csv(CACHE)
    return df


# ----------------------------------------------------------------------
# 1. Zone-price grouped bars
# ----------------------------------------------------------------------
def fig_zonebars():
    zp = get_zone_prices()
    for g, cfg in STUDIES.items():
        rows = [(name, lbl) for name, _, lbl in cfg['scen'] if f'{g}:{name}' in zp.index]
        if len(rows) < 2:
            continue
        x = np.arange(len(NO_ZONES))
        w = 0.8 / len(rows)
        colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(rows)))
        plt.figure(figsize=(10, 5))
        for i, (name, lbl) in enumerate(rows):
            vals = zp.loc[f'{g}:{name}', NO_ZONES].values.astype(float)
            navg = np.mean(vals)
            plt.bar(x + i * w - 0.4 + w / 2, vals, w, label=f'{lbl} (NO {navg:.0f})', color=colors[i])
        plt.xticks(x, NO_ZONES)
        plt.ylabel('Volume-weighted price [EUR/MWh]')
        plt.title(f'Zonal electricity prices — {cfg["title"]}')
        plt.legend(fontsize=8)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        for ext in ('png', 'pdf'):
            plt.savefig(OUT / f'zone_prices_{g}.{ext}', dpi=150, bbox_inches='tight')
        plt.close()
        print(f'  wrote zone_prices_{g}.png/pdf')


# ----------------------------------------------------------------------
# 2. System map coloured by average nodal price
# ----------------------------------------------------------------------
def fig_maps():
    targets = [('MD', 'BL_MD', 'Baseline'), ('MD', 'SMR6_MD', '9.0 GW SMR'),
               ('IC', 'BL_IC', 'Baseline'), ('IC', 'SMR6_IC', '9.0 GW SMR')]
    # common colour scale
    vmin, vmax = 0, 120
    for g, name, lbl in targets:
        cfg = STUDIES[g]
        sql = dict((s[0], s[1]) for s in cfg['scen']).get(name)
        if sql is None or not sql.exists():
            continue
        data = load_grid(cfg['data'], cfg['demand'])
        res = powergama.Results(data, str(sql), replace=False)
        try:
            prices = res.getAverageNodalPrices(timeMaxMin=ONE_YEAR)
        except Exception as e:
            print(f'  map {g}:{name} nodal prices failed: {e}')
            continue
        lat = data.node.lat.values.astype(float)
        lon = data.node.lon.values.astype(float)
        p = np.array([prices[i] if prices[i] is not None else np.nan for i in range(len(lat))])
        plt.figure(figsize=(6.5, 8))
        # DC + AC branches as faint lines
        for br, col in ((data.branch, '#bbbbbb'), (data.dcbranch, '#88aacc')):
            try:
                for _, row in br.iterrows():
                    n_from = data.node.index[data.node.id == row['node_from']].tolist()
                    n_to = data.node.index[data.node.id == row['node_to']].tolist()
                    if n_from and n_to:
                        a, b = n_from[0], n_to[0]
                        plt.plot([lon[a], lon[b]], [lat[a], lat[b]], color=col, lw=0.5, zorder=1)
            except Exception:
                pass
        sc = plt.scatter(lon, lat, c=p, cmap='RdYlGn_r', vmin=vmin, vmax=vmax,
                         s=28, edgecolor='k', linewidth=0.3, zorder=3)
        plt.colorbar(sc, label='Avg nodal price [EUR/MWh]', shrink=0.6)
        plt.title(f'{cfg["title"]}\n{lbl} — nodal price geography (2010)')
        plt.xlabel('Longitude'); plt.ylabel('Latitude')
        plt.tight_layout()
        for ext in ('png', 'pdf'):
            plt.savefig(OUT / f'map_{g}_{name}.{ext}', dpi=150, bbox_inches='tight')
        plt.close()
        print(f'  wrote map_{g}_{name}.png/pdf')


# ----------------------------------------------------------------------
# 3. plotAreaPrice time series (PowerGAMA-native)
# ----------------------------------------------------------------------
def fig_timeseries():
    targets = [('MD', 'BL_MD'), ('MD', 'SMR6_MD'), ('IC', 'BL_IC'), ('IC', 'SMR6_IC'),
               ('VOLT', 'N0_OW0'), ('VOLT', 'N2_OW0')]
    for g, name in targets:
        cfg = STUDIES[g]
        sql = dict((s[0], s[1]) for s in cfg['scen']).get(name)
        lbl = dict((s[0], s[2]) for s in cfg['scen']).get(name, name)
        if sql is None or not sql.exists():
            continue
        data = load_grid(cfg['data'], cfg['demand'])
        res = powergama.Results(data, str(sql), replace=False)
        try:
            plt.figure(figsize=(13, 4))
            res.plotAreaPrice(areas=['NO'], timeMaxMin=ONE_YEAR, showTitle=False)
            plt.title(f'{cfg["title"]} — {lbl}: Norwegian price (weather year 2010)')
            plt.ylabel('EUR/MWh')
            # replace raw timestep ticks with month labels for readability
            ax = plt.gca()
            month_starts = [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016]
            month_lbls = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            ax.set_xticks([ONE_YEAR[0] + m for m in month_starts])
            ax.set_xticklabels(month_lbls)
            ax.set_xlabel('Month (weather year 2010)')
            ax.set_xlim(ONE_YEAR[0], ONE_YEAR[1])
            plt.tight_layout()
            for ext in ('png', 'pdf'):
                plt.savefig(OUT / f'areaprice_{g}_{name}.{ext}', dpi=130, bbox_inches='tight')
            plt.close()
            print(f'  wrote areaprice_{g}_{name}.png/pdf')
        except Exception as e:
            print(f'  areaprice {g}:{name} failed: {e}')


# ----------------------------------------------------------------------
# 4. Reservoir filling over 30 years
# ----------------------------------------------------------------------
def fig_reservoir():
    targets = [('MD', 'BL_MD', 'Baseline'), ('MD', 'SMR6_MD', '9.0 GW SMR')]
    plt.figure(figsize=(13, 4.5))
    ok = False
    for g, name, lbl in targets:
        cfg = STUDIES[g]
        sql = dict((s[0], s[1]) for s in cfg['scen']).get(name)
        if sql is None or not sql.exists():
            continue
        data = load_grid(cfg['data'], cfg['demand'])
        res = powergama.Results(data, str(sql), replace=False)
        try:
            fill = res.getStorageFillingInAreas(areas=['NO'], generator_type='hydro')
            plt.plot(fill, label=lbl, lw=0.8)
            ok = True
        except Exception as e:
            print(f'  reservoir {g}:{name} failed: {e}')
    if ok:
        plt.ylabel('Relative reservoir filling [-]')
        plt.xlabel('Hour (1991-2020)')
        plt.title('Norwegian hydro reservoir filling — baseline vs 9 GW SMR (MD)')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        for ext in ('png', 'pdf'):
            plt.savefig(OUT / f'reservoir_filling_MD.{ext}', dpi=130, bbox_inches='tight')
        print('  wrote reservoir_filling_MD.png/pdf')
    plt.close()


SECTIONS = {'zonebars': fig_zonebars, 'maps': fig_maps,
            'timeseries': fig_timeseries, 'reservoir': fig_reservoir}


def main():
    want = sys.argv[1:] or list(SECTIONS)
    for s in want:
        if s not in SECTIONS:
            print(f'unknown section: {s} (have {list(SECTIONS)})')
            continue
        print(f'\n=== {s} ===')
        t = time.time()
        SECTIONS[s]()
        print(f'  [{s} done in {time.time()-t:.0f}s]')
    print(f'\nFigures in {OUT.relative_to(BASE)}/')


if __name__ == '__main__':
    main()
