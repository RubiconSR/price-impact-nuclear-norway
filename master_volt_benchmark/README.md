# Master Volt Benchmark

PowerGAMA-replikasjon av Volt/BCG "Mer vind til havs"-rapporten (april 2026) +
kjernekraft-scenarier for direkte sammenligning med havvind.

## Status

Alle målscenarier ferdig. Klar for analyse og figurer.

## Scenarier (alle 2040, 194 TWh, 30 værår 1991-2020)

| Navn | Innhold | Plassering | NO snitt (EUR/MWh) |
|------|---------|------------|---------------------:|
| N0_OW0 | V0 baseline | — | 60.70 |
| N0_OW1 | Volt S1: 2 GW havvind | NO2_2 | 59.57 |
| N0_OW2 | Volt S2: 4 GW havvind | NO2_2 | 54.78 |
| N1_OW0 | 2.1 GW SMR | NO2_2 | 53.27 |
| N2_OW0 | 3.9 GW SMR | NO2_2 | 42.28 |
| N1jevnt_OW0 | 2.1 GW SMR | Jevnt fordelt NO1-NO5 | 42.27 |

Arkiverte (første kjøring med OW på NO2_1, før vi flyttet til NO2_2 pga
eksport-lekkasje til GB-kabelen):
- N0_OW1_NO2_1, N0_OW2_NO2_1, N1_OW0_NO2_1

## Mappestruktur

```
master_volt_benchmark/
├── README.md              # Denne filen
├── data/                  # Input (symlinked fra nuclear_MD/data)
├── docs/                  # Metodikk-notater
│   ├── volt_metodikk.md
│   └── scenario_matrix.md
├── scripts/
│   ├── run_volt_benchmark.py    # Hovedskript — kjør én eller alle celler
│   ├── extract_zone_prices.py   # Volumvektet sonepris (Hjelmeland Eq. 5)
│   ├── diagnose_volt.py         # Brancheflyt + produksjon + eksport
│   └── plot_results.py          # PowerGAMA plotAreaPrice
├── results/
│   ├── *.sqlite           # PowerGAMA-resultater per scenario (~5 GB hver)
│   ├── diagnostics.txt    # Diagnose-output (brancheflyt, produksjon)
│   └── logs/              # Kjøringslogger og solver-logger
└── plots/                 # PNG-figurer per scenario
```

## Bruk

Kjør én scenariocelle:
```bash
python scripts/run_volt_benchmark.py N0 OW1
```

Hent ut sonepriser fra ferdige scenarier:
```bash
python scripts/extract_zone_prices.py
```

Generer plotAreaPrice for et scenario:
```bash
python scripts/plot_results.py N0_OW1
```

## Hovedfunn (foreløpig)

1. **Lokalt på NO2 stemmer vår modell med Volt** innenfor 1-3 EUR/MWh.
2. **Nasjonalt snitt er ~halvparten av Volts** prisreduksjon — mest sannsynlig
   pga. mer restriktiv intern norsk transmisjon i By & Skavlem-NTC.
3. **Kjernekraft (3.9 GW) gir 3× sterkere prisreduksjon enn havvind (4 GW)** ved
   samme plassering, fordi CF er nesten dobbelt så høy.
4. **Plassering dominerer over teknologi**: 2.1 GW SMR jevnt fordelt gir samme
   nasjonale prisreduksjon som 3.9 GW SMR konsentrert på NO2.
5. **NO4 (Nord-Norge) er flaskehalset**: prisen endres knapt uavhengig av
   plassering og teknologi sør i landet. Avvik fra Volt (de får −4.6 til −8.0).
