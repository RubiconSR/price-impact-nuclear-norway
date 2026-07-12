#!/usr/bin/env python3
"""Recompute the hourly NO price series as the 5-zone simple mean (mean of the
five zonal node-averages), matching the thesis 'simple mean' convention, so the
volatility-table 'Mean' reconciles with the Case 1 zonal-price tables."""
import sqlite3, os, sys
import numpy as np

ROOT = "/Users/siva/Downloads/MT/Nuclear Power Norway Price"
OUT  = os.path.join(ROOT, "studies/6_robustness/out")
SCEN = {
    "BL_MD":"scenarios/nuclear_MD/BL_MD/results/powergama_BL_MD.sqlite",
    "SMR1_MD":"scenarios/nuclear_MD/SMR1_MD/results/powergama_SMR1_MD.sqlite",
    "SMR3_MD":"scenarios/nuclear_MD/SMR3_MD/results/powergama_SMR3_MD.sqlite",
    "SMR6_MD":"scenarios/nuclear_MD/SMR6_MD/results/powergama_SMR6_MD.sqlite",
    "SMR_NTC_MD":"scenarios/nuclear_MD/SMR_NTC_MD/results/powergama_SMR_NTC_MD.sqlite",
    "BL_IC":"scenarios/nuclear_IC/BL_IC/results/powergama_BL_IC.sqlite",
    "SMR1_IC":"scenarios/nuclear_IC/SMR1_IC/results/powergama_SMR1_IC.sqlite",
    "SMR3_IC":"scenarios/nuclear_IC/SMR3_IC/results/powergama_SMR3_IC.sqlite",
    "SMR6_IC":"scenarios/nuclear_IC/SMR6_IC/results/powergama_SMR6_IC.sqlite",
    "SMR_NTC_IC":"scenarios/nuclear_IC/SMR_NTC_IC/results/powergama_SMR_NTC_IC.sqlite",
}
ZONES = ["NO1","NO2","NO3","NO4","NO5"]

def process(name, rel):
    con = sqlite3.connect(os.path.join(ROOT, rel))
    nodes = {i:(idd,area) for i,idd,area in con.execute("SELECT indx,id,area FROM Grid_Nodes")}
    con.execute("CREATE TEMP TABLE nz(indx INTEGER PRIMARY KEY, zone TEXT)")
    con.executemany("INSERT INTO nz VALUES (?,?)",
        [(i, idd.split('_')[0]) for i,(idd,area) in nodes.items() if area=="NO"])
    con.commit()
    # per-timestep per-zone node-average, then average the 5 zones in numpy
    zsum = {z: np.full(262992, np.nan) for z in ZONES}
    q = """SELECT rn.timestep, n.zone, AVG(rn.nodalprice)
           FROM Res_Nodes rn JOIN nz n ON rn.indx=n.indx
           GROUP BY rn.timestep, n.zone"""
    for ts, zone, p in con.execute(q):
        zsum[zone][ts] = p
    con.close()
    arr = np.vstack([zsum[z] for z in ZONES])     # 5 x 262992
    series = np.nanmean(arr, axis=0).astype(np.float32)
    np.save(os.path.join(OUT, f"price_series_{name}.npy"), series)
    print(f"[{name}] series mean={np.nanmean(series):.1f}", flush=True)

if __name__ == "__main__":
    for name in (sys.argv[1:] or list(SCEN)):
        process(name, SCEN[name])
    print("DONE", flush=True)
