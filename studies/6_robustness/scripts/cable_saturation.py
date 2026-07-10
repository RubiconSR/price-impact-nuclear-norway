#!/usr/bin/env python3
"""Recompute NO HVDC cable saturation consistently from the CURRENT official
databases, and regenerate the saturation table + figures. Single definition:
share of hours the cable operates within 99% of its rated capacity
(|flow| >= 0.99 * capacity), matching the table caption."""
import sqlite3, os, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/siva/Downloads/MT/Nuclear Power Norway Price"
FIG  = os.path.join(ROOT, "overleaf/pictures/results")
OUT  = os.path.join(ROOT, "studies/6_robustness/out")

# NO DC interconnectors: Res_DcBranches.indx -> (name, cap MW, NO_is_from)
DC = [
    ("Skagerrak",      8, 1632.0, False),  # DK1_1 -> NO2_5
    ("NorNed",         3,  700.0, False),  # NL    -> NO2_4
    ("NordLink",      11, 1400.0, True),   # NO2_4 -> DE
    ("North Sea Link",10, 1400.0, True),   # NO2_1 -> GB
]
SCEN = {
    "BL_MD":      "scenarios/nuclear_MD/BL_MD/results/powergama_BL_MD.sqlite",
    "SMR_NTC_MD": "scenarios/nuclear_MD/SMR_NTC_MD/results/powergama_SMR_NTC_MD.sqlite",
    "BL_IC":      "scenarios/nuclear_IC/BL_IC/results/powergama_BL_IC.sqlite",
    "SMR_NTC_IC": "scenarios/nuclear_IC/SMR_NTC_IC/results/powergama_SMR_NTC_IC.sqlite",
}

def saturation(scen):
    """Export-direction saturation: share of hours the cable exports power
    from Norway at >= 99% of its rated capacity."""
    con = sqlite3.connect(os.path.join(ROOT, SCEN[scen]))
    res = {}
    for name, indx, cap, no_from in DC:
        fl = np.array([f for (f,) in
                       con.execute("SELECT flow FROM Res_DcBranches WHERE indx=?", (indx,))])
        exp = fl if no_from else -fl          # +exp = export out of NO
        res[name] = 100.0 * np.mean(exp >= 0.99 * cap)
    con.close()
    return res

if __name__ == "__main__":
    data = {s: saturation(s) for s in SCEN}
    json.dump(data, open(os.path.join(OUT, "cable_saturation.json"), "w"), indent=1)
    for s in SCEN:
        print(s, {k: round(v, 1) for k, v in data[s].items()})

    names = [d[0] for d in DC]
    # ---- figures: BL vs NTC per demand ----
    for dem, blk, ntck in [("MD", "BL_MD", "SMR_NTC_MD"), ("IC", "BL_IC", "SMR_NTC_IC")]:
        bl = [data[blk][n] for n in names]
        nt = [data[ntck][n] for n in names]
        y = np.arange(len(names)); h = 0.38
        fig, ax = plt.subplots(figsize=(6.8, 4.4))
        ax.barh(y + h/2, nt, h, color="#2c7fb8", label="SMR$_{\\mathrm{NTC}}$")
        ax.barh(y - h/2, bl, h, color="#bdbdbd", label="Baseline")
        ax.set_yticks(y); ax.set_yticklabels(names, fontsize=12)
        ax.set_xlabel("Hours exporting at $\\geq$99% of capacity [%]", fontsize=12)
        ax.set_xlim(0, 112); ax.invert_yaxis()
        ax.tick_params(axis="x", labelsize=11)
        # legend placed ABOVE the axes so it never overlaps the bars
        ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01),
                  ncol=2, fontsize=12)
        for yi, v in zip(y + h/2, nt):
            ax.text(v + 1.5, yi, f"{v:.0f}", va="center", fontsize=10)
        for yi, v in zip(y - h/2, bl):
            ax.text(v + 1.5, yi, f"{v:.0f}", va="center", fontsize=10, color="0.35")
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, f"Fig_NTC_cable_saturation_{dem}.pdf"))
        fig.savefig(os.path.join(FIG, f"Fig_NTC_cable_saturation_{dem}.png"), dpi=150)
        plt.close(fig)
        print("wrote figure", dem)

    # ---- LaTeX table (MD, the scenario the caption describes) ----
    md = data["SMR_NTC_MD"]
    order = [("Skagerrak", "DK1"), ("NorNed", "NL"), ("NordLink", "DE"),
             ("North Sea Link", "GB")]
    rows = "\n".join(f"{n} & {ep} & {md[n]:.0f} \\\\" for n, ep in order)
    print("\n--- TABLE BODY (MD) ---")
    print(rows)
