#!/usr/bin/env python3
"""Illustrative theory-chapter figures (Ch2-3): merit order, water-value
dispatch, Nordic market timeline, and a stylised Norwegian bidding-zone map.

The first three are conceptual/schematic (no simulation data); the zone map
uses the real node coordinates from the model grid data. Output goes to
overleaf/pictures/ as PDF (vector) + PNG."""
import os, pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = pathlib.Path(__file__).resolve().parent.parent
OUT = BASE / "overleaf" / "pictures"
plt.rcParams.update({"font.size": 11, "axes.linewidth": 0.8})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def _assert_no_overlap(fig, ax, label_bar_pairs, bar_geoms):
    """Programmatic proof that the merit-order labelling is collision-free.

    Renders the figure and, via each artist's window extent (display px),
    asserts (i) no pair of text labels overlaps and (ii) no label sits over a
    bar that is not its own. Bar rectangles are taken from their known data
    coordinates transformed to display space, which is exact regardless of the
    patch draw order."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    EPS = 0.5  # px; a shared edge is not an overlap

    def boxes_overlap(a, b):
        ix = min(a.x1, b.x1) - max(a.x0, b.x0)
        iy = min(a.y1, b.y1) - max(a.y0, b.y0)
        return ix > EPS and iy > EPS

    from matplotlib.transforms import Bbox
    labels = [(lab, t, t.get_window_extent(rend)) for lab, t, _ in label_bar_pairs]

    # (i) pairwise overlap over *all* text artists in the axes
    all_texts = [(t.get_text(), t.get_window_extent(rend)) for t in ax.texts]
    for i in range(len(all_texts)):
        for j in range(i + 1, len(all_texts)):
            (la, ba), (lb, bb) = all_texts[i], all_texts[j]
            assert not boxes_overlap(ba, bb), \
                f"text overlap: '{la}' <-> '{lb}'"

    # (ii) label over a foreign bar
    bar_boxes = {}
    for lab, (x0, x1, y0, y1) in bar_geoms.items():
        (dx0, dy0) = ax.transData.transform((x0, y0))
        (dx1, dy1) = ax.transData.transform((x1, y1))
        bar_boxes[lab] = Bbox([[min(dx0, dx1), min(dy0, dy1)],
                               [max(dx0, dx1), max(dy0, dy1)]])
    for lab, _, tbox in labels:
        for blab, bbox in bar_boxes.items():
            if blab == lab:
                continue
            assert not boxes_overlap(tbox, bbox), \
                f"label '{lab}' overlaps foreign bar '{blab}'"
    print("  merit_order: overlap check passed "
          f"({len(labels)} labels, {len(bar_boxes)} bars)")


# ---------------------------------------------------------------- 1. merit order
def merit_order():
    # (label, width=capacity GW, marginal cost EUR/MWh, colour) -- illustrative.
    # Each bar is made wide enough for its own label so the horizontal,
    # bar-top label always fits within its own column and never spills over a
    # (taller) neighbouring bar to its right. Enforced by _assert_no_overlap.
    blocks = [
        ("Wind & solar", 12, 0, "#7fd08a"),
        ("Nuclear (SMR)", 9, 9, "#e8552d"),
        ("Reservoir hydro", 14, 15, "#1f5fa8"),
        ("Imports", 7, 45, "#9467bd"),
        ("Gas", 6, 90, "#7f7f7f"),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    label_bar_pairs = []  # (label, text artist, bar patch)
    bar_geoms = {}        # label -> (x0, x1, y0, y1) in data coords
    x = 0
    for lab, w, mc, col in blocks:
        cont = ax.bar(x + w / 2, mc, width=w, color=col, edgecolor="white",
                      align="center", zorder=2)
        # technology label placed above the top of each block, read
        # horizontally; the white halo keeps it legible over the axes.
        # "Wind & solar" (mc=0) therefore sits just above the baseline.
        t = ax.text(x + w / 2, mc + 2.5, lab, ha="center", va="bottom",
                    fontsize=9.5, color="black", zorder=5,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])
        label_bar_pairs.append((lab, t, cont.patches[0]))
        bar_geoms[lab] = (x, x + w, 0, mc)
        x += w
    demand = 28.0
    clearing = 15  # marginal block (reservoir hydro) at this demand
    ax.axvline(demand, color="black", ls="--", lw=1.4, zorder=3)
    ax.text(demand + 0.4, 105, "Demand", rotation=90, va="top", fontsize=10)
    ax.axhline(clearing, xmin=0, xmax=demand / x, color="#b30000", ls=":", lw=1.6, zorder=3)
    ax.set_xlabel("Cumulative available capacity [GW]")
    ax.set_ylabel("Marginal cost [EUR/MWh]")
    ax.set_title("Merit-order dispatch and market clearing (illustrative)")
    ax.set_xlim(0, x)
    ax.set_ylim(0, 115)
    ax.spines[["top", "right"]].set_visible(False)
    _assert_no_overlap(fig, ax, label_bar_pairs, bar_geoms)
    save(fig, "merit_order")


# ------------------------------------------------------- 2. water-value dispatch
def water_value_dispatch():
    rng = np.linspace(0, 14 * np.pi, 400)
    t = np.linspace(0, 14, 400)
    price = 30 + 22 * np.sin(rng / 2) + 8 * np.sin(rng * 1.7 + 1)
    wv = 30.0
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ax.plot(t, price, color="#1f5fa8", lw=1.8, label="Spot price", zorder=3)
    ax.axhline(wv, color="#b30000", ls="--", lw=1.5, label="Water value", zorder=3)
    ax.fill_between(t, wv, price, where=price >= wv, color="#7fd08a", alpha=0.55,
                    interpolate=True, label="Produce (price $>$ water value)")
    ax.fill_between(t, wv, price, where=price < wv, color="#c9c9c9", alpha=0.7,
                    interpolate=True, label="Store water (price $<$ water value)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price [EUR/MWh]")
    ax.set_title("Reservoir hydropower bidding on the water value (illustrative)")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 70)
    ax.set_xticks([])
    ax.legend(loc="upper right", fontsize=9, frameon=True, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "water_value_dispatch")


# ----------------------------------------------------------- 3. market timeline
def market_timeline():
    fig, ax = plt.subplots(figsize=(9.0, 3.3))
    ax.axhline(0, color="black", lw=1.2)
    # (start, end, label, colour)
    segs = [
        (0.5, 4.2, "Day-ahead market\n(hourly auction)", "#1f5fa8"),
        (4.2, 7.8, "Intraday market\n(continuous trading)", "#2c8a3d"),
        (7.8, 10.2, "Balancing /\nreal-time\n(TSO activation)", "#e8552d"),
    ]
    for s, e, lab, col in segs:
        # inset the box within its segment so the label has clear padding
        # between the text and the rounded box edge (esp. the intraday box)
        ax.add_patch(FancyBboxPatch((s + 0.08, 0.14), e - s - 0.28, 0.72,
                     boxstyle="round,pad=0.02,rounding_size=0.08",
                     facecolor=col, edgecolor="none", alpha=0.85))
        ax.text((s + e) / 2, 0.5, lab, ha="center", va="center", color="white", fontsize=8.6)
    for xt, lab in [(4.2, "day-ahead gate\nclosure (12:00 D$-$1)"),
                    (7.8, "intraday gate\nclosure ($\\sim$1 h before)"),
                    (10.2, "operating\nhour")]:
        ax.plot([xt, xt], [-0.12, 0.0], color="black", lw=1)
        ax.text(xt, -0.2, lab, ha="center", va="top", fontsize=8.2)
    ax.annotate("", xy=(10.9, 0), xytext=(0.2, 0),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2))
    ax.text(10.9, 0.08, "time", fontsize=9)
    ax.set_xlim(0, 11.3)
    ax.set_ylim(-0.62, 1.0)
    ax.axis("off")
    ax.set_title("Temporal segmentation of the Nordic power market", fontsize=12)
    save(fig, "market_timeline")


# --------------------------------------------------- 4. Norwegian bidding zones
def bidding_zones():
    node_csv = BASE / "scenarios" / "nuclear_MD" / "data" / "system" / "node.csv"
    if not node_csv.exists():
        node_csv = BASE / "scenarios" / "baseline" / "data" / "system" / "node.csv"
    df = pd.read_csv(node_csv)
    idcol = "id" if "id" in df.columns else df.columns[0]
    df["zone"] = df[idcol].astype(str).str[:3]
    no = df[df["zone"].str.match(r"NO\d")].copy()
    colours = {"NO1": "#1f5fa8", "NO2": "#e8552d", "NO3": "#2c8a3d",
               "NO4": "#9467bd", "NO5": "#d4a017"}
    fig, ax = plt.subplots(figsize=(5.4, 6.6))
    for z, g in no.groupby("zone"):
        ax.scatter(g["lon"], g["lat"], s=70, color=colours.get(z, "0.5"),
                   edgecolor="white", linewidth=0.6, zorder=3, label=z)
        ax.text(g["lon"].mean(), g["lat"].mean(), z, fontsize=13, fontweight="bold",
                ha="center", va="center", color="black",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=colours.get(z, "0.5"), alpha=0.9),
                zorder=4)
    ax.set_xlabel("Longitude [$^\\circ$E]")
    ax.set_ylabel("Latitude [$^\\circ$N]")
    ax.set_title("Norwegian bidding zones NO1--NO5")
    ax.set_aspect(2.0)  # approx lat/lon aspect at ~62N
    ax.grid(alpha=0.25)
    save(fig, "no_bidding_zones")


def _assert_pipeline_layout(fig, ax, text_owner, box_geoms):
    """Programmatic proof that the pipeline diagram is collision-free.

    text_owner: list of (text artist, owning box key).
    box_geoms:  dict box key -> (x0, x1, y0, y1) in data coordinates.
    Asserts (i) no pair of text artists overlaps and (ii) no text artist
    overlaps a box other than the one it belongs to."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    EPS = 0.5  # px; a shared edge is not an overlap
    from matplotlib.transforms import Bbox

    def boxes_overlap(a, b):
        ix = min(a.x1, b.x1) - max(a.x0, b.x0)
        iy = min(a.y1, b.y1) - max(a.y0, b.y0)
        return ix > EPS and iy > EPS

    texts = [(t, key, t.get_window_extent(rend)) for t, key in text_owner]

    # (i) pairwise text overlap
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            (ta, _, ba), (tb, _, bb) = texts[i], texts[j]
            assert not boxes_overlap(ba, bb), \
                f"text overlap: '{ta.get_text()}' <-> '{tb.get_text()}'"

    # (ii) text over a foreign box
    box_boxes = {}
    for key, (x0, x1, y0, y1) in box_geoms.items():
        (dx0, dy0) = ax.transData.transform((x0, y0))
        (dx1, dy1) = ax.transData.transform((x1, y1))
        box_boxes[key] = Bbox([[min(dx0, dx1), min(dy0, dy1)],
                               [max(dx0, dx1), max(dy0, dy1)]])
    for t, owner, tbox in texts:
        for key, bbox in box_boxes.items():
            if key == owner:
                continue
            assert not boxes_overlap(tbox, bbox), \
                f"text '{t.get_text()}' overlaps foreign box '{key}'"
    print("  methodology_pipeline: overlap check passed "
          f"({len(texts)} text elements, {len(box_boxes)} boxes)")


