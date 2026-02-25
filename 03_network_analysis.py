"""
03_network_analysis.py
======================
Models Mexico's federal highway system as a weighted undirected graph
and computes road network disruption metrics to create a counterfactual
optimal blockade strategy.

Analyses performed:
    1. Build Mexico federal highway graph (79 nodes, 114 edges)
    2. Betweenness centrality (node and edge, km-weighted)
    3. Node removal impact — Δ total pairwise travel (km)
    4. Greedy sequential optimal blockade (top-20 nodes)
    5. Match actual CJNG blockades to nearest network nodes
    6. Statistical comparison: actual vs. optimal

Outputs:
    data/node_criticality.csv
    data/edge_criticality.csv
    data/betweenness.csv
    data/edge_betweenness.csv
    data/greedy_blockade.csv
    data/network_vs_blockades.csv

Usage:
    python code/03_network_analysis.py

Requirements:
    pandas, numpy, scipy, networkx
"""

import pickle
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path
from scipy.spatial.distance import cdist
from scipy.stats import spearmanr

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
DATA_F  = ROOT / "data" / "mexico_incidents_COMBINED_feb22-23_2026.xlsx"
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. Build highway graph ────────────────────────────────────────────────────
def build_graph() -> tuple[nx.Graph, dict]:
    """
    Returns (G_undirected, nodes_dict).
    nodes_dict: {node_id: (name, lat, lon)}
    """
    nodes = {
        # Northern Border
        "TIJ": ("Tijuana",        32.53, -117.04), "MXL": ("Mexicali",       32.66, -115.47),
        "ENS": ("Ensenada",       31.87, -116.60), "SLK": ("San Luis RC",     32.47, -114.78),
        "NGL": ("Nogales",        31.30, -110.94), "AGP": ("Agua Prieta",     31.33, -109.55),
        "JRZ": ("Cd. Juárez",     31.73, -106.49), "OJG": ("Ojinaga",         29.55, -104.41),
        "PIE": ("Piedras Negras", 28.70, -100.52), "NLD": ("Nuevo Laredo",    27.48,  -99.52),
        "REY": ("Reynosa",        26.09,  -98.28), "MTM": ("Matamoros",       25.87,  -97.51),
        "CJU": ("Cd. Acuña",      29.32, -100.93),
        # Pacific / Interior
        "HMO": ("Hermosillo",     29.07, -110.96), "GYM": ("Guaymas",         27.92, -110.90),
        "CLN": ("Culiacán",       24.80, -107.39), "LOS": ("Los Mochis",      25.79, -109.02),
        "MZT": ("Mazatlán",       23.23, -106.41), "DGO": ("Durango",         24.03, -104.67),
        "TPC": ("Tepic",          21.51, -104.89), "GDL": ("Guadalajara",     20.67, -103.35),
        "AGS": ("Aguascalientes", 21.88, -102.28), "ZAC": ("Zacatecas",       22.77, -102.58),
        "SLP": ("San Luis Potosí",22.15, -100.97), "CHH": ("Chihuahua",       28.63, -106.07),
        "TOR": ("Torreón",        25.55, -103.43), "SAL": ("Saltillo",        25.43, -101.00),
        "MTY": ("Monterrey",      25.67, -100.31), "VIC": ("Cd. Victoria",    23.73,  -99.14),
        "TMP": ("Tampico",        22.25,  -97.86),
        # Bajío / Central
        "GTO": ("Guanajuato",     21.02, -101.26), "QRO": ("Querétaro",       20.59, -100.39),
        "LEO": ("León",           21.12, -101.68), "MOR": ("Morelia",         19.70, -101.18),
        "COL": ("Colima",         19.24, -103.72), "MAN": ("Manzanillo",      19.05, -104.32),
        "GUR": ("Cd. Guzmán",     19.71, -103.46), "PVR": ("Puerto Vallarta", 20.61, -105.25),
        "ZIT": ("Zitácuaro",      19.44, -100.36), "TOL": ("Toluca",          19.29,  -99.65),
        "CDMX":("Ciudad de México",19.43,-99.13),  "CUE": ("Cuernavaca",      18.92,  -99.23),
        "PUE": ("Puebla",         19.05,  -98.21), "TLA": ("Tlaxcala",        19.32,  -98.24),
        "PAC": ("Pachuca",        20.12,  -98.73), "TUL": ("Tula",            20.05,  -99.34),
        "SAZ": ("Sahagun Junc.",  19.83,  -98.57), "ORZ": ("Orizaba",         18.85,  -97.10),
        "XAL": ("Xalapa",         19.54,  -96.91), "VER": ("Veracruz",        19.18,  -96.14),
        "OAX": ("Oaxaca",         17.07,  -96.72), "SAL2":("Salina Cruz",     16.17,  -95.20),
        "TCO": ("Tehuantepec",    16.32,  -95.24), "MAT": ("Matías Romero",   16.88,  -95.04),
        "COA": ("Coatzacoalcos",  18.15,  -94.44), "VIL": ("Villahermosa",    17.99,  -92.92),
        "PAL": ("Palenque",       17.52,  -91.98), "MER": ("Mérida",          20.97,  -89.62),
        "CMP": ("Campeche",       19.85,  -90.53), "FCA": ("Frontera Junc.",  18.33,  -89.55),
        "CAN": ("Cancún",         21.16,  -86.85), "CHE": ("Chetumal",        18.50,  -88.30),
        "TGU": ("Tuxtla Gutiérrez",16.75,-93.12),  "TAP": ("Tapachula",       14.90,  -92.26),
        "ACA": ("Acapulco",       16.86,  -99.88), "CHI": ("Chilpancingo",    17.55,  -99.51),
        "ZHU": ("Zihuatanejo",    17.64, -101.55), "LAZ": ("Lázaro Cárdenas", 17.96, -102.19),
        "PAT": ("Pátzcuaro",      19.51, -101.62), "IRA": ("Irapuato",        20.67, -101.35),
        "CEL": ("Celaya",         20.52, -100.82), "HIR": ("Hidalgo Parral",  26.93, -105.66),
        "LCP": ("La Paz BCS",     24.14, -110.31), "CBO": ("Cd. Obregón",     27.48, -109.94),
        "NAV": ("Navojoa",        27.08, -109.44), "CAR": ("Cardel Junc.",    19.36,  -96.37),
        "TUX": ("Tuxtepec",       18.09,  -96.12), "OCO": ("Oax-Cuacnopalan", 18.20, -97.00),
    }

    edges = [
        # Hwy 2/2D  border
        ("TIJ","MXL",200), ("MXL","SLK",100), ("SLK","NGL",290), ("NGL","AGP",200), ("AGP","JRZ",310),
        ("NLD","REY",110), ("REY","MTM",90),  ("PIE","CJU",70),
        # Hwy 15/15D  Pacific
        ("NGL","HMO",303), ("HMO","GYM",136), ("GYM","CBO",119), ("CBO","NAV",55),  ("NAV","LOS",73),
        ("LOS","CLN",213), ("CLN","MZT",218), ("MZT","TPC",316), ("TPC","GDL",175), ("TPC","PVR",157),
        # Hwy 40/45/54
        ("MZT","DGO",317), ("DGO","TOR",330), ("TOR","MTY",310),
        ("JRZ","CHH",370), ("CHH","HIR",165), ("HIR","DGO",200), ("DGO","ZAC",315),
        ("GDL","ZAC",195), ("ZAC","SAL",310), ("SAL","MTY",85),
        # Hwy 57/85
        ("CDMX","QRO",220), ("QRO","SLP",210), ("SLP","SAL",270), ("SAL","MTY",85),
        ("MTY","NLD",235),  ("MTY","VIC",300), ("VIC","TMP",247), ("VIC","NLD",183),
        ("PIE","MTY",242),  ("SLP","TMP",445), ("SLP","VIC",264),
        # CDMX metro
        ("CDMX","TOL",67),  ("CDMX","PAC",92),  ("CDMX","PUE",135), ("CDMX","CUE",90),
        ("CDMX","TUL",102), ("CDMX","ZIT",203),  ("TOL","ZIT",140),  ("TOL","IRA",156),
        # Bajío
        ("QRO","GTO",104), ("GTO","IRA",51),  ("IRA","LEO",58),  ("LEO","AGS",106),
        ("AGS","ZAC",120), ("QRO","CEL",60),  ("CEL","IRA",55),  ("CEL","MOR",185),
        ("MOR","GDL",336), ("MOR","ZIT",133), ("MOR","PAT",46),  ("PAT","GDL",56),
        # Jalisco south + Pacific
        ("GDL","COL",97),  ("COL","MAN",97),  ("GDL","GUR",143), ("GUR","COL",59),
        ("GDL","AGS",225), ("MAN","ZHU",342), ("LAZ","MOR",280), ("LAZ","COL",277),
        # Guerrero / Pacific
        ("ACA","CHI",131), ("CHI","CDMX",265), ("ACA","ZHU",274), ("ZHU","LAZ",65),
        # Gulf / Veracruz
        ("PUE","ORZ",121), ("ORZ","VER",122), ("VER","XAL",106), ("XAL","PAC",263),
        ("VER","COA",308), ("CAR","VER",40),  ("CAR","XAL",55),  ("PUE","TLA",36),
        ("PAC","SAZ",55),  ("SAZ","PUE",75),  ("TMP","VER",337), ("TMP","XAL",310),
        # Oaxaca / Chiapas / Isthmus
        ("PUE","OCO",246), ("OCO","OAX",75),  ("OAX","TCO",250), ("TCO","SAL2",55),
        ("TCO","MAT",72),  ("MAT","COA",190), ("COA","VIL",228), ("VIL","PAL",165),
        ("VIL","CMP",195), ("CMP","MER",195), ("MER","CAN",315), ("CAN","CHE",385),
        ("CHE","FCA",165), ("FCA","VIL",245), ("TGU","VIL",289), ("TGU","OAX",485),
        ("TGU","TAP",285), ("OAX","CHI",250), ("COA","TUX",165), ("TUX","OAX",252),
        ("TUX","VER",296), ("SAL2","TGU",170),
        # Baja
        ("TIJ","ENS",108), ("ENS","LCP",1059),
        # Misc connectors
        ("OJG","CHH",228), ("OJG","PIE",367),
    ]

    G = nx.Graph()
    for nid, (name, lat, lon) in nodes.items():
        G.add_node(nid, name=name, lat=lat, lon=lon)
    for u, v, km in edges:
        G.add_edge(u, v, weight=km, km=km)

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Connected: {nx.is_connected(G)}")
    return G, nodes


