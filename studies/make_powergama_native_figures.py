#!/usr/bin/env python3
"""Results-chapter figures built on PowerGAMA's own result databases.

PowerGAMA's built-in plotting routines (res.plotMapGrid, plotEnergyMix,
plotAreaPrice) are used as the starting point; where a requested revision
cannot be expressed through them (a colour scale shared across two maps, a
proper calendar date axis, a TWh grouped-bar energy mix) the underlying data
is extracted via the Results API (getAverageNodalPrices, getAreaPrices,
getEnergyMix) and re-plotted with matplotlib.  No simulations are run here;
every figure is a pure read from the finished SQLite databases.

Output: overleaf/pictures/results/powergama/
"""
import sys
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import powergama

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generate_thesis_figures import load_grid, MD_DATA, VOLT_DEMAND, sqlpath

OUT = pathlib.Path(__file__).resolve().parent.parent / "overleaf" / "pictures" / "results" / "powergama"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Weather-year windows within the 30-year record (see thesis note on indexing).
# One weather year = 8760 h.  Year 20 (index 19) = 2010 = the DRY reference
# year; year 30 (index 29) = 2020 = the WET reference year.
# ---------------------------------------------------------------------------
DRY = [19 * 8760, 20 * 8760]        # 2010  -> [166440, 175200]
WET = [29 * 8760, 30 * 8760]        # 2020  -> [254040, 262800]
FULL_DATES = pd.date_range("1991-01-01", periods=262992, freq="h")
DATES = {"dry": FULL_DATES[DRY[0]:DRY[1]], "wet": FULL_DATES[WET[0]:WET[1]]}

MAP_CMAP = "RdYlGn_r"               # low price = green, high = red (matches captions)

VOLT_RES = lambda n: sqlpath("studies", "3_volt_benchmark", "results", f"{n}.sqlite")
MD_RES = lambda s: sqlpath("scenarios", "nuclear_MD", s, "results", f"powergama_{s}.sqlite")

# scenario registry: name -> (data_dir, demand_override, sqlite path)
SCEN = {
    "BL_MD":      (MD_DATA, None,        MD_RES("BL_MD")),
    "SMR6_MD":    (MD_DATA, None,        MD_RES("SMR6_MD")),
    "SMR_NTC_MD": (MD_DATA, None,        MD_RES("SMR_NTC_MD")),
    "VOLT_N0_OW0": (MD_DATA, VOLT_DEMAND, VOLT_RES("N0_OW0")),
    "VOLT_N2_OW0": (MD_DATA, VOLT_DEMAND, VOLT_RES("N2_OW0")),
    "VOLT_N0_OW2": (MD_DATA, VOLT_DEMAND, VOLT_RES("N0_OW2")),
}

_res_cache = {}


def get_res(name):
    if name in _res_cache:
        return _res_cache[name]
    ddir, dem, sql = SCEN[name]
    data = load_grid(ddir, dem)
    res = powergama.Results(data, str(sql), replace=False)
    _res_cache[name] = res
    return res


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


# ===========================================================================
# Maps: nodal-price geography with a COMMON colour scale and a neutral (white)
# background, replacing PowerGAMA's per-panel jet scale and turquoise ocean.
# ===========================================================================
def _node_xy(m, data):
    return m(data.node["lon"].astype(float).tolist(), data.node["lat"].astype(float).tolist())


def draw_map(ax, data, prices, vmin, vmax):
    from mpl_toolkits.basemap import Basemap
    lat = data.node["lat"].astype(float)
    lon = data.node["lon"].astype(float)
    m = Basemap(resolution="l", projection="merc", lat_ts=float(lat.mean()),
                llcrnrlon=float(lon.min()) - 1, llcrnrlat=float(lat.min()) - 1,
                urcrnrlon=float(lon.max()) + 1, urcrnrlat=float(lat.max()) + 1, ax=ax)
    m.drawcoastlines(linewidth=0.3, color="0.55")
    m.fillcontinents(color="0.94", lake_color="white")
    m.drawmapboundary(fill_color="white")
    # id -> (lon, lat) for branch endpoints
    coord = {r.id: (float(r.lon), float(r.lat)) for r in data.node.itertuples()}
    for br, col, lw in ((data.branch, "0.55", 0.4), (data.dcbranch, "#3a6ea5", 0.8)):
        for r in br.itertuples():
            a = coord.get(r.node_from); b = coord.get(r.node_to)
            if a and b:
                xa, ya = m(a[0], a[1]); xb, yb = m(b[0], b[1])
                ax.plot([xa, xb], [ya, yb], color=col, lw=lw, zorder=1)
    x, y = _node_xy(m, data)
    sc = m.scatter(x, y, c=np.asarray(prices, dtype=float), cmap=MAP_CMAP,
                   vmin=vmin, vmax=vmax, s=34, edgecolor="k", linewidth=0.3, zorder=3)
    ax.set_axis_off()
    return sc