# ----------------------------------------------- 5. methodology pipeline (Ch. 5)
def methodology_pipeline():
    """Sober horizontal flow diagram of the analysis chain, wrapped into two
    rows (boustrophedon) so the seven stages stay legible at text width. No
    result values appear in the figure; the [2]/[6] citations live in the
    LaTeX caption, not in the boxes."""
    # (title, detail); detail "" -> title centred alone
    stages = [
        ("Input data", "By & Skavlem grid;\nNVE demand\nprojection"),
        ("System\nconfiguration", "2050 / 2040 build"),
        ("Scenario\nconstruction", "BL, SMR1/3/6 $\\times$\nMD/IC; SMR$_{\\mathrm{NTC}}$;\nVolt set"),
        ("PowerGAMA", "sequential DC-OPF;\n30 weather years\n1991–2020 (GLPK)"),
        ("SQLite result\ndatabases", ""),
        ("Metrics", "Eqs. 5.4–5.8"),
        ("Results", "Chapter 8"),
    ]
    # box 1..4 on the top row (left->right), 5..7 on the bottom row
    # (right->left), with box 5 directly under box 4.
    top_y, bot_y = 1.5, -1.5
    xs = [0.0, 2.2, 4.4, 6.6]
    centres = [(xs[0], top_y), (xs[1], top_y), (xs[2], top_y), (xs[3], top_y),
               (xs[3], bot_y), (xs[2], bot_y), (xs[1], bot_y)]
    BW, BH = 1.92, 1.72
    CORE = 3  # index of the PowerGAMA compute box (slightly darker)

    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    text_owner, box_geoms = [], {}
    for i, ((cx, cy), (title, detail)) in enumerate(zip(centres, stages)):
        key = f"b{i}"
        face = "#dcdcdc" if i == CORE else "#f0f0f0"
        ax.add_patch(FancyBboxPatch((cx - BW / 2, cy - BH / 2), BW, BH,
                     boxstyle="round,pad=0.02,rounding_size=0.12",
                     facecolor=face, edgecolor="#333333", linewidth=1.3, zorder=2))
        box_geoms[key] = (cx - BW / 2, cx + BW / 2, cy - BH / 2, cy + BH / 2)
        if detail:
            ty, dy = cy + 0.44, cy - 0.34
            t = ax.text(cx, ty, title, ha="center", va="center", zorder=4,
                        fontsize=9.4, fontweight="bold", color="black")
            d = ax.text(cx, dy, detail, ha="center", va="center", zorder=4,
                        fontsize=7.9, color="#333333")
            text_owner += [(t, key), (d, key)]
        else:
            t = ax.text(cx, cy, title, ha="center", va="center", zorder=4,
                        fontsize=9.4, fontweight="bold", color="black")
            text_owner.append((t, key))

    def arrow(p0, p1):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=16,
                     color="#333333", lw=1.5, shrinkA=0, shrinkB=0, zorder=1))

    half = BW / 2
    for a, b in [(0, 1), (1, 2), (2, 3)]:  # top row, rightward
        arrow((centres[a][0] + half, top_y), (centres[b][0] - half, top_y))
    arrow((xs[3], top_y - BH / 2), (xs[3], bot_y + BH / 2))  # drop down
    for a, b in [(4, 5), (5, 6)]:  # bottom row, leftward
        arrow((centres[a][0] - half, bot_y), (centres[b][0] + half, bot_y))

    ax.set_xlim(-1.25, 7.85)
    ax.set_ylim(-2.75, 2.75)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Analysis pipeline of the thesis", fontsize=12)
    _assert_pipeline_layout(fig, ax, text_owner, box_geoms)
    save(fig, "methodology_pipeline")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    merit_order()
    water_value_dispatch()
    market_timeline()
    bidding_zones()
    methodology_pipeline()
    print("done ->", OUT)
