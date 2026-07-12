# Study 1 — Calibration of PowerGAMA against historical 2024 prices

Iterative calibration of the `storage_price` parameter for Norwegian hydropower
reservoirs (NO1–NO5) so simulated zonal prices match the observed 2024 spot
prices (excluding VAT). Six iterations were run, settling on **R6** as the
final calibration used in all subsequent studies.

## Scripts

| Script | Purpose |
|--------|---------|
| `run_baseline.py` | R0 — first uncalibrated baseline |
| `run_r3_2020.py` | R3 — calibration against single weather year 2020 (representative of 2024) |
| `run_r3_30yr.py` | R3 — extended to 30-year run |
| `run_r4.py` | R4 — branch-capacity calibration |
| `run_r5.py` | R5 — single-year `storage_price` calibration |
| `run_r5_30yr.py` | R5 — 30-year run |
| `run_r6.py` | **R6 — final calibration (used in Studies 2, 3, 4)** |
| `analyze_baseline.py` | Result analysis (zonal prices, energy mix) |
| `validate_baseline.py` | Validation vs. historical 2024 spot prices |
| `plot_baseline_results.py` | Generic baseline plots |
| `plot_fig1_validation.py` | Generates paper Figure 2 (validation plot) |

## Input data

Located at `../../scenarios/baseline/data/`.

## Results

SQLite databases at `../../scenarios/baseline/results/` (not in repo — ~30 GB).
Each file is one calibration iteration:
- `powergama_baseline_1991_2020.sqlite` (R0)
- `powergama_r3_1991_2020.sqlite` (R3)
- `powergama_r4_1991_2020.sqlite` (R4)
- `powergama_r5_2010.sqlite` (R5 single year)
- `powergama_r5_1991_2020.sqlite` (R5 full)
- `powergama_r6_1991_2020.sqlite` (R6 — final)

## Final R6 storage_price values per zone (EUR/MWh)

| Zone | R6 |
|------|----|
| NO1 | 8.0 |
| NO2 | 18.5 |
| NO3 | 7.0 |
| NO4 | 23.0 |
| NO5 | 27.0 |

These values are written into `scenarios/baseline/data/system/generator.csv` and
inherited by all 2050 and 2040 scenarios.