def total_pairwise_km(G: nx.Graph, n_orig: int, penalty: float = 3000.0) -> float:
    """Sum of all-pairs shortest path lengths; disconnected pairs penalised."""
    if not nx.is_connected(G):
        comp = [len(c) for c in nx.connected_components(G)]
        unreachable = n_orig * (n_orig - 1) - sum(s * (s - 1) for s in comp)
        ap = dict(nx.all_pairs_dijkstra_path_length(G, weight="km"))
        reachable = sum(ap[u][v] for u in ap for v in ap[u] if u != v)
        return reachable + unreachable * penalty
    ap = dict(nx.all_pairs_dijkstra_path_length(G, weight="km"))
    return sum(ap[u][v] for u in ap for v in ap[u] if u != v)


# ── 2. Betweenness centrality ─────────────────────────────────────────────────
def compute_betweenness(G: nx.Graph, nodes: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    bc = nx.betweenness_centrality(G, weight="km", normalized=True)
    bc_df = pd.DataFrame([
        {"node": k, "name": nodes[k][0], "lat": nodes[k][1], "lon": nodes[k][2],
         "betweenness": v}
        for k, v in bc.items()
    ]).sort_values("betweenness", ascending=False)

    ebc = nx.edge_betweenness_centrality(G, weight="km", normalized=True)
    ebc_df = pd.DataFrame([
        {"u": u, "v": v,
         "u_name": nodes[u][0], "v_name": nodes[v][0],
         "highway": G[u][v].get("highway", ""),
         "km": G[u][v].get("km", 0),
         "edge_betweenness": w}
        for (u, v), w in ebc.items()
    ]).sort_values("edge_betweenness", ascending=False)

    return bc_df, ebc_df


# ── 3. Node removal impact ────────────────────────────────────────────────────
def compute_node_criticality(G: nx.Graph, nodes: dict, baseline: float,
                              n_orig: int) -> pd.DataFrame:
    print("Computing node removal impact...")
    all_pairs_base = dict(nx.all_pairs_dijkstra_path_length(G, weight="km"))

    results = []
    for node in G.nodes():
        G_tmp = G.copy()
        G_tmp.remove_node(node)
        if not nx.is_connected(G_tmp):
            comp = [len(c) for c in nx.connected_components(G_tmp)]
            n_comp = len(comp)
            reachable = sum(s * (s - 1) for s in comp)
            disc_ratio = 1 - reachable / ((n_orig - 1) * (n_orig - 2))
            eff_increase = disc_ratio * 10000
            delta_pct = None
        else:
            ap = dict(nx.all_pairs_dijkstra_path_length(G_tmp, weight="km"))
            new_total = sum(ap[u][v] for u in ap for v in ap[u] if u != v)
            delta = new_total - baseline
            eff_increase = delta
            delta_pct = 100 * delta / baseline
            disc_ratio = 0
            n_comp = 1

        results.append({
            "node": node, "name": nodes[node][0],
            "lat": nodes[node][1], "lon": nodes[node][2],
            "connected": n_comp == 1,
            "n_components": n_comp,
            "disruption_ratio": disc_ratio,
            "effective_increase": eff_increase,
            "delta_pct": delta_pct,
        })

    df = pd.DataFrame(results).sort_values("effective_increase", ascending=False)
    print("  Done.")
    return df


# ── 4. Greedy optimal blockade ────────────────────────────────────────────────
def greedy_blockade(G: nx.Graph, nodes: dict, n_steps: int = 20) -> pd.DataFrame:
    print(f"Computing greedy optimal blockade (top {n_steps} steps)...")
    n_orig = G.number_of_nodes()
    baseline = total_pairwise_km(G, n_orig)
    G_curr = G.copy()
    seq = []

    for step in range(n_steps):
        best_node = None
        best_impact = -np.inf

        for n in list(G_curr.nodes()):
            G_test = G_curr.copy()
            G_test.remove_node(n)
            if G_test.number_of_nodes() == 0:
                continue
            score = total_pairwise_km(G_test, n_orig)
            if score - baseline > best_impact:
                best_impact = score - baseline
                best_node = n

        if best_node is None:
            break

        G_curr.remove_node(best_node)
        new_score = total_pairwise_km(G_curr, n_orig)
        nd = nodes.get(best_node, ("?", 0, 0))
        seq.append({
            "step": step + 1,
            "node": best_node,
            "name": nd[0],
            "lat": nd[1], "lon": nd[2],
            "step_impact_pct": 100 * best_impact / baseline,
            "cumulative_pct":  100 * (new_score - baseline) / baseline,
        })
        print(f"  Step {step+1:2d}: {nd[0]:<22}  cumulative +{100*(new_score-baseline)/baseline:.1f}%")
        baseline = new_score

    return pd.DataFrame(seq)


# ── 5. Match blockades to network, compare ────────────────────────────────────
def compare_actual_vs_optimal(G: nx.Graph, nodes: dict,
                               bc_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_excel(DATA_F, sheet_name="Combined Incidents")
    blockades = df[
        df["Subtype"].str.contains("Blockade|Bloqueo", case=False, na=False)
    ].dropna(subset=["Latitude", "Longitude"]).copy()

    node_ids   = list(nodes.keys())
    node_coords = np.array([[nodes[n][1], nodes[n][2]] for n in node_ids])
    D          = cdist(blockades[["Latitude", "Longitude"]].values, node_coords)
    blockades["nearest_node"] = [node_ids[i] for i in D.argmin(axis=1)]

    nf = blockades["nearest_node"].value_counts().reset_index()
    nf.columns = ["node", "blockade_count"]
    nf["name"] = nf["node"].map(lambda n: nodes[n][0])

    merged = bc_df.merge(nf[["node", "blockade_count"]], on="node", how="left")
    merged["blockade_count"] = merged["blockade_count"].fillna(0)

    rho, p = spearmanr(merged["betweenness"], merged["blockade_count"])
    print(f"\n── Statistical Comparison ────────────────────────────────────────")
    print(f"  Spearman ρ (betweenness vs. actual blockades): ρ={rho:.4f}, p={p:.4f}")

    top15_opt  = set(bc_df.nlargest(15, "betweenness")["node"])
    top15_cjng = set(nf.head(15)["node"])
    overlap    = top15_opt & top15_cjng
    jaccard    = len(overlap) / len(top15_opt | top15_cjng)
    print(f"  Jaccard overlap (top-15 optimal vs. top-15 CJNG): {jaccard:.3f} "
          f"({len(overlap)}/{len(top15_opt|top15_cjng)})")
    print(f"  Optimal nodes CJNG hit: {sorted(overlap)}")
    print(f"  Optimal nodes CJNG missed: {sorted(top15_opt - top15_cjng)}")

    return merged


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    G, nodes = build_graph()
    n_orig   = G.number_of_nodes()
    baseline = total_pairwise_km(G, n_orig)
    print(f"Baseline total pairwise km: {baseline:,.0f}")

    bc_df, ebc_df    = compute_betweenness(G, nodes)
    nc_df            = compute_node_criticality(G, nodes, baseline, n_orig)
    greedy_df        = greedy_blockade(G, nodes, n_steps=20)
    merged_df        = compare_actual_vs_optimal(G, nodes, bc_df)

    bc_df.to_csv(    OUT_DIR / "betweenness.csv",        index=False)
    ebc_df.to_csv(   OUT_DIR / "edge_betweenness.csv",   index=False)
    nc_df.to_csv(    OUT_DIR / "node_criticality.csv",   index=False)
    greedy_df.to_csv(OUT_DIR / "greedy_blockade.csv",    index=False)
    merged_df.to_csv(OUT_DIR / "network_vs_blockades.csv", index=False)

    with open(OUT_DIR / "mexico_road_graph.pkl", "wb") as f:
        pickle.dump((G, nodes), f)

    print("\nAll outputs saved to data/")


if __name__ == "__main__":
    main()
