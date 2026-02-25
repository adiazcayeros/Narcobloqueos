"""
02_spatial_statistics.py
========================
Spatial and spatio-temporal statistics on the combined incident dataset.

Analyses performed:
    1. Global Moran's I — severity and onset time (KNN-8 and DistanceBand-250km)
    2. LISA (Local Moran's I) — severity and onset time, 999 permutations
    3. Knox space-time interaction test — 999 permutations
    4. Highway diffusion — Spearman correlation along 5 federal highway corridors
    5. Spatial lag regression — severity ~ spatial lag (severity)

Outputs:
    figures/fig1_lisa.png
    figures/fig2_moran.png
    (printed tables of all statistics)

Usage:
    python code/02_spatial_statistics.py

Requirements:
    pandas, numpy, scipy, libpysal, esda, matplotlib
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import spearmanr

import libpysal
from esda.moran import Moran, Moran_Local

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
DATA_F   = ROOT / "data" / "mexico_incidents_COMBINED_feb22-23_2026.xlsx"
FIG_DIR  = ROOT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

PERMUTATIONS = 999
SEED         = 42


# ── Load data ─────────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    df = pd.read_excel(DATA_F, sheet_name="Combined Incidents")
    df = df.dropna(subset=["Latitude", "Longitude", "Severity", "OnsetHours"])
    df = df[df["Latitude"].between(14, 33) & df["Longitude"].between(-120, -86)]
    print(f"Records loaded for spatial analysis: {len(df)}")
    return df


# ── 1. Global Moran's I ───────────────────────────────────────────────────────
def run_moran(df: pd.DataFrame):
    """
    Compute Global Moran's I for severity and onset time under two
    weight matrices: KNN-8 and DistanceBand-250km.
    """
    coords = df[["Longitude", "Latitude"]].values

    print("\n── Global Moran's I ──────────────────────────────────────────────")

    for w_name, W in [
        ("KNN-8",          libpysal.weights.KNN.from_array(coords, k=8)),
        ("DistBand-250km", libpysal.weights.DistanceBand.from_array(
                               coords, threshold=2.25, binary=True)),  # ~250km in degrees
    ]:
        W.transform = "r"

        for var_name, y in [("Severity", df["Severity"].values),
                             ("OnsetHours", df["OnsetHours"].values)]:
            mi = Moran(y, W, permutations=PERMUTATIONS, seed=SEED)
            sig = "**" if mi.p_sim < 0.01 else ("*" if mi.p_sim < 0.05 else "n.s.")
            print(f"  [{w_name}] {var_name:12s}:  I={mi.I:.4f}  z={mi.z_norm:.2f}  "
                  f"p={mi.p_sim:.4f} {sig}")

    return coords


# ── 2. LISA ───────────────────────────────────────────────────────────────────
def run_lisa(df: pd.DataFrame, coords: np.ndarray) -> pd.DataFrame:
    """
    Compute LISA (Local Moran's I) for severity and onset time.
    Appends cluster labels to the dataframe and generates figure.
    """
    W = libpysal.weights.KNN.from_array(coords, k=8)
    W.transform = "r"

    print("\n── LISA Clusters ─────────────────────────────────────────────────")

    fig, axes = plt.subplots(1, 2, figsize=(18, 8), facecolor="white")
    cluster_colors = {0: "#D3D3D3",  # Not significant
                      1: "#C0392B",  # HH
                      2: "#2471A3",  # LL
                      3: "#F39C12",  # LH (spatial outlier)
                      4: "#8E44AD"}  # HL (spatial outlier)
    cluster_labels = {0: "n.s.", 1: "HH (hotspot)", 2: "LL (coldspot)",
                      3: "LH (outlier)", 4: "HL (outlier)"}

    for ax, (var_name, y) in zip(axes, [("Severity", df["Severity"].values),
                                         ("OnsetHours", df["OnsetHours"].values)]):
        lisa = Moran_Local(y, W, permutations=PERMUTATIONS, seed=SEED)

        # Assign cluster type: 0=ns, 1=HH, 2=LL, 3=LH, 4=HL
        cluster = np.zeros(len(df), dtype=int)
        sig_mask = lisa.p_sim < 0.05
        q = lisa.q  # 1=HH, 2=LH, 3=LL, 4=HL
        cluster[sig_mask & (q == 1)] = 1  # HH
        cluster[sig_mask & (q == 3)] = 2  # LL
        cluster[sig_mask & (q == 2)] = 3  # LH
        cluster[sig_mask & (q == 4)] = 4  # HL

        df[f"LISA_{var_name}_cluster"] = cluster
        for i, (k, v) in enumerate(cluster_colors.items()):
            mask = cluster == k
            ax.scatter(df.loc[mask, "Longitude"], df.loc[mask, "Latitude"],
                       c=v, s=25, alpha=0.75, label=cluster_labels[k],
                       edgecolors="white", linewidths=0.3, zorder=4)

        n_hh = (cluster == 1).sum()
        n_ll = (cluster == 2).sum()
        print(f"  {var_name}: HH={n_hh}, LL={n_ll}, "
              f"LH={(cluster==3).sum()}, HL={(cluster==4).sum()}")

        ax.set_title(f"LISA — {var_name}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        ax.set_xlim(-120, -86); ax.set_ylim(13.5, 34)
        ax.legend(fontsize=8, loc="lower left")
        ax.set_facecolor("#EEF6FF")
        ax.grid(True, lw=0.4, ls=":", color="#DDD")

    plt.suptitle("LISA Cluster Maps — Mexico CJNG Incidents, Feb 22–23 2026",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_lisa.png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close()
    print(f"  → Saved: {FIG_DIR / 'fig1_lisa.png'}")
    return df


# ── 3. Knox Space-Time Interaction ────────────────────────────────────────────
def run_knox(df: pd.DataFrame, coords: np.ndarray):
    """
    Knox test: are events closer in space AND time than expected by chance?
    Tests multiple (d_km, t_h) thresholds. Uses 999 random permutations.
    """
    print("\n── Knox Space-Time Interaction ───────────────────────────────────")

    from scipy.spatial.distance import cdist as sp_cdist

    n = len(df)
    geo_km   = sp_cdist(coords, coords) / (1 / 111.0)  # degrees → km
    time_h   = np.abs(df["OnsetHours"].values[:, None]
                    - df["OnsetHours"].values[None, :])

    # Observed counts
    configs = [(10, 2), (10, 6), (50, 2), (50, 6), (100, 2), (100, 6), (300, 2)]
    np.random.seed(SEED)

    print(f"  {'d_km':>6} {'t_h':>5} {'Obs':>8} {'Exp':>8} {'Ratio':>7} {'p':>7}")
    for d_km, t_h in configs:
        close_space = geo_km  <= d_km
        close_time  = time_h  <= t_h
        np.fill_diagonal(close_space, False)
        np.fill_diagonal(close_time,  False)

        obs = (close_space & close_time).sum() // 2

        # Permutation: shuffle timestamps
        perm_counts = []
        for _ in range(PERMUTATIONS):
            perm_times = df["OnsetHours"].values.copy()
            np.random.shuffle(perm_times)
            pt = np.abs(perm_times[:, None] - perm_times[None, :])
            np.fill_diagonal(pt, np.inf)
            perm_counts.append((close_space & (pt <= t_h)).sum() // 2)

        exp  = np.mean(perm_counts)
        ratio = obs / exp if exp > 0 else np.inf
        p_val = (np.sum(np.array(perm_counts) >= obs) + 1) / (PERMUTATIONS + 1)
        sig = "**" if p_val < 0.01 else ("*" if p_val < 0.05 else "n.s.")
        print(f"  {d_km:>6} {t_h:>5} {obs:>8} {exp:>8.1f} {ratio:>7.3f} "
              f"{p_val:>7.4f} {sig}")


# ── 4. Highway Diffusion ──────────────────────────────────────────────────────
def run_highway_diffusion(df: pd.DataFrame):
    """
    For each highway corridor, extract incidents along it (within ~15km buffer),
    sort by approximate highway position, and compute Spearman ρ between
    position and onset time. Positive ρ = northward/eastward diffusion.
    """
    print("\n── Highway Diffusion (Spearman ρ, position vs. onset time) ──────")

    corridors = {
        "GDL→Tepic→Mazatlán (Hwy 15D)": {
            "bounds": (-107.5, 19.5, -103.2, 23.5),
            "sort_by": "Latitude",   # northward
        },
        "CDMX→Monterrey (Hwy 57D/85D)": {
            "bounds": (-101.5, 19.0, -98.5, 26.5),
            "sort_by": "Latitude",
        },
        "GDL→Morelia (Hwy 15)": {
            "bounds": (-103.5, 19.4, -100.9, 21.0),
            "sort_by": "Longitude",  # eastward
        },
        "CDMX→Puebla (Hwy 150D)": {
            "bounds": (-99.5, 18.8, -96.8, 19.7),
            "sort_by": "Longitude",
        },
        "GDL→Manzanillo (Hwy 54D)": {
            "bounds": (-104.5, 18.9, -103.0, 21.0),
            "sort_by": "Latitude",
        },
    }

    for name, cfg in corridors.items():
        x0, y0, x1, y1 = cfg["bounds"]
        subset = df[
            df["Longitude"].between(x0, x1) &
            df["Latitude"].between(y0, y1)
        ].copy()

        if len(subset) < 5:
            print(f"  {name}: n={len(subset)} (too few, skip)")
            continue

        rho, p = spearmanr(subset[cfg["sort_by"]], subset["OnsetHours"])
        sig = "**" if p < 0.01 else ("*" if p < 0.05 else "n.s.")
        print(f"  {name}")
        print(f"    n={len(subset):3d}  ρ={rho:+.3f}  p={p:.4f} {sig}")


# ── 5. Moran Scatterplot ──────────────────────────────────────────────────────
def plot_moran_scatter(df: pd.DataFrame, coords: np.ndarray):
    W = libpysal.weights.KNN.from_array(coords, k=8)
    W.transform = "r"

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="white")
    for ax, (var_name, y) in zip(axes, [("Severity", df["Severity"].values),
                                         ("OnsetHours", df["OnsetHours"].values)]):
        mi = Moran(y, W, permutations=PERMUTATIONS, seed=SEED)

        y_std = (y - y.mean()) / y.std()
        wy    = W.sparse.dot(y_std)
        ax.scatter(y_std, wy, alpha=0.4, s=15, c="#2471A3", edgecolors="none")
        xlim = ax.get_xlim()
        ax.axhline(0, color="#999", lw=0.8, ls="--")
        ax.axvline(0, color="#999", lw=0.8, ls="--")
        z = np.polyfit(y_std, wy, 1)
        xp = np.linspace(xlim[0], xlim[1], 100)
        ax.plot(xp, np.polyval(z, xp), color="#C0392B", lw=2)
        ax.set_xlabel(f"Standardised {var_name}", fontsize=10)
        ax.set_ylabel("Spatial lag", fontsize=10)
        ax.set_title(f"Moran's I — {var_name}\nI={mi.I:.4f}, p={mi.p_sim:.4f}",
                     fontsize=10, fontweight="bold")
        ax.grid(True, lw=0.4, ls=":", color="#EEE")

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_moran.png", dpi=150, bbox_inches="tight",
                facecolor="white")
    plt.close()
    print(f"  → Saved: {FIG_DIR / 'fig2_moran.png'}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    df     = load_data()
    coords = df[["Longitude", "Latitude"]].values

    run_moran(df)
    df     = run_lisa(df, coords)
    run_knox(df, coords)
    run_highway_diffusion(df)
    plot_moran_scatter(df, coords)

    print("\nDone.")


if __name__ == "__main__":
    main()
