#!/usr/bin/env python3
"""Robustness & volatility extraction for the nuclear-price thesis.

Pure extraction from the existing 30-year result databases (no re-simulation).
For each scenario it computes, in a SINGLE scan per big table:
  - NO1..NO5 simple zonal price + national simple mean, per weather year
  - nuclear generation, NO hydro+ror generation, NO spill, generation mix, per year
  - a 262,992-long NO-average hourly price series (for duration curves / volatility)

Weather years 1991-2020 have variable length (leap years = 8784 h). The driest /
median / wettest years are identified from NO hydro inflow (output + spilled) and
used as the dry / normal / wet representatives, mirroring By & Skavlem (2025).
"""
import sqlite3, json, os, sys
import numpy as np

ROOT = "/Users/siva/Downloads/MT/Nuclear Power Norway Price"
OUT  = os.path.join(ROOT, "studies/6_robustness/out")

SCEN = {
    "BL_MD":      "scenarios/nuclear_MD/BL_MD/results/powergama_BL_MD.sqlite",
    "SMR1_MD":    "scenarios/nuclear_MD/SMR1_MD/results/powergama_SMR1_MD.sqlite",
    "SMR3_MD":    "scenarios/nuclear_MD/SMR3_MD/results/powergama_SMR3_MD.sqlite",
    "SMR6_MD":    "scenarios/nuclear_MD/SMR6_MD/results/powergama_SMR6_MD.sqlite",
    "SMR_NTC_MD": "scenarios/nuclear_MD/SMR_NTC_MD/results/powergama_SMR_NTC_MD.sqlite",
    "BL_IC":      "scenarios/nuclear_IC/BL_IC/results/powergama_BL_IC.sqlite",
    "SMR1_IC":    "scenarios/nuclear_IC/SMR1_IC/results/powergama_SMR1_IC.sqlite",
    "SMR3_IC":    "scenarios/nuclear_IC/SMR3_IC/results/powergama_SMR3_IC.sqlite",
    "SMR6_IC":    "scenarios/nuclear_IC/SMR6_IC/results/powergama_SMR6_IC.sqlite",
    "SMR_NTC_IC": "scenarios/nuclear_IC/SMR_NTC_IC/results/powergama_SMR_NTC_IC.sqlite",
}

YEARS = list(range(1991, 2021))
def is_leap(y): return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
HRS = [8784 if is_leap(y) else 8760 for y in YEARS]
BOUND = np.cumsum([0] + HRS)            # 31 boundaries, BOUND[-1] = 262992
assert BOUND[-1] == 262992, BOUND[-1]

def ts_to_yearidx(n):
    """vectorised timestep -> year index 0..29"""
    return np.searchsorted(BOUND, n, side="right") - 1

def make_tsyear(con):
    con.execute("CREATE TEMP TABLE tsyear(timestep INTEGER PRIMARY KEY, yr INTEGER)")
    rows = []
    for yi in range(30):
        for ts in range(int(BOUND[yi]), int(BOUND[yi+1])):
            rows.append((ts, yi))
    con.executemany("INSERT INTO tsyear VALUES (?,?)", rows)
    con.commit()

def gen_classes(con):
    """indx -> (country, zone, gtype) and NO-zone node indices."""
    nodes = {i: (idd, area) for i, idd, area in
             con.execute("SELECT indx,id,area FROM Grid_Nodes")}
    gclass = {}
    for indx, node, gtype in con.execute("SELECT indx,node,type FROM Grid_Generators"):
        zone = node.split("_")[0]
        country = zone[:2] if zone[:2].isalpha() else zone
        # country code = letters before the digit, e.g. NO1 -> NO
        c = "".join(ch for ch in zone if ch.isalpha())
        gclass[indx] = (c, zone, gtype)
    return nodes, gclass

