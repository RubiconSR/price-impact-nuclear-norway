# Master Thesis Structure

**Title**: The Price Impact of Nuclear Energy on the Norwegian Electricity Market

Following the structure of By & Skavlem (2025), *Investigating Different Energy
Pathways: A Techno-Economic Analysis of the Nordic Power System* — same
supervisors, same department, same modelling tool.

---

## Front matter

- Title page (NTNU template)
- Abstract (English)
- Sammendrag (Norwegian)
- Preface (acknowledgements, signature line)
- Table of Contents
- List of Figures
- List of Tables
- List of Abbreviations

---

## 1 Introduction (~8–10 pages)

- 1.1 Background and Motivation
  - Norway's hydropower system (~88 % of generation)
  - Rising demand to 2050 (NVE projections, data centres, hydrogen)
  - Climate change and hydrological uncertainty
  - Nuclear power debate in Norway (Kjernekraftutvalget 2026, IEA 2026)
- 1.2 Objective
  - Research question: how does nuclear deployment affect Norwegian zonal
    electricity prices, capacity factors, and trade balance?
  - Sub-questions: placement sensitivity, comparison with offshore wind
- 1.3 PowerGAMA (brief introduction)
- 1.4 Contribution
  - Three contributions: 2050 SMR analysis (paper), 2040 Volt benchmark,
    direct nuclear vs offshore wind comparison
- 1.5 Structure
- 1.6 Sustainable Development Goal (NTNU template requirement)

---

## Part I — Theory (~30 pages)

### 2 The Power System
- 2.1 The Electricity Grid (AC/DC, generators, loads, transmission)
- 2.2 The Norwegian and Nordic Power System (NO1–NO5, SE1–SE4, FI, DK)
- 2.3 Basic Mathematical Formulation (DC power flow, nodal pricing)

### 3 The Norwegian Power Market
- 3.1 Historical Background and Market Liberalization
- 3.2 Market Coupling with Europe (NTC, interconnectors)
- 3.3 Bidding Zones and Real-Time Balancing

### 4 Nuclear Power in Power Systems
- 4.1 Conventional Reactors vs Small Modular Reactors (SMR)
- 4.2 Nuclear in Hydro-Dominated Systems (Hjelmeland et al.)
- 4.3 Price Cannibalization Mechanism
- 4.4 Cost Structure and Capacity Factor

