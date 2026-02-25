"""
04_visualisation.py
===================
Generates all figures for the report:

    figures/fig_cluster_map_v2.png          Regional incident cluster map
    figures/fig_network1_chokepoints.png    Optimal chokepoints vs actual blockades
    figures/fig_network2_comparison.png     4-panel statistical comparison

Requires outputs from 02_spatial_statistics.py and 03_network_analysis.py.

Usage:
    python code/04_visualisation.py

Requirements:
    pandas, numpy, scipy, networkx, matplotlib, shapely
"""

import pickle
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from scipy.spatial.distance import cdist
from scipy.stats import spearmanr
import networkx as nx
from shapely.geometry import Polygon, MultiPoint
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
DATA_F  = ROOT / "data" / "mexico_incidents_COMBINED_feb22-23_2026.xlsx"
GRAPH_F = ROOT / "data" / "mexico_road_graph.pkl"
BC_F    = ROOT / "data" / "betweenness.csv"
EBC_F   = ROOT / "data" / "edge_betweenness.csv"
GREEDY_F= ROOT / "data" / "greedy_blockade.csv"
NV_F    = ROOT / "data" / "network_vs_blockades.csv"
NF_F    = ROOT / "data" / "node_criticality.csv"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


# ── Mexico border polygons (hand-built from geographic coordinates) ────────────
def get_mexico_polygons():
    baja = Polygon([
        (-117.08,32.53),(-116.60,32.47),(-116.10,31.82),(-115.55,30.82),
        (-114.75,29.73),(-113.39,27.25),(-112.50,25.52),(-111.35,24.01),
        (-110.27,23.02),(-109.79,22.46),(-109.42,22.99),(-110.59,24.27),
        (-112.10,26.01),(-113.39,27.95),(-114.62,29.78),(-115.47,30.98),
        (-116.60,32.40),(-117.08,32.53),
    ]).buffer(0)
    main = Polygon([
        (-117.08,32.53),(-114.81,32.49),(-111.08,31.33),(-108.22,31.33),
        (-106.53,31.78),(-104.68,29.91),(-103.33,28.96),(-100.62,28.00),
        (-97.36,25.87), (-97.13,25.97), (-97.29,22.79),(-94.87,18.23),
        (-92.73,18.47), (-90.46,21.39), (-87.47,21.44),(-88.82,15.73),
        (-90.41,17.82), (-92.47,17.97), (-94.53,16.20),(-98.75,16.17),
        (-103.51,18.89),(-105.73,20.40),(-107.67,21.48),(-109.42,22.99),
        (-109.95,22.87),(-117.08,32.53),
    ]).buffer(0)
    return [main, baja]


def draw_mexico(ax):
    for geom in get_mexico_polygons():
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for p in polys:
            ax.fill(*p.exterior.xy, color="#F0EDE6", zorder=1, alpha=1.0)
            ax.plot(*p.exterior.xy, color="#AAAAAA",  lw=0.8,   zorder=2)
    ax.set_facecolor("#D6EAF8")


# ── Cluster definitions ────────────────────────────────────────────────────────
CLUSTERS = {
    "Jalisco Metro":     {"color": "#C0392B", "states": ["Jalisco"]},
    "Michoacán":         {"color": "#7D3C98", "states": ["Michoacan", "Michoacán"]},
    "Zacatecas":         {"color": "#D35400", "states": ["Zacatecas"]},
    "Guanajuato":        {"color": "#1A6EA8", "states": ["Guanajuato"]},
    "Edo. México/CDMX":  {"color": "#117A65", "states": ["Estado de Mexico","Estado de México","Ciudad de Mexico","CDMX"]},
    "Veracruz/Puebla":   {"color": "#1A6EA8", "states": ["Veracruz","Puebla"]},
    "Tamaulipas":        {"color": "#148F77", "states": ["Tamaulipas"]},
    "Baja California":   {"color": "#B7950B", "states": ["Baja California"]},
    "Guerrero":          {"color": "#922B21", "states": ["Guerrero"]},
    "Oaxaca/Chiapas":    {"color": "#E74C3C", "states": ["Oaxaca","Chiapas"]},
}


