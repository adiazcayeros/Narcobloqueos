# Data Dictionary

## Combined Dataset: `mexico_incidents_COMBINED_feb22-23_2026.xlsx`

**Coverage:** February 22, 2026 08:00 CST — February 23, 2026 08:00 CST  
**Total records:** 389 (251 DataInt + 138 Aliado)  
**Deduplicated estimate:** ~373 unique events (32 cross-source pairs flagged)  
**Geographic scope:** 25 Mexican states

---

### Columns

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `Source` | string | Platform of origin: `DataInt` or `Aliado` | Both |
| `EventID` | string | Original platform record identifier | Both |
| `Timestamp` | datetime | Event datetime in CST (UTC-6). DataInt timestamps are precise; Aliado timestamps are alert-receipt time, which may lag the event by minutes to ~1 hour. | Both |
| `Latitude` | float | Decimal degrees, WGS84. DataInt: intersection-level precision. Aliado: some records use municipality centroids (±10–20 km error). | Both |
| `Longitude` | float | Decimal degrees, WGS84 (negative = west) | Both |
| `State` | string | Mexican state name (Spanish). Standardised to full state names across both sources. | Both |
| `Municipality` | string | Municipality name where available. More complete in DataInt. Many Aliado records have municipality-only coordinates. | Both |
| `Subtype` | string | Incident classification. DataInt uses English: "Narco Blockade", "Business Attack", "Clash with Security Forces", "Public Building Attack", "Attack on Civilians", "Intimidation Messages", "Mass Grave Discovery". Aliado uses Spanish alert titles. | Both |
| `Severity` | integer | Severity on a 1–4 scale. DataInt provides explicit values. Aliado severity inferred from subtype keywords and alert priority. **1** = Low (blockade, minor incident). **2** = Moderate (business attack, escalating blockade). **3** = High (armed clash with casualties, VBIED). **4** = Critical (mass casualty event, direct engagement with command). | Both |
| `Description` | string | Full incident description. DataInt descriptions are bilingual (EN + ES). Aliado descriptions are Spanish only, typically shorter. | Both |
| `DuplicateFlag` | integer | **1** = record flagged as a probable cross-source duplicate based on geographic proximity (within 1 km) and temporal proximity (within 2 hours). **0** = not flagged. Both records of each duplicate pair are retained. | Derived |
| `DuplicatePairID` | string | ID linking the two records in a duplicate pair (e.g., `PAIR_001`). Empty for non-flagged records. | Derived |
| `OnsetHours` | float | Hours elapsed since t=0, defined as 15:00 CST February 22, 2026 — the approximate time of first confirmed incidents. Negative values indicate incidents before t=0 (morning activity). Used for temporal diffusion analysis. | Derived |

---

### Severity Scale Reference

| Level | Label | Typical incident types |
|-------|-------|----------------------|
| 1 | Low | Single vehicle fire, tire spikes, isolated blockade, minor arson |
| 2 | Moderate | Multi-vehicle blockade, business fire, armed group sighting |
| 3 | High | Armed clash with security forces (casualties), car bomb, coordinated multi-site attack |
| 4 | Critical | Mass casualty event, ambush of security units, major command operation |

---

### Known Data Quality Issues

**Undercount by category (documented in report Section 5):**

| Category | Dataset count | Confirmed minimum | Estimated capture rate |
|----------|--------------|-------------------|----------------------|
| OXXO stores | 8 | 75+ | ~10% |
| Banco del Bienestar | 15 | 51+ | ~29% |
| Toll plazas (casetas) | 4–5 | 13+ | ~35% |
| Gas stations | 9 | 12–15 | ~65–75% |

**Jalisco systematic undercount:** Both platforms experienced ingestion saturation in Jalisco on February 22 due to the volume of simultaneous events (estimated 250+ blockades in Jalisco alone). The combined dataset captures a higher proportion of armed clashes and critical-severity incidents than commercial attacks.

**Banco del Bienestar naming mismatch:** DataInt uses "Bank of Wellbeing" / "Bank of Well-being" in English descriptions. Searching for "Bienestar" returns near-zero DataInt matches. Cross-referencing the Aliado Title column (which uses "Banco del Bienestar") is required for a complete count.

**Timestamp precision:** Aliado alerts reflect the time the alert was dispatched by C3ntro, not necessarily the time of the underlying event. In rapidly escalating situations, this lag can be 30–90 minutes. DataInt timestamps are generally closer to event time but also derive from monitoring reports rather than direct observation.

**Coordinate precision:** Approximately 20–25% of Aliado records have coordinates at the municipality centroid rather than the incident location. This affects spatial analysis (LISA, Knox) for those records but is not correctable without additional sourcing.

---

### Source Platform Notes

**DataInt:**  
Commercial security intelligence platform providing real-time incident monitoring across Mexico. Records in this dataset were collected via Python scraping (requests, BeautifulSoup) with rate limiting. DataInt classifies incidents on a 1–4 severity scale and provides bilingual descriptions. Coverage is strongest for highway incidents and armed clashes; weakest for commercial attacks in high-tempo situations.

**Aliado (Alephri):**  
Security intelligence platform sourcing data from C3ntro (Centro de Control, Comando, Comunicaciones y Cómputo) municipal security command-and-control systems across western Mexico, supplemented by Aliado patrol network alerts. Coverage is strongest in Jalisco, Michoacán, and Guanajuato. Records were obtained via Excel export. Alert titles are in Spanish and use standardised CJNG incident vocabulary.

---

### t=0 Definition

`t=0` is defined as **15:00 CST, February 22, 2026** — the approximate time at which the first confirmed blockades and vehicle fires began appearing simultaneously across Jalisco, Michoacán, Estado de México, Tamaulipas, and Sinaloa. This coincides with the period immediately following news of El Mencho's death becoming widely circulated. Individual records before t=0 (negative `OnsetHours`) represent morning activity from February 22 that predates the main activation wave.