def fig_map_2x2_dry_wet():
    """MERGED figure (former 8.2 + 8.3): rows = dry(2010)/wet(2020),
    cols = baseline/SMR6, single shared colour scale."""
    panels = [
        ("dry", "BL_MD",   "Dry year (2010) - Baseline (MD)"),
        ("dry", "SMR6_MD", "Dry year (2010) - 9 GW SMR (MD)"),
        ("wet", "BL_MD",   "Wet year (2020) - Baseline (MD)"),
        ("wet", "SMR6_MD", "Wet year (2020) - 9 GW SMR (MD)"),
    ]
    prices = {}
    for win, name, _ in panels:
        prices[(win, name)] = get_res(name).getAverageNodalPrices(
            timeMaxMin=DRY if win == "dry" else WET)
    allv = np.concatenate([np.asarray(p, float)[~np.isnan(np.asarray(p, float))]
                           for p in prices.values()])
    vmin, vmax = float(np.floor(allv.min())), float(np.ceil(allv.max()))
    fig, axes = plt.subplots(2, 2, figsize=(11, 12))
    sc = None
    for axf, (win, name, title) in zip(axes.flat, panels):
        sc = draw_map(axf, get_res(name).grid, prices[(win, name)], vmin, vmax)
        axf.set_title(title, fontsize=12)
    cbar = fig.colorbar(sc, ax=axes, orientation="horizontal", fraction=0.045,
                        pad=0.03, shrink=0.7)
    cbar.set_label("Nodal price [EUR/MWh]", fontsize=12)
    save(fig, "pg_map_dryWet_BL_SMR6")


def fig_map_pair(name_left, name_right, outbase, window=DRY):
    """Two standalone map PDFs sharing a common colour scale (for figures kept
    side-by-side in the LaTeX: SMR6-vs-NTC, and VOLT SMR-vs-OW)."""
    pl = get_res(name_left).getAverageNodalPrices(timeMaxMin=window)
    pr = get_res(name_right).getAverageNodalPrices(timeMaxMin=window)
    both = np.concatenate([np.asarray(pl, float), np.asarray(pr, float)])
    both = both[~np.isnan(both)]
    vmin, vmax = float(np.floor(both.min())), float(np.ceil(both.max()))
    for name, prices in ((name_left, pl), (name_right, pr)):
        fig, ax = plt.subplots(figsize=(6.5, 8))
        sc = draw_map(ax, get_res(name).grid, prices, vmin, vmax)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
        cbar.set_label("Nodal price [EUR/MWh]", fontsize=11)
        save(fig, outbase(name))


# ===========================================================================
# Area price time series: proper calendar (month) x-axis, shared y-limits.
# ===========================================================================
def area_series(name, window):
    return np.asarray(get_res(name).getAreaPrices("NO", timeMaxMin=window), dtype=float)


def fig_areaprice_stacked(panels, outname, window="dry"):
    """panels: list of (scenario_name, legend_label).  One figure, stacked
    subplots, shared y-limits, month date axis."""
    win = DRY if window == "dry" else WET
    dates = DATES[window]
    series = [(area_series(n, win), lbl) for n, lbl in panels]
    ymax = max(s.max() for s, _ in series)
    n = len(series)
    fig, axes = plt.subplots(n, 1, figsize=(9, 2.4 * n + 0.6), sharex=True)
    if n == 1:
        axes = [axes]
    for ax, (s, lbl) in zip(axes, series):
        ax.plot(dates, s, color="#1f5fa8", lw=0.5)
        ax.set_ylim(0, ymax * 1.03)
        ax.set_ylabel("Price [EUR/MWh]", fontsize=10)
        ax.legend([lbl], loc="upper right", fontsize=10, frameon=True)
        ax.grid(alpha=0.25)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    axes[-1].set_xlim(dates[0], dates[-1])
    fig.tight_layout()
    save(fig, outname)


