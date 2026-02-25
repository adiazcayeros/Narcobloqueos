"""
01_merge_deduplicate.py
=======================
Merges the DataInt (JSON) and Aliado (Excel) incident datasets,
standardises columns, and flags likely cross-source duplicates
using a 1 km spatial + 2-hour temporal proximity threshold.

Outputs:
    data/mexico_incidents_COMBINED_feb22-23_2026.xlsx

Usage:
    python code/01_merge_deduplicate.py
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.spatial.distance import cdist

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
RAW_DIR    = ROOT / "data" / "raw"
OUT_DIR    = ROOT / "data"
DATAINT_F  = RAW_DIR / "dataint_feb22-23_2026.json"
ALIADO_F   = RAW_DIR / "aliado_feb22-23_2026.xlsx"
OUTPUT_F   = OUT_DIR / "mexico_incidents_COMBINED_feb22-23_2026.xlsx"

# t=0: approximate onset of main activation wave
T0 = pd.Timestamp("2026-02-22 15:00:00", tz="America/Mexico_City")


# ── 1. Load DataInt ────────────────────────────────────────────────────────────
def load_dataint(path: Path) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    records = raw if isinstance(raw, list) else raw.get("incidents", raw.get("data", []))

    rows = []
    for r in records:
        rows.append({
            "Source":      "DataInt",
            "EventID":     str(r.get("id", r.get("event_id", ""))),
            "Timestamp":   pd.to_datetime(r.get("timestamp", r.get("date", "")), utc=True)
                             .tz_convert("America/Mexico_City"),
            "Latitude":    float(r.get("latitude",  r.get("lat", np.nan))),
            "Longitude":   float(r.get("longitude", r.get("lon", np.nan))),
            "State":       r.get("state", ""),
            "Municipality": r.get("municipality", r.get("city", "")),
            "Subtype":     r.get("subtype", r.get("type", "")),
            "Severity":    int(r.get("severity", 1)),
            "Description": r.get("description", r.get("summary", "")),
        })

    df = pd.DataFrame(rows)
    print(f"DataInt loaded: {len(df)} records")
    return df


# ── 2. Load Aliado ─────────────────────────────────────────────────────────────
def load_aliado(path: Path) -> pd.DataFrame:
    xl = pd.read_excel(path)

    # Normalise column names — Aliado exports vary; adjust as needed
    col_map = {
        # common Aliado export column names → our standard names
        "fecha":         "Timestamp",
        "date":          "Timestamp",
        "lat":           "Latitude",
        "latitude":      "Latitude",
        "lon":           "Longitude",
        "lng":           "Longitude",
        "longitude":     "Longitude",
        "estado":        "State",
        "state":         "State",
        "municipio":     "Municipality",
        "municipality":  "Municipality",
        "tipo":          "Subtype",
        "title":         "Subtype",
        "titulo":        "Subtype",
        "descripcion":   "Description",
        "description":   "Description",
        "severidad":     "Severity",
        "severity":      "Severity",
        "id":            "EventID",
    }
    xl.columns = [c.lower().strip() for c in xl.columns]
    xl = xl.rename(columns={k: v for k, v in col_map.items() if k in xl.columns})

    # Ensure required columns exist
    for col in ["Timestamp", "Latitude", "Longitude", "Subtype", "Description"]:
        if col not in xl.columns:
            xl[col] = np.nan if col in ("Latitude", "Longitude") else ""

    if "Severity" not in xl.columns:
        # Infer severity from subtype keywords
        xl["Severity"] = xl["Subtype"].apply(_infer_severity)

    if "EventID" not in xl.columns:
        xl["EventID"] = [f"ALI_{i:04d}" for i in range(len(xl))]

    xl["Source"] = "Aliado"
    xl["Timestamp"] = pd.to_datetime(xl["Timestamp"], utc=False, errors="coerce")
    # Localise if tz-naive
    if xl["Timestamp"].dt.tz is None:
        xl["Timestamp"] = xl["Timestamp"].dt.tz_localize("America/Mexico_City",
                                                          ambiguous="infer",
                                                          nonexistent="shift_forward")
    else:
        xl["Timestamp"] = xl["Timestamp"].dt.tz_convert("America/Mexico_City")

    xl["Latitude"]  = pd.to_numeric(xl["Latitude"],  errors="coerce")
    xl["Longitude"] = pd.to_numeric(xl["Longitude"], errors="coerce")

    df = xl[["Source", "EventID", "Timestamp", "Latitude", "Longitude",
             "State", "Municipality", "Subtype", "Severity", "Description"]].copy()
    print(f"Aliado loaded: {len(df)} records")
    return df


def _infer_severity(subtype: str) -> int:
    """Heuristic severity inference from Aliado alert text."""
    s = str(subtype).lower()
    if any(w in s for w in ("enfrentamiento", "ataque armado", "balacera", "artefacto")):
        return 3
    if any(w in s for w in ("bloqueo", "incendio", "quema")):
        return 2
    return 1


# ── 3. Compute onset hours ─────────────────────────────────────────────────────
def add_onset_hours(df: pd.DataFrame) -> pd.DataFrame:
    t0 = T0
    df["OnsetHours"] = (df["Timestamp"] - t0).dt.total_seconds() / 3600
    return df


# ── 4. Cross-source deduplication ─────────────────────────────────────────────
KM_THRESHOLD   = 1.0    # km
HOUR_THRESHOLD = 2.0    # hours
DEG_PER_KM     = 1 / 111.0  # approximate


def flag_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag likely cross-source duplicate pairs using a 1km / 2h threshold.
    Only compares DataInt rows against Aliado rows (not within-source).
    Both records in each pair are retained; DuplicateFlag=1 marks them.
    """
    di = df[df["Source"] == "DataInt"].copy().reset_index()
    al = df[df["Source"] == "Aliado"].copy().reset_index()

    di_coords = di[["Latitude", "Longitude"]].values
    al_coords = al[["Latitude", "Longitude"]].values

    # Pairwise geographic distance (degrees → km approx)
    geo_dist = cdist(di_coords, al_coords) / DEG_PER_KM  # km

    di_hours = di["OnsetHours"].values
    al_hours = al["OnsetHours"].values
    time_dist = np.abs(di_hours[:, None] - al_hours[None, :])  # hours

    pairs = []
    pair_counter = 0
    for i in range(len(di)):
        for j in range(len(al)):
            if geo_dist[i, j] <= KM_THRESHOLD and time_dist[i, j] <= HOUR_THRESHOLD:
                pair_counter += 1
                pid = f"PAIR_{pair_counter:03d}"
                pairs.append((di.at[i, "index"], al.at[j, "index"], pid))

    df["DuplicateFlag"]   = 0
    df["DuplicatePairID"] = ""

    for orig_i, orig_j, pid in pairs:
        df.at[orig_i, "DuplicateFlag"]   = 1
        df.at[orig_j, "DuplicateFlag"]   = 1
        df.at[orig_i, "DuplicatePairID"] = pid
        df.at[orig_j, "DuplicatePairID"] = pid

    n_pairs = len(pairs)
    print(f"Duplicate pairs flagged: {n_pairs} ({n_pairs * 2} records, "
          f"{100 * n_pairs * 2 / len(df):.1f}% of combined dataset)")
    return df


# ── 5. Main ────────────────────────────────────────────────────────────────────
def main():
    di = load_dataint(DATAINT_F)
    al = load_aliado(ALIADO_F)

    combined = pd.concat([di, al], ignore_index=True)
    combined = combined.sort_values("Timestamp").reset_index(drop=True)
    combined = add_onset_hours(combined)
    combined = flag_duplicates(combined)

    print(f"\nCombined dataset: {len(combined)} records total")
    print(f"  DataInt: {(combined.Source=='DataInt').sum()}")
    print(f"  Aliado:  {(combined.Source=='Aliado').sum()}")
    print(f"  Duplicate-flagged: {combined.DuplicateFlag.sum()}")
    print(f"  States covered: {combined.State.nunique()}")
    print(f"  Severity distribution:\n{combined.Severity.value_counts().sort_index()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT_F, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="Combined Incidents", index=False)
        # Summary sheet
        summary = combined.groupby(["Source", "Severity"]).size().unstack(fill_value=0)
        summary.to_excel(writer, sheet_name="Summary by Severity")

    print(f"\nSaved: {OUTPUT_F}")


if __name__ == "__main__":
    main()
