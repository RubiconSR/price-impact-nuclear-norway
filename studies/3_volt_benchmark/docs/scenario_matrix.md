# Scenariematrise

## 4 × 3 full matrise (12 celler)

Rader: kjernekraft (0, 1.5, 4.5, 9 GW)
Kolonner: havvind (0, 2, 4 GW)

|              | OW0 (0 GW) | OW1 (2 GW)   | OW2 (4 GW)   |
|--------------|------------|--------------|--------------|
| **N0** (0 GW SMR)  | V0         | V1           | V2           |
| **N1** (1.5 GW SMR) | N1         | N1+V1        | N1+V2        |
| **N3** (4.5 GW SMR) | N3         | N3+V1        | N3+V2        |
| **N6** (9 GW SMR)   | N6         | N6+V1        | N6+V2        |

### Cellebeskrivelse

- **V0**: Volts Scenario 0 — referanse uten OW eller nuclear
- **V1, V2**: Volts Scenario 1 og 2, replikert i PowerGAMA
- **N1, N3, N6**: Kun nuclear, ingen OW (matcher dine eksisterende paper-scenarier, men i 2040-system med 194 TWh — ikke direkte sammenliknbare med paperets 2050-tall)
- **Kombinerte celler**: Det interessante for masterbidraget — interaksjon mellom OW og nuclear

### SMR-konfigurasjon (samme som paper)

- 300 MW per enhet
- Min produksjon 30 MW
- Marginalkost 9.37 EUR/MWh
- Tilgjengelighet 0.90
- Vedlikehold uke 20–24, staggered mellom soner
- Fordelt jevnt NO1–NO5 (medmindre annet bestemt med veileder)

| Nivå | Total kapasitet | Per sone | Totale enheter |
|------|----------------|----------|----------------|
| N1   | 1.5 GW         | 1 × 300 MW | 5  |
| N3   | 4.5 GW         | 3 × 300 MW | 15 |
| N6   | 9.0 GW         | 6 × 300 MW | 30 |

## Reduksjon ved tidspress

Hvis 12 celler er for mye: drop **N6**-raden, kjør 3 × 3 = 9 celler. Det dekker fortsatt bredden.

Minimum-versjon (ved hard tidsbeskjær): 2 × 3 = 6 celler — Volt-baselinen + N3 (paperets sentrale SMR-nivå) krysset med OW.

## Compute-budsjett

- 1 PowerGAMA-kjøring 30 år: ~2 timer
- 12 celler sekvensielt: ~24 timer
- 4 parallelle kjøringer på Mac: ~6 timer total
- **Strategi**: Kjør V0/V1/V2 først (3 timer), valider mot Volt-tall, deretter resten
