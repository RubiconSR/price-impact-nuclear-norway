"""
Case 1 capture-price figure: nuclear production-weighted capture price and
realised capacity factor as a function of installed SMR capacity, for the
MD and IC demand pathways. Dual axis: left = capture price (EUR/MWh),
right = capacity factor (%); a horizontal reference line marks the SMR
fuel cost (9.37 EUR/MWh), so the shrinking margin over the floor is
visible as the mechanism behind the capacity-factor decline.

Style matches the adjacent Case 1 CF figure (regen_fig6_cf.py).

Values are the DB-verified figures of Table 8.5 (tab:res_case1_cf) and are
hardcoded so the figure renders without the ~5 GB result databases (as in
regen_fig6_cf.py). They are reproducible from the databases via the
powergama.database Results API with `python plot_capture_price.py --reproduce`
(extract_capture_cf below), which reads generator power and nodal prices
through Database.getResultGeneratorPower / getResultNodalPrice -- no raw SQL
on the result tables. Verified: extract_capture_cf reproduces every cell of
Table 8.5 exactly.
"""
import sys
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = pathlib.Path(__file__).resolve().parents[2]
OUT = BASE / 'overleaf' / 'pictures' / 'results'

GW = [1.5, 4.5, 9.0]
# DB-verified values of Table 8.5 (tab:res_case1_cf).
CAPTURE = {'MD': [61.6, 36.8, 21.6], 'IC': [109.1, 54.6, 24.9]}
CF = {'MD': [74.0, 61.5, 50.8], 'IC': [89.8, 76.4, 60.3]}

FUEL = 9.37                       # SMR fuel cost (EUR/MWh) -- the price floor
CAP_COL = '#2c7fb8'               # capture price (left axis); matches Fig6 MD blue
CF_COL = '#2e7d4f'                # capacity factor (right axis)
FUEL_COL = '#b3202f'


# ---------------------------------------------------------------------------
# Reproducibility: extract capture price and capacity factor via the
# powergama.database Results API (no raw SQL on the result tables).
# ---------------------------------------------------------------------------
def extract_capture_cf(db_path, cap_gw, n_hours=262992):
    """Return (capture_price, capacity_factor_percent) for the Norwegian SMR
    fleet in one scenario, using Database.getResultGeneratorPower and
    getResultNodalPrice. Static grid metadata (which generators are nuclear
    and their nodes) is read from the Grid_* definition tables; every result
    value comes through the Results API."""
    import sqlite3
    from powergama.database import Database

    con = sqlite3.connect(str(db_path))
    name_col = [r[1] for r in con.execute('PRAGMA table_info(Grid_Nodes)')
                if r[1].lower() in ('node', 'id', 'name')][0]
    smr = con.execute("SELECT indx, node FROM Grid_Generators "
                      "WHERE type='nuclear' AND node LIKE 'NO%'").fetchall()
    node_idx = {r[1]: r[0] for r in
                con.execute(f'SELECT indx, {name_col} FROM Grid_Nodes')}
    con.close()

    db = Database(str(db_path))
    num = den = 0.0
    for gen_i, node in smr:
        out = db.getResultGeneratorPower(gen_i, [0, n_hours])
        price = db.getResultNodalPrice(node_idx[node], [0, n_hours])
        num += sum(o * p for o, p in zip(out, price))
        den += sum(out)
    capture = num / den
    cf = den / (len(smr) * 300 * n_hours) * 100
    return capture, cf


def reproduce_from_db():
    scen = {'MD': [('SMR1_MD', 1.5), ('SMR3_MD', 4.5), ('SMR6_MD', 9.0)],
            'IC': [('SMR1_IC', 1.5), ('SMR3_IC', 4.5), ('SMR6_IC', 9.0)]}
    for dem, rows in scen.items():
        for name, cap in rows:
            sub = 'nuclear_MD' if dem == 'MD' else 'nuclear_IC'
            db = BASE / 'scenarios' / sub / name / 'results' / f'powergama_{name}.sqlite'
            cp, cf = extract_capture_cf(db, cap)
            print(f'{name}: capture={cp:.1f}  CF={cf:.1f}%')


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(8.5, 5.2))
    ax2 = ax1.twinx()

    ax1.plot(GW, CAPTURE['MD'], color=CAP_COL, lw=2.2, marker='o', ms=7, ls='-')
    ax1.plot(GW, CAPTURE['IC'], color=CAP_COL, lw=2.2, marker='s', ms=7, ls='--')
    ax2.plot(GW, CF['MD'], color=CF_COL, lw=2.2, marker='o', ms=7, ls='-')
    ax2.plot(GW, CF['IC'], color=CF_COL, lw=2.2, marker='s', ms=7, ls='--')

    # fuel-cost floor (labelled via the legend, not floating text)
    ax1.axhline(FUEL, color=FUEL_COL, lw=1.4, ls='--')

    ax1.set_xlabel('Installed SMR capacity [GW]', fontsize=12)
    ax1.set_ylabel('Nuclear capture price [EUR/MWh]', fontsize=12, color=CAP_COL)
    ax2.set_ylabel('Capacity factor [%]', fontsize=12, color=CF_COL)
    ax1.tick_params(axis='y', labelcolor=CAP_COL, labelsize=10)
    ax2.tick_params(axis='y', labelcolor=CF_COL, labelsize=10)

    ax1.set_xticks(GW)
    ax1.set_xticklabels(['1.5', '4.5', '9.0'], fontsize=11)
    ax1.set_xlim(1.0, 9.5)
    ax1.set_ylim(0, 120)
    ax2.set_ylim(0, 100)
    ax1.grid(axis='y', alpha=0.3)
    ax1.set_axisbelow(True)

    handles = [
        Line2D([0], [0], color=CAP_COL, lw=2.2, marker='o', ls='-', label='Capture price, MD'),
        Line2D([0], [0], color=CAP_COL, lw=2.2, marker='s', ls='--', label='Capture price, IC'),
        Line2D([0], [0], color=CF_COL, lw=2.2, marker='o', ls='-', label='Capacity factor, MD'),
        Line2D([0], [0], color=CF_COL, lw=2.2, marker='s', ls='--', label='Capacity factor, IC'),
        Line2D([0], [0], color=FUEL_COL, lw=1.4, ls='--', label=f'SMR fuel cost ({FUEL:.2f})'),
    ]
    ax1.legend(handles=handles, loc='upper right', fontsize=10, frameon=True)
    ax1.set_title('Nuclear capture price and capacity factor vs SMR deployment (Case 1)',
                  fontsize=13)

    fig.tight_layout()
    for ext in ('pdf', 'png'):
        fig.savefig(OUT / f'capture_price_cf.{ext}', dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('wrote capture_price_cf to', OUT)


if __name__ == '__main__':
    if '--reproduce' in sys.argv:
        reproduce_from_db()
    else:
        main()
