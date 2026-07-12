#!/usr/bin/env python3
"""Zone price matrix (Case 1): average zonal price [EUR/MWh] for every scenario
and zone, as an annotated heatmap. Values are the verified 30-year R3 results
reported in Chapter 8 (Tables res_case1_md / res_case1_ic)."""
import numpy as np, pathlib
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = pathlib.Path(__file__).resolve().parent.parent/"overleaf"/"pictures"/"results"
zones = ["NO1","NO2","NO3","NO4","NO5"]
MD = {"BL":[157.0,67.1,99.3,27.3,77.8],"SMR1":[118.5,64.1,64.0,20.8,48.2],
      "SMR3":[82.1,63.3,37.3,13.9,29.4],"SMR6":[72.0,62.1,30.9,10.6,23.5]}
IC = {"BL":[250.2,74.8,211.6,96.6,163.2],"SMR1":[193.9,69.7,138.6,36.8,109.7],
      "SMR3":[110.9,63.6,58.6,20.6,43.7],"SMR6":[74.3,62.8,34.8,12.9,27.1]}
def panel(ax, data, title, vmax):
    rows=list(data.keys()); M=np.array([data[r] for r in rows])
    im=ax.imshow(M,cmap="RdYlGn_r",aspect="auto",vmin=0,vmax=vmax)
    ax.set_xticks(range(len(zones))); ax.set_xticklabels(zones)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v=M[i,j]; ax.text(j,i,f"{v:.0f}",ha="center",va="center",
                              color="white" if v>0.62*vmax else "black",fontsize=10)
    ax.set_title(title,fontsize=12)
    return im
fig,axes=plt.subplots(1,2,figsize=(10,3.4))
im0=panel(axes[0],MD,"Moderate Demand (208 TWh)",160)
im1=panel(axes[1],IC,"Increased Consumption (230 TWh)",250)
for ax in axes: ax.set_xlabel("Bidding zone")
axes[0].set_ylabel("Nuclear scenario")
fig.colorbar(im1,ax=axes,label="Average zonal price [EUR/MWh]",fraction=0.046,pad=0.04)
fig.savefig(OUT/"zone_price_matrix.pdf",bbox_inches="tight")
fig.savefig(OUT/"zone_price_matrix.png",dpi=150,bbox_inches="tight")
print("wrote zone_price_matrix")