def assign_cluster(state: str) -> str:
    s = str(state).strip()
    for cname, cfg in CLUSTERS.items():
        if any(st.lower() in s.lower() for st in cfg["states"]):
            return cname
    return "Other"


# ── Figure 1: Cluster map ─────────────────────────────────────────────────────
def fig_cluster_map(df: pd.DataFrame):
    df = df.copy()
    df["cluster"] = df["State"].apply(assign_cluster)
    df_geo = df.dropna(subset=["Latitude", "Longitude"])

    fig, ax = plt.subplots(figsize=(22, 15), facecolor="white")
    draw_mexico(ax)
    ax.set_xlim(-120, -86); ax.set_ylim(13.5, 33.8)
    ax.grid(True, color="#DDDDDD", lw=0.5, ls=":", alpha=0.7)

    # Convex hulls per cluster
    for cname, cfg in CLUSTERS.items():
        pts = df_geo[df_geo["cluster"] == cname][["Longitude", "Latitude"]].values
        if len(pts) < 3:
            continue
        try:
            hull = MultiPoint(pts).convex_hull.buffer(0.18)
            cx, cy = hull.centroid.x, hull.centroid.y
            expanded = Polygon([(cx + 1.35*(x-cx), cy + 1.35*(y-cy))
                                for x, y in hull.exterior.coords]).buffer(0)
            xs, ys = expanded.exterior.xy
            ax.fill(xs, ys, color=cfg["color"], alpha=0.12, zorder=3)
            ax.plot(xs, ys, color=cfg["color"], lw=1.8, ls="--", alpha=0.55, zorder=4)
        except Exception:
            pass

    # Events
    size_map = {1: 18, 2: 35, 3: 90, 4: 220}
    for cname, cfg in CLUSTERS.items():
        sub = df_geo[df_geo["cluster"] == cname]
        if sub.empty:
            continue
        sizes = sub["Severity"].map(size_map).fillna(35).values
        ax.scatter(sub["Longitude"], sub["Latitude"],
                   s=sizes, c=cfg["color"], alpha=0.85,
                   edgecolors="white", linewidths=0.5, zorder=6)

    # Labels
    cluster_lpos = {
        "Jalisco Metro":    (-105.8, 21.2),
        "Michoacán":        (-103.0, 18.9),
        "Zacatecas":        (-100.2, 22.5),
        "Guanajuato":       (-100.4, 21.8),
        "Edo. México/CDMX": (-97.5,  20.2),
        "Veracruz/Puebla":  (-95.0,  20.8),
        "Tamaulipas":       (-97.5,  26.8),
        "Baja California":  (-118.5, 31.5),
        "Guerrero":         (-101.5, 16.8),
        "Oaxaca/Chiapas":   (-92.5,  15.5),
    }
    for cname, cfg in CLUSTERS.items():
        sub = df_geo[df_geo["cluster"] == cname]
        if sub.empty:
            continue
        lx, ly = cluster_lpos.get(cname, (sub["Longitude"].mean(), sub["Latitude"].mean()))
        cx, cy = sub["Longitude"].mean(), sub["Latitude"].mean()
        ax.plot([cx, lx], [cy, ly], color=cfg["color"], lw=1.0, alpha=0.7, zorder=7)
        ax.text(lx, ly, f"{cname}\n({len(sub)})",
                fontsize=9.5, fontweight="bold", color="#1a1a1a",
                bbox=dict(boxstyle="round,pad=0.5", fc="white", ec=cfg["color"],
                          lw=2.0, alpha=0.95),
                ha="center", va="center", zorder=10)

    # Diffusion arrow GDL→Tepic→Mazatlán
    ax.annotate("", xy=(-106.4, 23.2), xytext=(-103.35, 20.67),
                arrowprops=dict(arrowstyle="->", color="#2C3E50",
                                lw=2.5, connectionstyle="arc3,rad=0.15"))
    ax.text(-105.6, 21.8, "Diffusion\nwave →", fontsize=8.5, color="#2C3E50",
            fontweight="bold", rotation=55, ha="center")

    ax.set_title("Mexico Security Incidents — February 22–23, 2026\n"
                 "Regional clusters · Dot size = severity · "
                 "Arrow = GDL→Tepic→Mazatlán diffusion wave (ρ=+0.42, p<0.001)",
                 fontsize=13, fontweight="bold", color="#1A1A2E")
    ax.set_xlabel("Longitude", fontsize=9, color="#555")
    ax.set_ylabel("Latitude",  fontsize=9, color="#555")
    ax.tick_params(labelsize=8, colors="#999")
    for sp in ax.spines.values(): sp.set_edgecolor("#CCC")

    legend_patches = [mpatches.Patch(color=v["color"], label=k)
                      for k, v in CLUSTERS.items()]
    ax.legend(handles=legend_patches, ncol=2, loc="lower left",
              fontsize=8.5, framealpha=0.97, facecolor="white", edgecolor="#CCC")

    plt.tight_layout()
    out = FIG_DIR / "fig_cluster_map_v2.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  → {out}")


