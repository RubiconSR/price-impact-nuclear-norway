# The Price Impact of Nuclear Energy on the Norwegian Electricity Market

Master's thesis source code — NTNU Department of Electric Energy.

Author: SR

## Overview

This repository contains all the source code and scripts used to produce the
results in the master's thesis. The analysis uses PowerGAMA (sequential optimal
power flow) on the Nordic power system with 30 years of historical weather data
(1991–2020).

The work is divided into two phases:

### Phase 1 — IEEE conference paper (submitted)
2050 system analysis with 8 SMR deployment scenarios under moderate and high
demand growth. Files: `run_nuclear_MD.py`, `run_nuclear_IC.py`,
`run_nuclear_NTC.py`, `setup_nuclear_MD.py`, `plot_nuclear_*.py`, `IEEE/`.

### Phase 2 — Master extensions (this thesis)
- 2040 benchmark against the Volt/BCG offshore wind report
- Direct nuclear vs. offshore wind comparison in the same modelling framework
- Placement sensitivity analysis (uniform vs. concentrated SMR deployment)

Files: `master_volt_benchmark/`

## Repository structure

```
.
├── IEEE/                       # Paper LaTeX and figures
├── scenarios/                  # Phase 1 input data (CSV)
│   ├── baseline/data/system/
│   ├── nuclear_MD/data/system/  # 2050 Moderate Demand inputs
│   └── nuclear_IC/data/system/  # 2050 High Demand inputs
├── master_volt_benchmark/      # Phase 2 (master extensions)
│   ├── scripts/                # All Volt benchmark scripts
│   ├── docs/                   # Methodology notes, scenario matrix
│   ├── plots/                  # Generated figures
│   └── README.md               # Phase 2 documentation
├── SMR_NTC_v2_results/         # SMR_NTC border placement results
├── run_*.py                    # Simulation entry points
├── plot_*.py                   # Plot generation scripts
└── setup_nuclear_MD.py         # Phase 1 system construction
```

## Reproducing results

### Requirements
- Python 3.12
- PowerGAMA 1.5.1 (with the modifications from
  [NordicNuclearAnalysis](https://github.com/Zynecut/NordicNuclearAnalysis)
  applied to `venv/lib/python3.12/site-packages/powergama/`)
- HiGHS or GLPK solver
- Time series profile data (1991–2020 hourly): not included due to size
  (~144 MB), available from NordicNuclearAnalysis

### Phase 1 example
```bash
python setup_nuclear_MD.py
python run_nuclear_MD.py
python plot_nuclear_MD.py
```

### Phase 2 example
```bash
python master_volt_benchmark/scripts/run_volt_benchmark.py N0 OW0
python master_volt_benchmark/scripts/extract_zone_prices.py
python master_volt_benchmark/scripts/plot_volt_comparison.py
```

Each simulation takes ~3 hours on a single core for the 30-year horizon
(262,968 hourly time steps).

## Key references

- Hjelmeland & Nøland (2026), *Power Market Impacts of Nuclear Energy in
  Hydropower-Dominated Power Systems*, SSRN preprint
- By & Skavlem (2025), *Investigating Different Energy Pathways*, MSc thesis NTNU
- Svendsen & Spro (2016), *PowerGAMA*, Journal of Renewable and Sustainable Energy
- Volt Power Analytics & BCG (2026), *Mer vind til havs — mindre å betale hjemme*
- NVE LA2025 (2025), *Long-Term Electricity Market Analysis*

## Notes

- Results databases (`*.sqlite`) are generated locally and excluded from this
  repository due to size (114 GB total across all scenarios).
- Reservoir-based water values are calibrated to observed 2024 zonal prices
  through three iterations (R3 used in Phase 1, R6 in Phase 2).
- Modified PowerGAMA source files are in the upstream
  [NordicNuclearAnalysis](https://github.com/Zynecut/NordicNuclearAnalysis) repo
  under `sourceCodeUpdates/`.