# ===========================================================================
# Energy mix: grouped bars per technology, in TWh/yr, common y-scale.
# ===========================================================================
TECH_ORDER = ["hydro", "ror", "wind_on", "wind_off", "solar", "nuclear",
              "fossil_gas", "biomass"]
TECH_LABEL = {"hydro": "Hydro", "ror": "Run-of-river", "wind_on": "Onshore wind",
              "wind_off": "Offshore wind", "solar": "Solar", "nuclear": "Nuclear",
              "fossil_gas": "Gas", "biomass": "Biomass"}
N_YEARS = 30.0

_energy_cache = {}


def energy_twh(name):
    """NO annual generation per technology [TWh/yr], read directly from the
    result DB so that runtime-added SMR generators (absent from the static
    generator.csv) are included consistently."""
    if name in _energy_cache:
        return _energy_cache[name]
    import sqlite3
    sql = SCEN[name][2]
    con = sqlite3.connect(str(sql))
    gsum = pd.read_sql("SELECT indx, SUM(output) AS mwh FROM Res_Generators GROUP BY indx", con)
    gg = pd.read_sql("SELECT indx, node, type FROM Grid_Generators", con)
    gn = pd.read_sql("SELECT id, area FROM Grid_Nodes", con)
    con.close()
    df = gsum.merge(gg, on="indx").merge(gn, left_on="node", right_on="id")
    per = df[df["area"] == "NO"].groupby("type")["mwh"].sum() / 1e6 / N_YEARS
    out = {t: float(per.get(t, 0.0)) for t in TECH_ORDER}
    _energy_cache[name] = out
    return out


def fig_energymix_grouped(name_a, lbl_a, name_b, lbl_b, outname):
    a = energy_twh(name_a)
    b = energy_twh(name_b)
    techs = [t for t in TECH_ORDER if a[t] > 0.05 or b[t] > 0.05]
    x = np.arange(len(techs))
    w = 0.4
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ba = ax.bar(x - w / 2, [a[t] for t in techs], w, label=lbl_a,
                color="#bdbdbd", edgecolor="black", lw=0.4)
    bb = ax.bar(x + w / 2, [b[t] for t in techs], w, label=lbl_b,
                color="#e8552d", edgecolor="black", lw=0.4)
    ax.bar_label(ba, fmt="%.0f", fontsize=8, padding=2)
    ax.bar_label(bb, fmt="%.0f", fontsize=8, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels([TECH_LABEL[t] for t in techs], rotation=25, ha="right", fontsize=10)
    ax.set_ylabel("Annual generation [TWh/yr]", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, outname)


# ===========================================================================
def main():
    print("=== maps ===")
    fig_map_2x2_dry_wet()
    fig_map_pair("SMR6_MD", "SMR_NTC_MD",
                 lambda n: {"SMR6_MD": "pg_map_SMR6_MD",
                            "SMR_NTC_MD": "pg_map_SMR_NTC_MD"}[n])
    fig_map_pair("VOLT_N2_OW0", "VOLT_N0_OW2",
                 lambda n: {"VOLT_N2_OW0": "pg_map_VOLT_N2_OW0",
                            "VOLT_N0_OW2": "pg_map_VOLT_N0_OW2"}[n])

    print("=== area price time series ===")
    fig_areaprice_stacked(
        [("BL_MD", "Baseline (MD)"), ("SMR6_MD", "9 GW SMR (MD)")],
        "pg_areaprice_BL_SMR6_MD", window="dry")
    fig_areaprice_stacked(
        [("VOLT_N0_OW0", "V0 baseline"),
         ("VOLT_N2_OW0", "3.9 GW SMR @ NO2"),
         ("VOLT_N0_OW2", "4 GW offshore wind")],
        "pg_areaprice_VOLT_3panel", window="dry")

    print("=== energy mix ===")
    fig_energymix_grouped("BL_MD", "Baseline (MD)", "SMR6_MD", "9 GW SMR (MD)",
                          "pg_energymix_grouped_BL_SMR6")
    fig_energymix_grouped("SMR6_MD", "9 GW SMR uniform (MD)",
                          "SMR_NTC_MD", "9.3 GW SMR @ cables (MD)",
                          "pg_energymix_grouped_SMR6_NTC")
    print("ALL DONE")


if __name__ == "__main__":
    main()