# ── Figure 2: Network chokepoints map ─────────────────────────────────────────
def fig_network_chokepoints(G, nodes, bc_df, ebc_df, blockades_df):
    pos = {n: (nodes[n][2], nodes[n][1]) for n in G.nodes()}
    cmap = plt.cm.YlOrRd
    max_ebc = ebc_df["edge_betweenness"].max()

    fig, axes = plt.subplots(1, 2, figsize=(24, 13), facecolor="white")
    titles = ["Optimal chokepoints (betweenness centrality)",
              "Actual CJNG blockades (Feb 22–23)"]
    show_blockades = [False, True]

    for ax, title, show_b in zip(axes, titles, show_blockades):
        draw_mexico(ax)
        ax.set_xlim(-120, -86); ax.set_ylim(13.5, 34)
        ax.grid(True, color="#E0E0E0", lw=0.4, ls=":", alpha=0.7)

        for _, row in ebc_df.iterrows():
            u, v = row["u"], row["v"]
            if u not in pos or v not in pos: continue
            intensity = row["edge_betweenness"] / max_ebc
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=cmap(0.15 + 0.85*intensity),
                    lw=0.6 + 3.5*intensity, alpha=0.75, zorder=4,
                    solid_capstyle="round")

        max_bc = bc_df["betweenness"].max()
        for _, row in bc_df.iterrows():
            n = row["node"]
            if n not in pos: continue
            intensity = row["betweenness"] / max_bc
            ax.scatter(*pos[n], s=30+320*intensity,
                       c=[cmap(0.1+0.9*intensity)], zorder=6,
                       edgecolors="white", linewidths=0.8)
            if row["betweenness"] > 0.08:
                ax.text(pos[n][0]+0.15, pos[n][1]+0.12, row["name"],
                        fontsize=7.5, fontweight="bold", color="#222",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                  ec="none", alpha=0.75), zorder=10)

        if show_b:
            ax.scatter(blockades_df["Longitude"], blockades_df["Latitude"],
                       s=22, c="#1A5276", alpha=0.55, linewidths=0, zorder=8)
        else:
            for _, row in bc_df.nlargest(8, "betweenness").iterrows():
                if row["node"] in pos:
                    ax.scatter(*pos[row["node"]], s=500, c="none",
                               edgecolors="#C0392B", linewidths=2.5, zorder=12)
            ax.scatter([], [], s=200, c="none", edgecolors="#C0392B",
                       linewidths=2.5, label="Top-8 optimal chokepoints")
            ax.legend(loc="lower left", fontsize=8.5)

        sm = ScalarMappable(cmap=cmap, norm=Normalize(0, max_ebc))
        sm.set_array([])
        cb = plt.colorbar(sm, ax=ax, shrink=0.45, pad=0.02, aspect=20)
        cb.set_label("Edge betweenness centrality", fontsize=8)
        cb.ax.tick_params(labelsize=7)
        ax.set_title(title, fontsize=12, fontweight="bold", color="#1A1A2E")
        ax.tick_params(labelsize=8, colors="#999")
        for sp in ax.spines.values(): sp.set_edgecolor("#CCC")

    fig.suptitle("Federal Highway Network — Optimal Chokepoints vs. Actual CJNG Blockades",
                 fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = FIG_DIR / "fig_network1_chokepoints.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  → {out}")


