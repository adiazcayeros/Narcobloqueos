# mexico-cjng-feb2026

**Security incident analysis of the CJNG national response to the killing of El Mencho, February 22–23, 2026.**

Combined DataInt + Aliado (Alephri) dataset · 389 incidents · 25 states · Network disruption counterfactual

---

## Overview

On February 22, 2026, Nemesio Oseguera Cervantes ("El Mencho"), leader of the Jalisco New Generation Cartel (CJNG), was killed during a federal security operation in Tapalpa, Jalisco. Within hours, CJNG cells activated across Mexico in a coordinated national response — highway blockades, commercial attacks, and armed confrontations with security forces — that ultimately spanned 25 states, killed approximately 58–60 people, and temporarily closed major federal highways across the country.

This repository documents the analytical process used to characterise that incident wave: data collection, deduplication, spatial statistics, and a road network disruption counterfactual comparing CJNG's actual blockade pattern against the theoretically optimal disruption strategy.

---

## Repository Structure

```
mexico-cjng-feb2026/
│
├── README.md                          ← This file
├── REPORT.md                          ← Full analytical report (GitHub-readable)
│
├── data/
│   ├── mexico_incidents_COMBINED_feb22-23_2026.xlsx   ← Merged & deduplicated dataset
│   ├── README_data.md                                  ← Data dictionary
│   └── raw/
│       ├── dataint_feb22-23_2026.json                  ← Original DataInt export
│       └── aliado_feb22-23_2026.xlsx                   ← Original Aliado export
│
├── code/
│   ├── 01_merge_deduplicate.py        ← Merge DataInt + Aliado, flag duplicates
│   ├── 02_spatial_statistics.py       ← Moran's I, LISA, Knox, highway diffusion
│   ├── 03_network_analysis.py         ← Highway graph, betweenness, greedy blockade
│   ├── 04_visualisation.py            ← All figures (cluster map, network maps, stats)
│   └── requirements.txt               ← Python dependencies
│
├── figures/
│   ├── fig_cluster_map_v2.png         ← Regional incident cluster map
│   ├── fig_network1_chokepoints.png   ← Optimal chokepoints vs. actual blockades
│   ├── fig_network2_comparison.png    ← 4-panel statistical comparison
│   ├── fig1_lisa.png                  ← LISA cluster map
│   └── fig2_moran.png                 ← Moran scatterplot
│
└── docs/
    ├── mexico_incident_report_feb22-23_2026.docx        ← Full Word report
    ├── spatial_analysis_appendix_feb22-23_2026.docx     ← Spatial stats appendix
    └── network_appendix_C_feb22-23_2026.docx            ← Network analysis appendix
```

---

## Key Findings

### Scale and speed
- **389 records** across **25 states** collected from two independent platforms
- Incidents activated within **hours** of El Mencho's death with near-simultaneous onset across regions (Knox space-time ratio 1.41 at ≤2h, p<0.001)
- Three sequential waves: highway blockades (15:00–17:00 CST) → urban commercial attacks (17:00–20:00) → overnight armed clashes (20:00–04:00)

### Spatial structure
- **Global Moran's I = 0.110** (severity, p<0.001): high-severity events significantly clustered, not random
- **LISA High-High hotspot** in Jalisco–Zacatecas belt (p<0.05)
- **GDL→Tepic→Mazatlán confirmed diffusion wave** (Spearman ρ=+0.415, p=0.0002) alongside near-simultaneous national broadcast activation

### Network disruption analysis
- Highway system modelled as weighted graph: **79 nodes, 114 edges**
- CJNG achieved **+50.6% degradation** of national road network travel capacity
- This is **69.9% of the theoretically maximum disruption** achievable with the same number of blockades
- Spearman correlation between betweenness centrality and actual blockade location: **ρ=0.062, p=0.59** (not significant — blockades were not placed at optimal chokepoints)
- The largest efficiency gap is structural: the three most critical national nodes (Culiacán, Los Mochis, Navojoa) lie in **Sinaloa Cartel territory**, unreachable by CJNG

### Three distinct regional strategies
| Strategy | Regions | Signature |
|----------|---------|-----------|
| **Type I: Armed Confrontation + Infrastructure** | Jalisco, Zacatecas, Guanajuato | Direct GN engagement + blockades; highest severity |
| **Type II: Pure Highway Denial** | Tamaulipas, Baja California, Veracruz/Puebla | Exclusively highway blockades; standardised methodology |
| **Type III: Commercial Infrastructure Terror** | CDMX metro, Guerrero, Chiapas, Tabasco | OXXO/Bienestar/gas attacks; no highway component |

