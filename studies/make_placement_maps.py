"""
Chapter 7 placement maps (design illustrations, not result figures):
  - case2_placement.pdf : Case 2 cable-endpoint SMR placement (7 nodes, 9.3 GW)
  - case3_placement.pdf : Case 3 Volt 2040 scenario placement (2 panels)

Node coordinates are read from the grid dataset node.csv (verified to exist
before plotting). The Norway base map uses the project's own price-zone
polygons (power-market-app/mapMaking/geo/NO_1..NO_5.geojson). Clean matplotlib
in the thesis's visual language (light-blue zones, no lat/lon axes).
"""
import csv
import pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import geopandas as gpd

BASE = pathlib.Path(__file__).resolve().parents[1]
NODE_CSV = BASE / 'scenarios' / 'nuclear_MD' / 'data' / 'system' / 'node.csv'
GEO = BASE / 'NordicNuclearAnalysis NY' / 'power-market-app' / 'mapMaking' / 'geo'
OUT = BASE / 'overleaf' / 'pictures' / 'results'
OUT.mkdir(parents=True, exist_ok=True)

ZONE_FC = '#d6e4f0'      # light-blue zone fill
ZONE_EC = '#8ba9cc'      # zone border
SMR_C = '#2e7d4f'        # SMR (nuclear) green
OW_C = '#1f6fb2'         # offshore wind blue
ASPECT = 1.0 / np.cos(np.radians(64.5))   # lat correction for Norway

with open(NODE_CSV, encoding='utf-8-sig') as f:
    NODES = {r['id']: (float(r['lon']), float(r['lat'])) for r in csv.DictReader(f)}


def need(ids):
    missing = [n for n in ids if n not in NODES]
    if missing:
        raise SystemExit(f'Missing nodes in node.csv: {missing}')


def norway_base(ax):
    for i in range(1, 6):
        gpd.read_file(GEO / f'NO_{i}.geojson').plot(
            ax=ax, facecolor=ZONE_FC, edgecolor=ZONE_EC, linewidth=0.5, zorder=1)
    ax.set_aspect(ASPECT)
    ax.set_axis_off()


# ============================================================
# Figure 1 - Case 2: cable-endpoint placement
# ============================================================
CASE2 = [  # (node, MW, interconnector label)
    ('NO1_5', 1800, 'SE3 cables'),
    ('NO2_1', 1500, 'North Sea Link'),
    ('NO2_4', 2100, 'NorNed + NordLink'),
    ('NO2_5', 1500, 'Skagerrak'),
    ('NO3_1',  900, 'SE2_4'),
    ('NO4_1', 1200, 'SE1_1 + FI_1'),
    ('NO4_3',  300, 'SE2_1'),
]
CASE2_OFF = {'NO1_5': (14, -2), 'NO2_1': (-12, 12), 'NO2_4': (-14, -16),
             'NO2_5': (16, -6), 'NO3_1': (14, 0), 'NO4_1': (14, 2), 'NO4_3': (-14, -10)}


def fig_case2():
    need([n for n, _, _ in CASE2])
    fig, ax = plt.subplots(figsize=(6.4, 8.2))
    norway_base(ax)
    for node, mw, link in CASE2:
        lon, lat = NODES[node]
        ax.scatter(lon, lat, s=mw * 0.28, color=SMR_C, edgecolor='white',
                   linewidth=1.0, zorder=4)
        dx, dy = CASE2_OFF[node]
        ha = 'left' if dx > 0 else 'right'
        ax.annotate(f'{node}\n{mw} MW\n{link}', (lon, lat),
                    textcoords='offset points', xytext=(dx, dy), ha=ha, va='center',
                    fontsize=8, zorder=5,
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.85))
    handles = [Line2D([0], [0], marker='o', color='w', markerfacecolor=SMR_C,
                      markeredgecolor='white', markersize=np.sqrt(mw * 0.28),
                      label=f'{mw} MW') for mw in (300, 900, 1500, 2100)]
    ax.legend(handles=handles, loc='lower right', fontsize=8, frameon=True,
              title='SMR capacity', title_fontsize=8, labelspacing=1.3, borderpad=0.9)
    ax.set_title('Case 2: cable-endpoint SMR placement (9.3 GW total)',
                 fontsize=12, pad=6)
    fig.tight_layout()
    fig.savefig(OUT / 'case2_placement.pdf', bbox_inches='tight')
    plt.close(fig)
    print('wrote case2_placement.pdf')


# ============================================================
# Figure 2 - Case 3: Volt 2040 scenario placement (2 panels)
# ============================================================
UNIFORM = ['NO1_3', 'NO2_2', 'NO3_1', 'NO4_1', 'NO5_1']  # N1jevnt_OW0 nodes


def fig_case3():
    need(['NO2_2'] + UNIFORM)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10, 7.2))

    norway_base(axL)
    lon, lat = NODES['NO2_2']
    axL.scatter(lon - 0.35, lat, s=170, marker='^', color=OW_C,
                edgecolor='white', linewidth=1.0, zorder=4)
    axL.scatter(lon + 0.35, lat, s=170, marker='o', color=SMR_C,
                edgecolor='white', linewidth=1.0, zorder=4)
    axL.annotate('NO2_2\nOffshore wind: 2.0 / 4.0 GW\n(N0_OW1 / N0_OW2)\n'
                 'SMR: 2.1 / 3.9 GW\n(N1_OW0 / N2_OW0)',
                 (lon, lat), textcoords='offset points', xytext=(16, -6),
                 ha='left', va='center', fontsize=8.5, zorder=5,
                 bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#bbbbbb', alpha=0.9))
    axL.set_title('Concentrated at NO2_2', fontsize=12, pad=6)

    norway_base(axR)
    for node in UNIFORM:
        lon, lat = NODES[node]
        axR.scatter(lon, lat, s=90, marker='o', color=SMR_C,
                    edgecolor='white', linewidth=0.9, zorder=4)
        axR.annotate(node[:3], (lon, lat), textcoords='offset points',
                     xytext=(10, 0), ha='left', va='center', fontsize=8.5, zorder=5)
    axR.set_title('Uniform SMR: N1jevnt_OW0 (2.1 GW over NO1-NO5)', fontsize=12, pad=6)

    handles = [Line2D([0], [0], marker='^', color='w', markerfacecolor=OW_C,
                      markeredgecolor='white', markersize=11, label='Offshore wind'),
               Line2D([0], [0], marker='o', color='w', markerfacecolor=SMR_C,
                      markeredgecolor='white', markersize=11, label='SMR')]
    fig.legend(handles=handles, loc='lower center', ncol=2, fontsize=10,
               frameon=False, bbox_to_anchor=(0.5, 0.01))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / 'case3_placement.pdf', bbox_inches='tight')
    plt.close(fig)
    print('wrote case3_placement.pdf')


if __name__ == '__main__':
    fig_case2()
    fig_case3()
