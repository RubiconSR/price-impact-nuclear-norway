# The Price Impact of Nuclear Energy on the Norwegian Electricity Market

Master's thesis source code — NTNU Department of Electric Energy.

Author: SR

## Overview

This repository contains the source code, input data, and figures from the
master's thesis. The analysis uses PowerGAMA (sequential optimal power flow)
on the Nordic power system with 30 years of historical weather data
(1991–2020), and is organised into four self-contained studies.

## Repository structure

```
.
├── studies/                        # Thematic studies (per case + calibration/robustness)
│   ├── 0_calibration/              # R0–R6 baseline calibration vs 2024 prices
│   ├── 1_paper_uniform_smr/        # Case 1: BL/SMR1/3/6 × MD/IC
│   ├── 2_ntc_border/               # Case 2: SMRs at cable-endpoint nodes
│   ├── 3_volt_benchmark/           # Case 3: Volt benchmark + OW vs SMR
│   ├── 4_sensitivity_no1_ntc/      # NO1 transmission-capacity sensitivity
│   └── 5_robustness/               # Hydrological robustness + figure scripts
│
├── scenarios/                      # Input data + results (SQLite gitignored)
│   ├── baseline/data/              # Calibration inputs
│   ├── nuclear_MD/data/            # 2050 Moderate Demand inputs
│   └── nuclear_IC/data/            # 2050 Increased Consumption inputs
│
├── IEEE/                           # Paper LaTeX + figures
├── README.md                       # This file
└── .gitignore                      # Excludes SQLite, venv, large profiles
```

## The four studies

| # | Study | Purpose | Year |
|---|-------|---------|------|
| 1 | Calibration | Iteratively tune `storage_price` to match observed 2024 zonal prices. Output: R6 calibration used in all subsequent studies | — |
| 2 | Uniform SMR 2050 | 8 main paper scenarios: 0/1.5/4.5/9 GW SMR × MD/IC demand, SMRs uniformly distributed NO1–NO5 | 2050 |
| 3 | NTC border placement | Same 9.3 GW SMR concentrated at cable-endpoint nodes (NSL, NordLink, NorNed, Skagerrak, SE-cables). Tests export-cable interaction | 2050 |
| 4 | Volt benchmark 2040 | Replicate Volt/BCG offshore-wind scenarios (S0/S1/S2) in PowerGAMA + parallel nuclear scenarios. Direct OW vs SMR comparison at same node | 2040 |

Each study has its own `README.md` with detailed methodology and results.

## How to run

Each study's scripts assume the project root is **three levels up** from the
script:
```python
BASE_DIR = pathlib.Path(__file__).parent.parent.parent
```

So invoke scripts from anywhere:
```bash
python studies/0_calibration/run_baseline.py
python studies/1_paper_uniform_smr/run_nuclear_MD.py
python studies/2_ntc_border/run_nuclear_NTC.py
python studies/3_volt_benchmark/scripts/run_volt_benchmark.py N0 OW1
```

## Requirements

- Python 3.12
- PowerGAMA 1.5.1 with the modifications from
  [Zynecut/NordicNuclearAnalysis](https://github.com/Zynecut/NordicNuclearAnalysis)
  copied into `venv/lib/python3.12/site-packages/powergama/`
- HiGHS or GLPK solver
- Time-series profile data (1991–2020 hourly, ~144 MB): not in repo, fetch from
  NordicNuclearAnalysis upstream

Each 30-year simulation takes ~3 hours on a single CPU core. The
full study set required ~75 hours of compute across 25 scenarios.

## Key references

- Hjelmeland & Nøland (2026), *Power Market Impacts of Nuclear Energy in
  Hydropower-Dominated Power Systems*, SSRN preprint
- By & Skavlem (2025), *Investigating Different Energy Pathways*, MSc thesis NTNU
- Svendsen & Spro (2016), *PowerGAMA*, Journal of Renewable and Sustainable Energy
- Volt Power Analytics & BCG (2026), *Mer vind til havs — mindre å betale hjemme*
- NVE LA2025 (2025), *Long-Term Electricity Market Analysis*

## Notes

- SQLite results are generated locally and excluded from the repo (114 GB total).
- Calibration: R6 storage_price values per zone are persisted in
  `scenarios/baseline/data/system/generator.csv` and inherited by all studies.
- Modified PowerGAMA source files: upstream
  [NordicNuclearAnalysis](https://github.com/Zynecut/NordicNuclearAnalysis)
  under `sourceCodeUpdates/`.
