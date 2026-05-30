# Study 3 — Nuclear at Cable-Endpoint Nodes (NTC Border Placement)

Extension of Study 2: instead of distributing SMRs uniformly across NO1–NO5,
9.3 GW is concentrated at the Norwegian nodes that are direct endpoints of
interconnectors to neighbouring markets. Tests whether placement near export
cables changes the price impact and trade balance.

## Nuclear placement

| Node | Capacity | Connected to |
|------|---------:|--------------|
| NO1_5 | 1,800 MW | SE3 cables |
| NO2_1 | 1,500 MW | North Sea Link (GB) |
| NO2_4 | 2,100 MW | NorNed + NordLink (NL + DE) |
| NO2_5 | 1,500 MW | Skagerrak (DK1) |
| NO3_1 | 900 MW | SE2_4 cable |
| NO4_1 | 1,200 MW | SE1_1 + FI_1 |
| NO4_3 | 300 MW | SE2_1 |
| **Total** | **9,300 MW** | 31 × 300 MW units |

Two demand levels: MD (208 TWh) and IC (230 TWh). System base same as Study 2.

## Scripts

| Script | Purpose |
|--------|---------|
| `run_nuclear_NTC.py` | Runs SMR_NTC_MD and SMR_NTC_IC |
| `plot_NTC_v2.py` | All NTC-specific plots (cable saturation, zone prices, generation mix) |
| `plot_remaining.py`, `plot_remaining2.py` | Auxiliary plotting helpers |

## Results

| | Baseline | NTC SMR | Change |
|--|---------:|--------:|-------:|
| **MD avg price** | 101.7 EUR/MWh | 43.6 | **-57%** |
| **IC avg price** | 182.0 | 63.5 | **-65%** |
| **MD nuclear CF** | — | 68.3% | |
| **IC nuclear CF** | — | 76.5% | |
| **MD net export** | +1.1 TWh | +42.5 TWh | +41.4 |
| **IC net export** | -15.9 TWh | +35.6 TWh | +51.5 |

Cable saturation dramatically increases — most interconnectors hit >85% utilisation
under SMR_NTC. See `../../SMR_NTC_v2_results/RESULTS_REPORT.txt` for full details.

Plots are in `../../SMR_NTC_v2_results/` and individual scenario subfolders.

## Comparison with Study 2 (uniform distribution)

| | Uniform 9 GW (Study 2) | NTC 9.3 GW (Study 3) |
|--|-----------------------|----------------------|
| MD price reduction | -63% | -57% |
| IC price reduction | -76% | -65% |

Uniform distribution gives slightly stronger price suppression (consistent with
the master-thesis Study 4 finding that placement strongly affects outcome).
