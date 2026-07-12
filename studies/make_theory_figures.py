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
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = pathlib.Path(__file__).resolve().parent.parent
OUT = BASE / "overleaf" / "pictures"
plt.rcParams.update({"font.size": 11, "axes.linewidth": 0.8})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


# ---------------------------------------------------------------- 1. merit order
def merit_order():
    # (label, width=capacity GW, marginal cost EUR/MWh, colour) -- illustrative
    blocks = [
        ("Wind & solar", 12, 0, "#7fd08a"),
        ("Nuclear (SMR)", 6, 9, "#e8552d"),
        ("Reservoir hydro", 14, 15, "#1f5fa8"),
        ("Imports", 6, 45, "#9467bd"),
        ("Gas", 6, 90, "#7f7f7f"),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    x = 0
    for lab, w, mc, col in blocks:
        ax.bar(x + w / 2, mc, width=w, color=col, edgecolor="white",
               align="center", zorder=2)
        ax.text(x + w / 2, mc + 2.5, lab, ha="center", va="bottom", fontsize=9.5, rotation=0)
        x += w
    demand = 26.0
    clearing = 15  # marginal block (reservoir hydro) at this demand
    ax.axvline(demand, color="black", ls="--", lw=1.4, zorder=3)
    ax.text(demand + 0.4, 105, "Demand", rotation=90, va="top", fontsize=10)
    ax.axhline(clearing, xmin=0, xmax=demand / x, color="#b30000", ls=":", lw=1.6, zorder=3)
    ax.annotate("Clearing price", xy=(0.5, clearing), xytext=(1, 55),
                fontsize=10, color="#b30000",
                arrowprops=dict(arrowstyle="->", color="#b30000"))
    ax.annotate("marginal unit", xy=(demand - 3, clearing), xytext=(demand - 12, 30),
                fontsize=9.5, arrowprops=dict(arrowstyle="->", color="0.3"))
    ax.set_xlabel("Cumulative available capacity [GW]")
    ax.set_ylabel("Marginal cost [EUR/MWh]")
    ax.set_title("Merit-order dispatch and market clearing (illustrative)")
    ax.set_xlim(0, x)
    ax.set_ylim(0, 115)
    ax.spines[["top", "right"]].set_visible(False)
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
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.axhline(0, color="black", lw=1.2)
    # (start, end, label, colour)
    segs = [
        (0.5, 4.2, "Day-ahead market\n(closes 12:00, day D$-$1)", "#1f5fa8"),
        (4.2, 7.8, "Intraday market\n(continuous, up to $\\sim$1 h before)", "#2c8a3d"),
        (7.8, 10.2, "Balancing / real time\n(TSO activation)", "#e8552d"),
    ]
    for s, e, lab, col in segs:
        ax.add_patch(FancyBboxPatch((s, 0.15), e - s - 0.12, 0.7,
                     boxstyle="round,pad=0.02,rounding_size=0.08",
                     facecolor=col, edgecolor="none", alpha=0.85))
        ax.text((s + e) / 2, 0.5, lab, ha="center", va="center", color="white", fontsize=9.2)
    for xt, lab in [(4.2, "gate\nclosure"), (10.0, "operating\nhour")]:
        ax.plot([xt, xt], [-0.12, 0.0], color="black", lw=1)
        ax.text(xt, -0.2, lab, ha="center", va="top", fontsize=8.5)
    ax.annotate("", xy=(10.6, 0), xytext=(0.2, 0),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2))
    ax.text(10.6, 0.08, "time", fontsize=9)
    ax.set_xlim(0, 11)
    ax.set_ylim(-0.5, 1.0)
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


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    merit_order()
    water_value_dispatch()
    market_timeline()
    bidding_zones()
    print("done ->", OUT)