# ── Figure 3: 4-panel comparison ─────────────────────────────────────────────
def fig_comparison(G, nodes, bc_df, ebc_df, greedy_df, nv_df, blockades_df):
    BLUE = "#2471A3"; RED = "#C0392B"; GREEN = "#1E8449"
    pos = {n: (nodes[n][2], nodes[n][1]) for n in G.nodes()}

    # Node frequency from actual blockades
    node_ids    = list(nodes.keys())
    node_coords = np.array([[nodes[n][1], nodes[n][2]] for n in node_ids])
    D = cdist(blockades_df[["Latitude","Longitude"]].values, node_coords)
    blockades_df = blockades_df.copy()
    blockades_df["nearest_node"] = [node_ids[i] for i in D.argmin(axis=1)]
    nf = blockades_df["nearest_node"].value_counts().reset_index()
    nf.columns = ["node", "blockade_count"]
    nf["name"] = nf["node"].map(lambda n: nodes[n][0])

    bc_df = bc_df.merge(nf[["node","blockade_count"]], on="node", how="left")
    bc_df["blockade_count"] = bc_df["blockade_count"].fillna(0)

    fig, axes = plt.subplots(2, 2, figsize=(20, 14), facecolor="white")

    # Panel A
    ax = axes[0, 0]
    rho, p = spearmanr(bc_df["betweenness"], bc_df["blockade_count"])
    ax.scatter(bc_df["betweenness"], bc_df["blockade_count"],
               s=55, c=BLUE, alpha=0.65, edgecolors="white", lw=0.5)
    for _, row in bc_df.iterrows():
        if row["blockade_count"] >= 6 or row["betweenness"] > 0.20:
            ax.annotate(row["name"], (row["betweenness"], row["blockade_count"]),
                        fontsize=8, xytext=(5,3), textcoords="offset points",
                        color="#111", fontweight="bold")
    z  = np.polyfit(bc_df["betweenness"], bc_df["blockade_count"], 1)
    xp = np.linspace(0, bc_df["betweenness"].max(), 100)
    ax.plot(xp, np.polyval(z, xp), color=RED, lw=2, ls="--", alpha=0.8)
    sig = f"p={p:.2f} (n.s.)" if p > 0.05 else f"p={p:.3f} **"
    ax.set_title(f"A.  Network Importance vs. Actual Blockades\nSpearman ρ = {rho:.3f},  {sig}",
                 fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Betweenness centrality"); ax.set_ylabel("Actual CJNG blockades")
    ax.grid(True, lw=0.5, ls=":", color="#EEE")
    for sp in ax.spines.values(): sp.set_edgecolor("#DDD")

    # Panel B
    ax = axes[0, 1]
    top12_opt  = bc_df.nlargest(12, "betweenness").reset_index(drop=True)
    top12_opt_set  = set(top12_opt["node"])
    top12_cjng_set = set(nf.head(12)["node"])
    overlap12 = top12_opt_set & top12_cjng_set
    y_pos = np.arange(12)
    opt_norm  = (top12_opt["betweenness"] / top12_opt["betweenness"].max()).values
    cjng_bc   = top12_opt["node"].map(dict(zip(nf["node"], nf["blockade_count"]))).fillna(0).values
    cjng_norm = cjng_bc / nf["blockade_count"].max()
    ax.barh(y_pos+0.20, opt_norm,  0.38, color=RED,  alpha=0.70, label="Optimal (betweenness)")
    ax.barh(y_pos-0.20, cjng_norm, 0.38, color=BLUE, alpha=0.70, label="Actual CJNG")
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{i+1}. {r['name']}" for i, r in top12_opt.iterrows()], fontsize=9)
    ax.set_xlabel("Normalised score"); ax.legend(fontsize=9, loc="lower right")
    ax.set_title("B.  Top-12 Optimal vs. Actual Blockade Zones\n(✓ = CJNG also hit)",
                 fontsize=9.5, fontweight="bold")
    ax.set_xlim(0, 1.22)
    ax.grid(True, axis="x", lw=0.5, ls=":", color="#EEE")
    for sp in ax.spines.values(): sp.set_edgecolor("#DDD")
    for i, row in top12_opt.iterrows():
        if row["node"] in overlap12:
            ax.text(1.14, i, "✓", color=GREEN, fontsize=13, va="center", fontweight="bold")

    # Panel C
    ax = axes[1, 0]
    def total_km_pen(Gt, n_orig):
        if not nx.is_connected(Gt):
            comp = [len(c) for c in nx.connected_components(Gt)]
            pu = n_orig*(n_orig-1) - sum(s*(s-1) for s in comp)
            ap = dict(nx.all_pairs_dijkstra_path_length(Gt, weight="km"))
            return sum(ap[u][v] for u in ap for v in ap[u] if u != v) + pu*3000
        ap = dict(nx.all_pairs_dijkstra_path_length(Gt, weight="km"))
        return sum(ap[u][v] for u in ap for v in ap[u] if u != v)

    n_orig   = G.number_of_nodes()
    baseline = total_km_pen(G, n_orig)

    cjng_order = nf.head(12)["node"].tolist()
    G_cjng = G.copy()
    cjng_cum = [0]
    for nn in cjng_order:
        if nn in G_cjng.nodes(): G_cjng.remove_node(nn)
        cjng_cum.append(100*(total_km_pen(G_cjng, n_orig)-baseline)/baseline)

    opt_cum = [0] + greedy_df["cumulative_pct"].tolist()
    ax.plot(range(len(opt_cum)),  opt_cum,  color=RED,  lw=2.5, marker="o", ms=7, label="Optimal greedy")
    ax.plot(range(len(cjng_cum)), cjng_cum, color=BLUE, lw=2.5, marker="s", ms=7, ls="--", label="Actual CJNG")
    nm = min(len(opt_cum), len(cjng_cum))
    ax.fill_between(range(nm), opt_cum[:nm], cjng_cum[:nm], alpha=0.10, color=RED, label="Strategic gap")
    n8 = min(8, len(opt_cum)-1, len(cjng_cum)-1)
    ax.annotate(f"n=8:\nOptimal +{opt_cum[n8]:.0f}%\nCJNG   +{cjng_cum[n8]:.0f}%\n(70% efficiency)",
                xy=(n8, cjng_cum[n8]), xytext=(n8-3, cjng_cum[n8]+10),
                fontsize=8.5, color="#222",
                arrowprops=dict(arrowstyle="->", color="#999", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#CCC", alpha=0.95))
    ax.set_xlabel("Nodes blocked"); ax.set_ylabel("Network degradation (%)")
    ax.set_title("C.  Cumulative Network Degradation\nOptimal vs. Actual CJNG Sequence",
                 fontsize=10.5, fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, lw=0.5, ls=":", color="#EEE")
    for sp in ax.spines.values(): sp.set_edgecolor("#DDD")

    # Panel D: map
    ax = axes[1, 1]
    draw_mexico(ax)
    ax.set_xlim(-120, -86); ax.set_ylim(13.5, 34)
    ax.grid(True, color="#E0E0E0", lw=0.4, ls=":", alpha=0.6)
    for u, v in G.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0],pos[v][0]], [pos[u][1],pos[v][1]],
                    color="#CCCCCC", lw=0.8, alpha=0.6, zorder=3)
    for n in G.nodes():
        if n in pos:
            ax.scatter(*pos[n], s=20, c="#BBBBBB", zorder=4, edgecolors="white", lw=0.3)

    missed    = top12_opt_set - top12_cjng_set
    hit       = top12_opt_set & top12_cjng_set
    cjng_only = top12_cjng_set - top12_opt_set

    for n in cjng_only:
        if n not in pos: continue
        ax.scatter(*pos[n], s=180, c=BLUE, zorder=6, edgecolors="white", lw=1.0, alpha=0.75)
        ax.text(pos[n][0]+0.15, pos[n][1]+0.12, nodes[n][0], fontsize=7, color=BLUE,
                fontweight="bold", bbox=dict(fc="white", ec="none", alpha=0.7,
                boxstyle="round,pad=0.15"), zorder=10)
    for n in missed:
        if n not in pos: continue
        ax.scatter(*pos[n], s=260, c="none", edgecolors=RED, lw=2.8, zorder=7)
        ax.scatter(*pos[n], s=90,  c=RED,    zorder=7, alpha=0.25)
        ax.text(pos[n][0]+0.15, pos[n][1]-0.28, nodes[n][0], fontsize=8, color=RED,
                fontweight="bold", bbox=dict(fc="white", ec=RED, alpha=0.92,
                boxstyle="round,pad=0.25", lw=1.2), zorder=11)
    for n in hit:
        if n not in pos: continue
        ax.scatter(*pos[n], s=260, c=GREEN, zorder=7, edgecolors="white", lw=1.5, marker="D")
        ax.text(pos[n][0]+0.15, pos[n][1]+0.12, nodes[n][0], fontsize=7.5, color=GREEN,
                fontweight="bold", bbox=dict(fc="white", ec="none", alpha=0.7,
                boxstyle="round,pad=0.15"), zorder=10)

    leg_els = [
        mpatches.Patch(color=GREEN, label=f"Optimal & hit by CJNG ({len(hit)})"),
        mpatches.Patch(facecolor="white", edgecolor=RED, linewidth=2,
                       label=f"Optimal — CJNG missed ({len(missed)})"),
        mpatches.Patch(color=BLUE, alpha=0.75, label=f"CJNG-only, not optimal ({len(cjng_only)})"),
    ]
    ax.legend(handles=leg_els, loc="lower left", fontsize=8.5,
              framealpha=0.97, facecolor="white", edgecolor="#CCC")
    ax.set_title("D.  Geographic Map of Strategic Alignment\nGreen=optimal+hit, Red=missed optimal, Blue=CJNG non-optimal",
                 fontsize=9.5, fontweight="bold")
    ax.tick_params(labelsize=8, colors="#999")
    for sp in ax.spines.values(): sp.set_edgecolor("#CCC")

    plt.suptitle("Counterfactual Blockade Analysis — Strategic Efficiency of CJNG Road Network Disruption",
                 fontsize=13, fontweight="bold", color="#1A1A2E", y=1.005)
    plt.tight_layout(h_pad=2.5, w_pad=2.5)
    out = FIG_DIR / "fig_network2_comparison.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  → {out}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    df = pd.read_excel(DATA_F, sheet_name="Combined Incidents")
    df_geo = df.dropna(subset=["Latitude", "Longitude"])
    blockades_df = df_geo[
        df_geo["Subtype"].str.contains("Blockade|Bloqueo", case=False, na=False)
    ].copy()

    with open(GRAPH_F, "rb") as f:
        G, nodes = pickle.load(f)

    bc_df    = pd.read_csv(BC_F)
    ebc_df   = pd.read_csv(EBC_F)
    greedy_df= pd.read_csv(GREEDY_F)

    print("Generating figures...")
    fig_cluster_map(df_geo)
    fig_network_chokepoints(G, nodes, bc_df, ebc_df, blockades_df)
    fig_comparison(G, nodes, bc_df, ebc_df, greedy_df, None, blockades_df)
    print("Done.")


if __name__ == "__main__":
    main()