### 5 Power Market Modelling
- 5.1 Optimization Models
- 5.2 Simulation Models
- 5.3 Equilibrium Models
- 5.4 PowerGAMA (detailed)
- 5.5 EMPS (Hjelmeland's tool)
- 5.6 IFE-TIMES-Norway
- 5.7 Comparative Analysis — PowerGAMA vs EMPS vs IFE-TIMES

---

## Part II — Methodology (~25 pages)

### 6 Methodology
- 6.1 Power System Modelling in PowerGAMA
- 6.2 Model Modifications and Tool Development
  - Week-based water value lookup
  - Generator ramping constraints
  - Nuclear MSO (maintenance) representation
  - `appsi_highs` solver integration
- 6.3 Inputs and Outputs
  - Input: node, branch, dcbranch, generator, consumer CSV
  - Time series: 30 weather years 1991–2020
  - Output: SQLite databases (nodal prices, generation, storage, flows)
- 6.4 Data Sources
  - NVE LA2025
  - Hjelmeland et al. (2026)
  - By & Skavlem (2025)
  - Volt/BCG (2026)
  - Renewables.ninja
  - ENTSO-E TYNDP
- 6.5 Volume-Weighted Zonal Price (Hjelmeland Eq. 5)
- 6.6 Consumer Cost Calculation and NOK Conversion

---

## Part III — Case Studies & Results (~80 pages)

### 7 Validation Study (Calibration of the 2024 Baseline)
*Maps to: studies/0_calibration/*

- 7.1 Model Configuration (system data, 2024 reference)
- 7.2 Calibration Process (R0 → R3 → R5 → R6, iterative `storage_price` tuning)
- 7.3 Final Validation vs Historical 2024 Spot Prices
- 7.4 Key Insights and Adjustments
- 7.5 R6 Calibration Used in All Subsequent Studies

### 8 Case Studies 2050
*Maps to: studies/1_paper_uniform_smr/ + studies/2_ntc_border/*

- 8.1 Common System Configuration (NVE B2050 capacity targets)
- 8.2 Case A: Baseline (no nuclear) — MD (208 TWh) and IC (230 TWh)
- 8.3 Case B: Low SMR Deployment (1.5 GW, 5 × 300 MW uniformly distributed)
- 8.4 Case C: Moderate SMR Deployment (4.5 GW, 15 × 300 MW)
- 8.5 Case D: High SMR Deployment (9.0 GW, 30 × 300 MW)
- 8.6 Case E: NTC Border Placement (9.3 GW at cable endpoints)

### 9 Case Studies 2040
*Maps to: studies/3_volt_benchmark/*

- 9.1 Common System Configuration (Volt's framework, 194 TWh)
- 9.2 Case V0: Baseline (no offshore wind, no nuclear)
- 9.3 Case V1: 2 GW Offshore Wind on NO2 (Volt Scenario 1 replication)
- 9.4 Case V2: 4 GW Offshore Wind on NO2 (Volt Scenario 2 replication)
- 9.5 Case N1: 2.1 GW SMR on NO2 (capacity-matched to V1)
- 9.6 Case N2: 3.9 GW SMR on NO2 (capacity-matched to V2)
- 9.7 Case N1-distributed: 2.1 GW SMR uniformly across NO1–NO5
- 9.8 Archived Cases on NO2_1 (placement sensitivity demonstration)

### 10 Results
- 10.1 System Outlooks (capacity mix per case)
- 10.2 2050 Results — Uniform SMR Distribution (paper main)
  - 10.2.1 Zonal Prices under MD
  - 10.2.2 Zonal Prices under IC
  - 10.2.3 Generation Mix and Hydraulic Substitution
  - 10.2.4 Capacity Factor and Price Cannibalization
  - 10.2.5 Trade Balance and the Importer → Exporter Shift
- 10.3 2050 Results — NTC Border Placement
  - 10.3.1 Zonal Prices and Cable Saturation
  - 10.3.2 Comparison with Uniform Distribution
- 10.4 2040 Results — Volt Benchmark
  - 10.4.1 V0 Baseline vs Volt Reference
  - 10.4.2 V1, V2: PowerGAMA vs Volt Original Numbers
  - 10.4.3 NO2-Local vs National Discrepancy
- 10.5 2040 Results — Nuclear vs Offshore Wind
  - 10.5.1 Direct Comparison at Same Node and Capacity
  - 10.5.2 Per-GW and Per-TWh Effectiveness
- 10.6 2040 Results — Placement Sensitivity
  - 10.6.1 Concentrated NO2_2 vs Uniform NO1–NO5
  - 10.6.2 Archived NO2_1 Runs: Export Leakage to UK
- 10.7 Consumer Cost Savings (mrd NOK/year)
  - Comparison with Volt/BCG published numbers (12.5 / 23.4 mrd)
- 10.8 System Stress Tests (optional — dry year, dunkelflaute)

### 11 Discussion
- 11.1 Scenario Analysis (cross-cutting findings)
- 11.2 Comparison with Hjelmeland EMPS Results
- 11.3 Comparison with Volt/BCG (methodological differences)
- 11.4 Comparison with IFE-TIMES-Norway
- 11.5 PowerGAMA Adequacy for Norwegian Analysis
- 11.6 Water Value Calibration (R6 robustness)
- 11.7 Placement Effect Implications for Energy Policy
- 11.8 Limitations
  - Deterministic vs stochastic hydropower
  - Fixed generation profiles for neighbouring countries
  - Simplified nuclear plant representation
  - NTC assumptions

### 12 Conclusion and Future Work
- 12.1 Conclusion
  - Six key findings consolidated
- 12.2 Future Work
  - Stochastic hydropower inflows
  - Flexible nuclear operation (load-following)
  - Endogenous transmission expansion
  - Detailed economic analysis (NPV, LCOE, capacity payments)

---

## References

---

## Appendices

- **A — GitHub Repository**
  - Link to https://github.com/RubiconSR/price-impact-nuclear-norway
  - Structure overview
  - How to reproduce results

- **B — Model**
  - Hydrological inflow profiles for Norwegian zones
  - Water value curves R6
  - Generator parameters

- **C — Case Studies**
  - Detailed input data per case
  - 2050 capacity mix tables
  - 2040 demand distribution per zone

- **D — Additional Results**
  - Per-zone detailed price tables
  - Per-scenario reservoir filling
  - Per-scenario branch flows
  - Cable saturation tables

- **E — IEEE Conference Paper**
  - Full text of the submitted paper as appendix

---

## Mapping: Studies → Chapters

| Repo study | Thesis chapter |
|-----------|----------------|
| `studies/0_calibration/` | Ch 7 (Validation Study) |
| `studies/1_paper_uniform_smr/` | Ch 8.2–8.5 (Case Studies 2050) + Ch 10.2 (Results) |
| `studies/2_ntc_border/` | Ch 8.6 + Ch 10.3 |
| `studies/3_volt_benchmark/` | Ch 9 (Case Studies 2040) + Ch 10.4–10.6 |

---

## Writing order (recommended)

1. **Ch 7 — Validation Study** — data is ready, calibration story is clear
2. **Ch 8 — Case Studies 2050** — straightforward (from paper)
3. **Ch 10.2 — 2050 Results** — adapt from paper
4. **Ch 9 — Case Studies 2040** — new material, needs scenario tables
5. **Ch 10.4–10.6 — 2040 Results** — main new contribution
6. **Ch 11 — Discussion** — synthesise after results
7. **Ch 6 — Methodology** — write once results are clear
8. **Ch 2–5 — Theory chapters** — literature-heavy, save for later
9. **Ch 1 — Introduction** — write last, frames everything
10. **Ch 12 — Conclusion** — write last

---

## Estimated length

- Front matter: ~10 pages
- Ch 1: 8 pages
- Part I (theory): 30 pages
- Part II (methodology): 25 pages
- Part III (cases + results): 80 pages
- Discussion: 10 pages
- Conclusion: 5 pages
- References: 5–7 pages
- Appendices: 25–40 pages

**Total: ~200 pages** (consistent with NTNU master thesis norms — By & Skavlem
was 170+ pages including appendices)
