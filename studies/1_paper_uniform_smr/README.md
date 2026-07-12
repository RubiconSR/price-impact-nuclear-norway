# Study 2 — Uniform SMR Deployment in the 2050 System

Main scenarios of the IEEE conference paper. Eight scenarios combining four
nuclear deployment scales (0 / 1.5 / 4.5 / 9.0 GW) with two demand levels
(Moderate Demand 208 TWh / Increased Consumption 230 TWh). All SMRs distributed
uniformly across NO1–NO5.

## System

- Year: 2050 (NVE B2050 capacity targets)
- Hydro: 42.6 GW, Wind onshore: 8.2 GW, Wind offshore: 3.6 GW, Solar: 11.3 GW
- R6-calibrated storage_price values (from Study 1)
- 30 weather years (1991–2020)

## Scripts

| Script | Purpose |
|--------|---------|
| `setup_nuclear_MD.py` | Scales R6 baseline to 2050 MD targets and writes new CSV inputs |
| `run_nuclear_MD.py` | Runs BL/SMR1/SMR3/SMR6 under MD (208 TWh) |
| `run_nuclear_IC.py` | Runs BL/SMR1/SMR3/SMR6 under IC (230 TWh) |
| `run_all_MD.sh` | Shell wrapper for MD batch run |
| `run_all_IC.sh` | Shell wrapper for IC batch run |
| `start_IC.py` | Helper that sets up IC data symlink and launches batch |
| `plot_nuclear_MD.py` | All MD plots (zone prices, generation mix, etc.) |
| `plot_nuclear_IC.py` | All IC plots |
| `plot_energymix_and_cf.py` | Generates paper Figure 5 (generation mix) and Figure 6 (CF) |
| `plot_fig4_energy_mix_IC.py` | Generates paper Figure 4 |
| `calc_cf_table.py` | Computes SMR capacity factor table |

## Input data

- `../../scenarios/nuclear_MD/data/` — Moderate Demand inputs
- `../../scenarios/nuclear_IC/data/` — Increased Consumption inputs

## Results

SQLite databases at `../../scenarios/nuclear_MD/{BL,SMR1,SMR3,SMR6}_MD/results/`
and equivalent IC paths (not in repo — ~50 GB).

## Key findings

| | MD (208 TWh) | IC (230 TWh) |
|--|--------------|--------------|
| Baseline price | 85.7 EUR/MWh | 159.3 EUR/MWh |
| 1.5 GW SMR | 71.4 (-17%) | 118.6 (-26%) |
| 4.5 GW SMR | 45.2 (-47%) | 59.5 (-63%) |
| 9.0 GW SMR | 31.8 (-63%) | 38.4 (-76%) |
| Net export at 4.5 GW | +14.4 TWh | +8.0 TWh (flip from -15.9) |

Nuclear capacity factor degrades from 74.0% (low SMR, MD) to 50.8% (high SMR, MD)
due to price cannibalization.
