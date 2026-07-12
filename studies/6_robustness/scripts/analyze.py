#!/usr/bin/env python3
"""Build robustness + volatility tables and figures from extract.py output."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/siva/Downloads/MT/Nuclear Power Norway Price"
OUT  = os.path.join(ROOT, "studies/6_robustness/out")
FIG  = os.path.join(ROOT, "overleaf/pictures/results")
TEX  = os.path.join(ROOT, "studies/6_robustness/out")
os.makedirs(FIG, exist_ok=True)

YEARS = list(range(1991, 2021))
def is_leap(y): return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
HRS = np.array([8784 if is_leap(y) else 8760 for y in YEARS])
BOUND = np.concatenate([[0], np.cumsum(HRS)])
ZONES = ["NO1", "NO2", "NO3", "NO4", "NO5"]

MD = ["BL_MD", "SMR1_MD", "SMR3_MD", "SMR6_MD", "SMR_NTC_MD"]
IC = ["BL_IC", "SMR1_IC", "SMR3_IC", "SMR6_IC", "SMR_NTC_IC"]
NUC_GW = {"BL": 0, "SMR1": 1.5, "SMR3": 4.5, "SMR6": 9.0, "SMR_NTC": 9.3}
LABEL = {"BL": "BL", "SMR1": "SMR1", "SMR3": "SMR3", "SMR6": "SMR6", "SMR_NTC": "SMR$_{\\mathrm{NTC}}$"}
def stem(s): return s.replace("_MD", "").replace("_IC", "")

def load(name):
    m = json.load(open(os.path.join(OUT, f"metrics_{name}.json")))
    return m

def zprice_year(m, yi, zone): return m["zprice"][f"{yi}|{zone}"]
def nat_year(m, yi): return np.mean([zprice_year(m, yi, z) for z in ZONES])

# ---- classify weather years into terciles by NO hydro inflow (from BL_MD) ----
bl = load("BL_MD")
inflow = []
for yi in range(30):
    tot = 0.0
    for t in ("hydro", "ror"):
        k = f"{yi}|NO|{t}"
        if k in bl["gen"]:
            tot += sum(bl["gen"][k])
    inflow.append(tot / 1e6)            # TWh
inflow = np.array(inflow)
order = np.argsort(inflow)              # ascending: driest first
DRY = sorted(order[:10].tolist())
NRM = sorted(order[10:20].tolist())
WET = sorted(order[20:].tolist())
driest_year  = YEARS[order[0]]
wettest_year = YEARS[order[-1]]
print("DRY tercile yrs :", [YEARS[i] for i in DRY])
print("NORMAL tercile  :", [YEARS[i] for i in NRM])
print("WET tercile yrs :", [YEARS[i] for i in WET])
print(f"driest={driest_year}  wettest={wettest_year}")

def tercile_natmean(m, idxs):
    """hour-weighted national simple-mean price over a set of year-indices."""
    vals = np.array([nat_year(m, yi) for yi in idxs])
    w = HRS[idxs]
    return (vals * w).sum() / w.sum()

def natmean_all(m):
    vals = np.array([nat_year(m, yi) for yi in range(30)])
    return (vals * HRS).sum() / HRS.sum()

# ================= TABLE 1: hydrological robustness of national price =========
def price_table(group, tag):
    rows = []
    for s in group:
        m = load(s)
        dry = tercile_natmean(m, DRY)
        nrm = tercile_natmean(m, NRM)
        wet = tercile_natmean(m, WET)
        # full 30-yr spread of annual national price
        ann = np.array([nat_year(m, yi) for yi in range(30)])
        lo, hi = ann.min(), ann.max()
        rows.append((stem(s), dry, nrm, wet, lo, hi))
    return rows

def fmt_price_table(rows, tag, demand):
    lines = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append(f"\\caption{{Hydrological robustness of the national simple-mean Norwegian "
                 f"price (EUR/MWh) under {demand}. Columns give the mean over the driest, "
                 f"middle, and wettest thirds of the 30 weather years; the last column gives "
                 f"the full 30-year annual range.}}")
    lines.append(f"\\label{{tab:res_robust_price_{tag}}}")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("\\toprule")
    lines.append("Scenario & Dry third & Normal third & Wet third & 30-yr range \\\\")
    lines.append("\\midrule")
    for name, dry, nrm, wet, lo, hi in rows:
        lab = LABEL[name]
        lines.append(f"{lab} & {dry:.1f} & {nrm:.1f} & {wet:.1f} & {lo:.0f}--{hi:.0f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)

# ================= TABLE 2: spill & nuclear CF by year-type ===================
def spill_cf_table(group, demand, tag):
    lines = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append(f"\\caption{{Norwegian hydropower spillage (TWh/yr) and nuclear capacity "
                 f"factor (\\%) by hydrological year-type under {demand}. Spillage is the "
                 f"mean annual NO hydro+RoR inflow that is spilled; capacity factor is "
                 f"NO nuclear generation over rated capacity.}}")
    lines.append(f"\\label{{tab:res_robust_spillcf_{tag}}}")
    lines.append("\\begin{tabular}{lcccccc}")
    lines.append("\\toprule")
    lines.append(" & \\multicolumn{3}{c}{Spill (TWh/yr)} & \\multicolumn{3}{c}{Nuclear CF (\\%)} \\\\")
    lines.append("\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}")
    lines.append("Scenario & Dry & Normal & Wet & Dry & Normal & Wet \\\\")
    lines.append("\\midrule")
    for s in group:
        m = load(s)
        cap = m["nuclear_cap_MW"]
        def spill(idxs):
            tot = 0.0; w = 0
            for yi in idxs:
                yspill = 0.0
                for t in ("hydro", "ror"):
                    k = f"{yi}|NO|{t}"
                    if k in m["gen"]: yspill += m["gen"][k][1]
                tot += yspill
            return tot / len(idxs) / 1e6  # TWh/yr
        def cf(idxs):
            if cap <= 1: return None
            g = 0.0; hrs = 0
            for yi in idxs:
                k = f"{yi}|NO|nuclear"
                if k in m["gen"]: g += m["gen"][k][0]
                hrs += HRS[yi]
            return 100.0 * g / (cap * hrs)
        sd, sn, sw = spill(DRY), spill(NRM), spill(WET)
        cd, cn, cw = cf(DRY), cf(NRM), cf(WET)
        cstr = lambda v: "--" if v is None else f"{v:.1f}"
        lines.append(f"{LABEL[stem(s)]} & {sd:.1f} & {sn:.1f} & {sw:.1f} & "
                     f"{cstr(cd)} & {cstr(cn)} & {cstr(cw)} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)

# ================= FIGURE 1: price-duration curves ===========================
def duration_fig(group, demand, fname):
    fig, ax = plt.subplots(figsize=(7, 4.3))
    colors = plt.cm.viridis(np.linspace(0, 0.85, len(group)))
    for s, col in zip(group, colors):
        ser = np.load(os.path.join(OUT, f"price_series_{s}.npy"))
        ser = ser[~np.isnan(ser)]
        sd = np.sort(ser)[::-1]
        x = np.linspace(0, 100, len(sd))
        ax.plot(x, sd, color=col, lw=1.6, label=LABEL[stem(s)])
    ax.set_xlabel("Share of hours [%]")
    ax.set_ylabel("Norwegian average price [EUR/MWh]")
    ax.set_title(f"Price-duration curve ({demand})")
    ax.set_xlim(0, 100); ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3); ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=150)
    fig.savefig(os.path.join(FIG, fname.replace(".png", ".pdf")))
    plt.close(fig)
    print("wrote", fname)

# ================= FIGURE 2: volatility / cannibalization signature ===========
def volatility_table_and_fig(group, demand, tag, fname):
    rows = []
    for s in group:
        ser = np.load(os.path.join(OUT, f"price_series_{s}.npy"))
        ser = ser[~np.isnan(ser)]
        mean = ser.mean(); std = ser.std()
        cov = std / mean if mean > 0 else float("nan")
        nz = 100.0 * np.mean(ser < 1.0)         # % near-zero-price hours
        hi = 100.0 * np.mean(ser > 100.0)       # % high-price hours
        p5, p95 = np.percentile(ser, [5, 95])
        rows.append((stem(s), mean, std, cov, nz, hi, p5, p95))
    # table
    lines = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append(f"\\caption{{Price distribution and volatility of the Norwegian average "
                 f"price under {demand}: mean, standard deviation, coefficient of variation, "
                 f"share of near-zero-price hours ($<$1~EUR/MWh) and high-price hours "
                 f"($>$100~EUR/MWh), and the 5th/95th percentiles.}}")
    lines.append(f"\\label{{tab:res_volatility_{tag}}}")
    lines.append("\\begin{tabular}{lccccccc}")
    lines.append("\\toprule")
    lines.append("Scenario & Mean & Std & CoV & $<$1 & $>$100 & P5 & P95 \\\\")
    lines.append(" & \\multicolumn{2}{c}{EUR/MWh} & & \\multicolumn{2}{c}{\\% hrs} & \\multicolumn{2}{c}{EUR/MWh} \\\\")
    lines.append("\\midrule")
    for name, mean, std, cov, nz, hi, p5, p95 in rows:
        lines.append(f"{LABEL[name]} & {mean:.1f} & {std:.1f} & {cov:.2f} & "
                     f"{nz:.1f} & {hi:.1f} & {p5:.1f} & {p95:.1f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    # figure: near-zero & high-price share vs nuclear GW (uniform scenarios only)
    uni = [r for r in rows if r[0] in ("BL", "SMR1", "SMR3", "SMR6")]
    gw = [NUC_GW[r[0]] for r in uni]
    nzs = [r[4] for r in uni]; his = [r[5] for r in uni]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(gw, nzs, "o-", color="#2c7fb8", lw=1.8, label="Near-zero-price hours ($<$1)")
    ax.plot(gw, his, "s--", color="#d95f0e", lw=1.8, label="High-price hours ($>$100)")
    ax.set_xlabel("Installed NO nuclear capacity [GW]")
    ax.set_ylabel("Share of hours [%]")
    ax.set_title(f"Price-tail response to nuclear capacity ({demand})")
    ax.grid(alpha=0.3); ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=150)
    fig.savefig(os.path.join(FIG, fname.replace(".png", ".pdf")))
    plt.close(fig)
    print("wrote", fname)
    return "\n".join(lines)

# ================= FIGURE 3: hydrological fan of national price ===============
def fan_fig(group, demand, fname):
    fig, ax = plt.subplots(figsize=(7, 4.3))
    xs = np.arange(len(group))
    for j, s in enumerate(group):
        m = load(s)
        ann = np.array([nat_year(m, yi) for yi in range(30)])
        ax.scatter(np.full(30, j), ann, s=14, color="0.6", alpha=0.6, zorder=2)
        ax.plot([j-0.25, j+0.25], [tercile_natmean(m, DRY)]*2, color="#c0392b", lw=2.4, zorder=3)
        ax.plot([j-0.25, j+0.25], [tercile_natmean(m, WET)]*2, color="#2980b9", lw=2.4, zorder=3)
        ax.plot([j-0.25, j+0.25], [natmean_all(m)]*2, color="k", lw=2.4, zorder=4)
    ax.set_xticks(xs); ax.set_xticklabels([LABEL[stem(s)] for s in group])
    ax.set_ylabel("National simple-mean price [EUR/MWh]")
    ax.set_title(f"Annual price spread across 30 weather years ({demand})")
    from matplotlib.lines import Line2D
    leg = [Line2D([0],[0],color="k",lw=2.4,label="30-yr mean"),
           Line2D([0],[0],color="#c0392b",lw=2.4,label="Dry third"),
           Line2D([0],[0],color="#2980b9",lw=2.4,label="Wet third"),
           Line2D([0],[0],marker="o",color="0.6",lw=0,label="Individual year")]
    ax.legend(handles=leg, frameon=False, fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=150)
    fig.savefig(os.path.join(FIG, fname.replace(".png", ".pdf")))
    plt.close(fig)
    print("wrote", fname)

if __name__ == "__main__":
    frags = []
    frags.append("% === auto-generated by studies/6_robustness/scripts/analyze.py ===")
    frags.append(f"% dry tercile years: {[YEARS[i] for i in DRY]}")
    frags.append(f"% wet tercile years: {[YEARS[i] for i in WET]}")
    frags.append(f"% driest={driest_year} wettest={wettest_year}")
    frags.append(fmt_price_table(price_table(MD, "md"), "md", "MD"))
    frags.append(fmt_price_table(price_table(IC, "ic"), "ic", "IC"))
    frags.append(spill_cf_table(MD, "MD", "md"))
    frags.append(spill_cf_table(IC, "IC", "ic"))
    frags.append(volatility_table_and_fig(MD, "MD", "md", "robust_volatility_MD.png"))
    frags.append(volatility_table_and_fig(IC, "IC", "ic", "robust_volatility_IC.png"))
    duration_fig(MD, "MD", "robust_duration_MD.png")
    duration_fig(IC, "IC", "robust_duration_IC.png")
    fan_fig(MD, "MD", "robust_fan_MD.png")
    fan_fig(IC, "IC", "robust_fan_IC.png")
    with open(os.path.join(TEX, "robust_tables.tex"), "w") as f:
        f.write("\n\n".join(frags))
    print("wrote robust_tables.tex")
