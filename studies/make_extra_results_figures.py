#!/usr/bin/env python3
"""Two extra results figures from the verified Chapter-8 values:
(1) net export across all eight scenarios (importer->exporter flip),
(2) Norwegian generation-mix progression under MD (hydraulic substitution)."""
import numpy as np, pathlib
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = pathlib.Path(__file__).resolve().parent.parent/"overleaf"/"pictures"/"results"

# (1) Net export -- Table res_case1_summary
scen=["BL","SMR1","SMR3","SMR6"]; x=np.arange(4); w=0.38
md=[1.1,7.5,14.4,19.7]; ic=[-15.9,-5.8,8.0,16.1]
fig,ax=plt.subplots(figsize=(7.4,4.2))
ax.axhline(0,color="black",lw=0.8)
b1=ax.bar(x-w/2,md,w,label="Moderate Demand (208 TWh)",color="#2c7fb8",edgecolor="black",lw=0.5)
b2=ax.bar(x+w/2,ic,w,label="Increased Consumption (230 TWh)",color="#e08a3c",edgecolor="black",lw=0.5)
ax.bar_label(b1,fmt="%+.1f",fontsize=9,padding=2); ax.bar_label(b2,fmt="%+.1f",fontsize=9,padding=2)
ax.set_xticks(x); ax.set_xticklabels(["BL","SMR1\n(1.5 GW)","SMR3\n(4.5 GW)","SMR6\n(9.0 GW)"])
ax.set_ylabel("Net export [TWh/yr]"); ax.set_title("Norwegian net export vs nuclear deployment")
ax.axhspan(-20,0,color="#f2dede",alpha=0.4,zorder=0); ax.axhspan(0,22,color="#dff0d8",alpha=0.4,zorder=0)
ax.text(3.4,-13,"net importer",ha="right",color="#a94442",fontsize=9)
ax.text(3.4,18,"net exporter",ha="right",color="#3c763d",fontsize=9)
ax.set_ylim(-20,22); ax.legend(loc="upper left",fontsize=9); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"net_export.pdf",bbox_inches="tight"); fig.savefig(OUT/"net_export.png",dpi=150,bbox_inches="tight")
print("wrote net_export")

# (2) Generation mix MD -- Table res_spill
nuc=[0,9.7,24.3,40.1]; hyd=[166.7,164.3,158.3,149.5]; vre=[40.7,40.1,38.8,37.3]; spill=[4.4,6.7,12.6,21.4]
fig,ax=plt.subplots(figsize=(7.4,4.6)); x=np.arange(4); w=0.6
ax.bar(x,hyd,w,label="Hydro + run-of-river",color="#1f5fa8",edgecolor="white")
ax.bar(x,vre,w,bottom=hyd,label="Variable renewables",color="#2c8a3d",edgecolor="white")
ax.bar(x,nuc,w,bottom=np.array(hyd)+np.array(vre),label="Nuclear (SMR)",color="#e8552d",edgecolor="white")
# spilled inflow as hatched marker above
tot=np.array(hyd)+np.array(vre)+np.array(nuc)
ax.plot(x,np.array(hyd),"o--",color="#0d2b4f",ms=4,lw=1,label="Hydro+RoR trend")
for xi,s in zip(x,spill): ax.text(xi,tot[xi]+3,f"spill {s:.1f}",ha="center",fontsize=8,color="#555")
ax.set_xticks(x); ax.set_xticklabels(["BL","SMR1","SMR3","SMR6"])
ax.set_ylabel("Annual generation [TWh/yr]"); ax.set_ylim(0,270)
ax.set_title("Norwegian generation mix under moderate demand")
ax.legend(loc="upper right",fontsize=8,ncol=2); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT/"generation_mix_progression_MD.pdf",bbox_inches="tight"); fig.savefig(OUT/"generation_mix_progression_MD.png",dpi=150,bbox_inches="tight")
print("wrote generation_mix_progression_MD")