### Dataset limitations (documented undercounts)
| Category | Dataset | Confirmed minimum | Capture rate |
|----------|---------|------------------|--------------|
| OXXO stores | 8 | 75+ | ~10% |
| Banco del Bienestar | 15 | 51+ | ~29% |
| Toll plazas | 4–5 | 13+ | ~35% |
| Gas stations | 9 | 12–15 | ~65–75% |

---

## Quickstart

```bash
# Clone
git clone https://github.com/your-org/mexico-cjng-feb2026.git
cd mexico-cjng-feb2026

# Install Python dependencies
pip install -r code/requirements.txt

# Run the full pipeline
python code/01_merge_deduplicate.py        # produces data/mexico_incidents_COMBINED.xlsx
python code/02_spatial_statistics.py       # produces spatial stats + figures
python code/03_network_analysis.py         # produces network CSVs + greedy sequence
python code/04_visualisation.py            # produces all figures in figures/
```

Input files expected in `data/raw/`. See [`data/README_data.md`](data/README_data.md) for the full data dictionary.

---

## Data

The combined dataset (`data/mexico_incidents_COMBINED_feb22-23_2026.xlsx`) contains the following columns:

| Column | Description |
|--------|-------------|
| `Source` | DataInt or Aliado |
| `EventID` | Original platform ID |
| `Timestamp` | Event datetime (CST) |
| `Latitude`, `Longitude` | Coordinates |
| `State` | Mexican state |
| `Municipality` | Municipality (where available) |
| `Subtype` | Incident classification (bilingual) |
| `Severity` | 1 (low) to 4 (critical) |
| `Description` | Full incident description |
| `DuplicateFlag` | 1 = flagged as cross-source duplicate |
| `DuplicatePairID` | Links flagged pairs |
| `OnsetHours` | Hours since t=0 (15:00 CST Feb 22) |

---

## Methods

All analysis was performed in Python. Key libraries:

- **[PySAL](https://pysal.org/)** — spatial statistics (libpysal, esda)
- **[NetworkX](https://networkx.org/)** — graph analysis and betweenness centrality
- **[Matplotlib](https://matplotlib.org/)** + **[Shapely](https://shapely.readthedocs.io/)** — visualisation
- **pandas / numpy / scipy** — data processing and statistics

Detailed methodology in [`REPORT.md` Appendix C](REPORT.md#appendix-c-methodology-and-ai-assisted-process-note).

---

## Analytical notebooks / scripts

| Script | What it does |
|--------|-------------|
| [`01_merge_deduplicate.py`](code/01_merge_deduplicate.py) | Loads JSON (DataInt) and Excel (Aliado), standardises columns, applies 1km/2h deduplication threshold, exports combined Excel |
| [`02_spatial_statistics.py`](code/02_spatial_statistics.py) | Global Moran's I (KNN-8 + DistanceBand-250km), LISA with 999 permutations, Knox space-time test, Spearman highway diffusion, spatial lag regression |
| [`03_network_analysis.py`](code/03_network_analysis.py) | Builds Mexico federal highway graph, computes betweenness centrality, node/edge removal impact, greedy optimal blockade sequence, matches blockades to nearest node, statistical comparison |
| [`04_visualisation.py`](code/04_visualisation.py) | Cluster map, network chokepoint maps, 4-panel statistical comparison, LISA maps, Moran scatterplot |

---

## Citation

If you use this dataset or analysis, please cite:

```
Mexico CJNG Incident Analysis, February 22–23, 2026.
Combined DataInt + Aliado dataset, 389 records.
Spatial and network analysis performed with PySAL and NetworkX.
GitHub: https://github.com/your-org/mexico-cjng-feb2026
```

---

## Caveats

- Both source platforms **undercount** actual events, most severely in Jalisco where simultaneous event volume overwhelmed ingestion capacity
- Network model (79 nodes) is a **simplification** of the full Mexican highway system; secondary roads are not modelled
- Statistical findings describe the **observed dataset**, not ground truth — undercounting may suppress measured spatial autocorrelation
- All interpretations of CJNG command structure are **analytical inferences**, not established facts

---

## License

Data derived from DataInt and Aliado (Alephri) platforms. Code released under MIT. See [LICENSE](LICENSE).