def process(name, relpath):
    path = os.path.join(ROOT, relpath)
    print(f"[{name}] open {relpath}", flush=True)
    con = sqlite3.connect(path)
    nodes, gclass = gen_classes(con)
    make_tsyear(con)

    # generator class temp table
    con.execute("CREATE TEMP TABLE gc(indx INTEGER PRIMARY KEY, country TEXT, zone TEXT, gtype TEXT)")
    con.executemany("INSERT INTO gc VALUES (?,?,?,?)",
                    [(i, c, z, t) for i, (c, z, t) in gclass.items()])
    # node zone temp table (NO nodes only)
    con.execute("CREATE TEMP TABLE nz(indx INTEGER PRIMARY KEY, zone TEXT)")
    con.executemany("INSERT INTO nz VALUES (?,?)",
                    [(i, idd.split('_')[0]) for i, (idd, area) in nodes.items()
                     if area == "NO"])
    con.commit()

    # ---- 1. generation by year x country x gtype (one scan of Res_Generators) ----
    print(f"[{name}] scan Res_Generators ...", flush=True)
    gen = {}   # (yr, country, gtype) -> [sum_output_MWh, sum_spill_MWh]
    q = """SELECT y.yr, g.country, g.gtype,
                  SUM(rg.output), SUM(rg.inflow_spilled)
           FROM Res_Generators rg
           JOIN tsyear y ON rg.timestep=y.timestep
           JOIN gc g      ON rg.indx=g.indx
           GROUP BY y.yr, g.country, g.gtype"""
    for yr, country, gtype, out, spill in con.execute(q):
        gen[(yr, country, gtype)] = [out or 0.0, spill or 0.0]

    # nuclear capacity (MW) = sum of per-generator max output over the run
    print(f"[{name}] nuclear capacity ...", flush=True)
    nuc_cap = con.execute("""
        SELECT COALESCE(SUM(m),0) FROM (
          SELECT MAX(rg.output) m FROM Res_Generators rg
          JOIN gc g ON rg.indx=g.indx
          WHERE g.gtype='nuclear' AND g.country='NO'
          GROUP BY rg.indx)""").fetchone()[0]

    # ---- 2. zonal prices by year (one scan of Res_Nodes) ----
    print(f"[{name}] scan Res_Nodes (zonal) ...", flush=True)
    zprice = {}  # (yr, zone) -> avg nodalprice
    q2 = """SELECT y.yr, n.zone, AVG(rn.nodalprice)
            FROM Res_Nodes rn
            JOIN tsyear y ON rn.timestep=y.timestep
            JOIN nz n     ON rn.indx=n.indx
            GROUP BY y.yr, n.zone"""
    for yr, zone, p in con.execute(q2):
        zprice[(yr, zone)] = p

    # ---- 3. NO-average hourly price series (one scan of Res_Nodes) ----
    print(f"[{name}] scan Res_Nodes (hourly series) ...", flush=True)
    series = np.full(262992, np.nan)
    q3 = """SELECT rn.timestep, AVG(rn.nodalprice)
            FROM Res_Nodes rn JOIN nz n ON rn.indx=n.indx
            GROUP BY rn.timestep"""
    for ts, p in con.execute(q3):
        series[ts] = p

    con.close()
    np.save(os.path.join(OUT, f"price_series_{name}.npy"), series.astype(np.float32))

    result = {
        "scenario": name,
        "nuclear_cap_MW": nuc_cap,
        "zprice": {f"{yr}|{zone}": v for (yr, zone), v in zprice.items()},
        "gen": {f"{yr}|{c}|{t}": v for (yr, c, t), v in gen.items()},
    }
    with open(os.path.join(OUT, f"metrics_{name}.json"), "w") as f:
        json.dump(result, f)
    print(f"[{name}] DONE nuc_cap={nuc_cap:.0f} MW", flush=True)
    return result

if __name__ == "__main__":
    todo = sys.argv[1:] or list(SCEN)
    for name in todo:
        process(name, SCEN[name])
    print("ALL DONE", flush=True)
