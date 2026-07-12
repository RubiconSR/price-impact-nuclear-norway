#!/usr/bin/env python3
"""Verify the Case 2 cable-saturation numbers and the +42.5 TWh net-export
figure directly from the flow tables (P8 + no-fabricated-numbers check)."""
import sqlite3, os, sys
ROOT = "/Users/siva/Downloads/MT/Nuclear Power Norway Price"

# DC interconnectors that touch NO (row index in dcbranch.csv = Res_DcBranches.indx)
# (indx, name, cap, NO_is_from?)  flow>0 means node_from -> node_to
DC = {
    3:  ("NorNed",        700.0, False),  # NL -> NO2_4  : +flow = import to NO
    8:  ("Skagerrak",    1632.0, False),  # DK1 -> NO2_5 : +flow = import
    10: ("North Sea Link",1400.0, True),  # NO2_1 -> GB  : +flow = export
    11: ("NordLink",     1400.0, True),   # NO2_4 -> DE  : +flow = export
}
# AC cross-border branches with NO (from=NO side per Grid_Branches): +flow = export
AC = {49:1000.0, 54:911.0, 55:911.0, 59:900.0, 61:400.0, 95:84.0}

def run(scen, rel):
    con = sqlite3.connect(os.path.join(ROOT, rel))
    print(f"\n=== {scen} ===")
    # --- DC cables: saturation + gross export/import ---
    net_exp = 0.0
    for indx, (name, cap, no_from) in DC.items():
        rows = con.execute("SELECT flow FROM Res_DcBranches WHERE indx=?", (indx,)).fetchall()
        n = len(rows)
        sat = sum(1 for (f,) in rows if abs(f) >= 0.99*cap)
        # export direction energy (MWh -> TWh); sign depends on orientation
        exp = sum((f if no_from else -f) for (f,) in rows) / 1e6
        net_exp += exp
        print(f"  DC {name:15s} cap={cap:6.0f}  sat={100*sat/n:5.1f}%  netexp={exp:+6.1f} TWh  (n={n})")
    # --- AC cables: net export ---
    ac_exp = 0.0
    for indx, cap in AC.items():
        rows = con.execute("SELECT flow FROM Res_Branches WHERE indx=?", (indx,)).fetchall()
        e = sum(f for (f,) in rows) / 1e6
        ac_exp += e
    print(f"  AC NO-SE/FI total net export = {ac_exp:+.1f} TWh")
    print(f"  >>> TOTAL NO net export (DC+AC) = {net_exp+ac_exp:+.1f} TWh  "
          f"(thesis quotes +42.5 TWh for SMR_NTC_MD)")
    con.close()

if __name__ == "__main__":
    run("SMR_NTC_MD", "scenarios/nuclear_MD/SMR_NTC_MD/results/powergama_SMR_NTC_MD.sqlite")
