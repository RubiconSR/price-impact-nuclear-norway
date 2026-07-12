# Study 5 — NO1 NTC Sensitivity (BL_MD doubled NO1↔NO2)

Tester om NO1's høye 2050-pris (€157 sonesnitt / €223 last-vektet) skyldes
unscaled intern transmisjon. Dobler kapasiteten på NO1↔NO2-korridoren og
rekjører BL_MD med ellers identisk system.

## Bakgrunn (oppdaget i diagnose_no1.py)

- NO2_1→NO1_4 (620 MW) er mettet **56.9 %** av tiden i BL_MD
- **95.5 %** av NO1's høypristimer (>€100) sammenfaller med metning på minst én importkabel
- NO1 har **53 % demand-vekst** fra dagens til 2050, men NTC er uendret

## Hva som endres

| Branch | Standard | Sensitivitet (2×) |
|--------|---------:|------------------:|
| NO2_1→NO1_3 | 367 MW | 734 MW |
| **NO2_1→NO1_4** | **620 MW** | **1240 MW** |
| NO1_3→NO2_3 | 239 MW | 478 MW |
| NO1_4→NO2_3 | 631 MW | 1262 MW |
| NO1_5→NO2_3 | 533 MW | 1066 MW |
| **Total NO1↔NO2** | **2390 MW** | **4780 MW** |

Alt annet (NO1↔NO3 = 1000 MW, NO1↔NO5 = 2964 MW, NO1↔SE3 = 1822 MW,
demand, generatorer, kalibrering R6) er identisk med BL_MD.

## Scenario-ID

- `BL_MD_NTC2x` — eneste nye kjøring

## Forventet kjøretid

GLPK, 30 værår × 8 760 timer = 262 968 tidssteg ≈ 3 timer CPU.

## Hva sammenligningen viser

Hvis NO1-prisen faller betydelig (f.eks. €157 → ~€100), bekrefter det at
mest av NO1-anomalien er en transmisjonsartefakt.
Hvis den knapt endres, er det demand/produksjon-begrenset.
