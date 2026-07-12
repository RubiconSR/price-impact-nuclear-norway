# Volts metodikk — vår tolkning

Volt/BCG-rapporten oppgir kun øvre nivå på modelloppsett. Dette dokumentet samler alt som er eksplisitt i rapporten, og markerer det som er antatt på vår side.

## Eksplisitt i rapporten

- **Modell**: Volt Power Analytics sin egen kraftmarkedsmodell. Type ikke spesifisert (sannsynligvis fundamentalmodell).
- **Geografisk omfang**: Norge (NO1–NO5) eksplisitt rapportert. Naboland og kontinent inngår implisitt i kraftbalansen.
- **Tidsoppløsning**: Time, hele perioden 2025–2050.
- **Værår**: 30 ulike værår simulert per modellår; gjennomsnitt rapporteres.
- **Forbruk 2040**: 194 TWh i Norge.
- **Forbruksforutsetning**: **Lik etterspørsel i alle tre scenarier**, unntatt fleksibel hydrogenproduksjon (+1–3 TWh ved lavere pris).
- **Havvind-plassering**: NO2 i alle scenarier.
- **SNII**: 1.5 GW i full drift fra 2031.
- **Utsira Nord**: 0.5 GW i full drift fra 2033.
- **Scenario 2 ekstra 2 GW**: Fordelt som +1.5 GW fra 2038 og +0.5 GW fra 2040 (figurtekst).
- **Subsidier (kontekst, ikke modellinput)**: 58 mrd. NOK planlagt for SNII + UN.

## Ikke eksplisitt — antakelser vi må gjøre

| Element | Volts valg (antatt) | Vår løsning |
|---------|---------------------|-------------|
| Lastvekst 2025→2040 | 139 → 194 TWh, fordeling per sone ikke oppgitt | Fordel proporsjonalt med dagens last, eller bruk NVE B2050 ned-skalert til 194 TWh |
| Naboland kraftbalanse | Trolig dynamisk modellert | Vår modell har faste profiler — kjent metodisk avvik |
| NTC-kapasiteter 2040 | Antatt dagens + kjente utvidelser | Bruk eksisterende fra By & Skavlem (R6) |
| Vannverdier | Volts egen kalibrering | Vi beholder R6 |
| OW-profil (CF, time-til-time) | Volts egen | Bruk renewables.ninja eller TYNDP 2022 for NO2-koordinater |
| Brensel- og CO2-priser | Ikke oppgitt | Beholder dine paper-verdier (gass 137.52 EUR/MWh inkl. CO2) |
| OW LCOE / fuelcost | Lav marginalkost antatt | Sett fuelcost = 0 EUR/MWh (renvariabel kost) |
| OW-tilkoblingsnode på NO2 | Ikke spesifisert | Foreslår NO2_4 (samme som NorNed/NordLink-endepunkt) |
| Hydrogen-respons (+1–3 TWh) | Implisitt fleksibel last | Modelleres som flex_load på relevant node hvis aktuelt |

## Avvik mellom Volt og PowerGAMA — forventet

Disse vil være kilder til at PowerGAMA-tallene avviker fra Volts:

1. **Stokastisk vs. deterministisk hydro**: Volt har sannsynligvis SDP-baserte vannverdier per simuleringsår; PowerGAMA bruker eksogene profiler. PowerGAMA over-dispatcher hydro i tørre værår (Golombek 2022).
2. **Naboland**: Faste profiler vs. dynamisk modellering gir ulik importrespons under høy norsk OW-produksjon.
3. **Tidsdynamikk**: Volt simulerer 2025–2050 år for år; PowerGAMA-en vår er statisk per kjøring (vi bruker 2040-snapshot).
4. **NTC-utbygging**: Volt antar trolig oppdaterte NTC frem mot 2040; vi bruker By & Skavlem-baseline.

## Konvertering NOK ↔ EUR

Rapporten oppgir tall i NOK; PowerGAMA-en din regner i EUR. Bruk:

- **8.7 NOK/EUR** (samme antakelse som Volt, jf. norske analyser 2026)
- 1 øre/kWh = 1.149 EUR/MWh

### Volt-tall i EUR/MWh

| Scenario | NO1 | NO2 | NO3 | NO4 | NO5 | Snitt |
|----------|-----|-----|-----|-----|-----|-------|
| 1        | -8.0 | -8.0 | -6.9 | -4.6 | -8.0 | -7.4  |
| 2        | -14.9 | -16.1 | -13.8 | -8.0 | -13.8 | -13.9 |

Disse blir referansepunktene for sammenligning med PowerGAMA-output.
