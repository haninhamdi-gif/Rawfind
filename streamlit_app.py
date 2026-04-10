import streamlit as st
import mysql.connector
import pandas as pd
from bi_engine import rank_offers

# ─── CONNEXION BDD (identique à database.py) ───────────────────────────────
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        port=8889,
        user="root",
        password="root",
        database="rawfind"
    )

# ─── FONCTIONS DE CHARGEMENT DES DONNÉES ───────────────────────────────────
def load_materials():
    """Récupère toutes les matières premières depuis Oracle/MySQL"""
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM matieres", conn)
    conn.close()
    return df

def load_offers_for_material(matiere_id):
    """Récupère toutes les offres d'une matière avec les infos fournisseur"""
    conn = get_connection()
    query = """
    SELECT
        offres.id,
        fournisseurs.nomF   AS fournisseur,
        fournisseurs.ville,
        offres.prix,
        offres.qualite,
        offres.delai_livraison,
        offres.disponible
    FROM offres
    JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
    WHERE offres.matiere_id = %s
    """
    df = pd.read_sql(query, conn, params=(matiere_id,))
    conn.close()
    return df

# ─── CONFIGURATION DE LA PAGE ───────────────────────────────────────────────
st.set_page_config(
    page_title="RawFind Tunisia — Démo BI",
    page_icon="⬡",
    layout="wide"
)

# ─── EN-TÊTE ────────────────────────────────────────────────────────────────
st.title("⬡ RawFind Tunisia — Démo Analyse BI")
st.caption("Plateforme de comparaison de matières premières · Tunisie")
st.divider()

# ─── CHARGEMENT DES MATIÈRES ────────────────────────────────────────────────
materials_df = load_materials()

# Crée un dictionnaire {nom: id} pour le selectbox
material_options = dict(zip(materials_df["nomM"], materials_df["id"]))

# ─── SIDEBAR : FILTRES ET PONDÉRATIONS ──────────────────────────────────────
st.sidebar.header("⚙️ Paramètres BI")
st.sidebar.subheader("Choisir une matière")

# Selectbox pour choisir la matière
selected_name = st.sidebar.selectbox(
    "Matière première",
    options=list(material_options.keys())
)
selected_id = material_options[selected_name]

st.sidebar.divider()
st.sidebar.subheader("Ajuster les pondérations")

# Sliders pour modifier les poids du score BI en temps réel
# st.sidebar.slider(label, min, max, valeur_par_defaut, pas)
w_prix    = st.sidebar.slider("Prix (%)",        0, 100, 35, 5)
w_qualite = st.sidebar.slider("Qualité (%)",     0, 100, 40, 5)
w_delai   = st.sidebar.slider("Délai (%)",       0, 100, 15, 5)
w_dispo   = st.sidebar.slider("Disponibilité (%)", 0, 100, 10, 5)

# Calcule le total des poids
total_poids = w_prix + w_qualite + w_delai + w_dispo

# Avertissement si les poids ne font pas 100%
if total_poids != 100:
    st.sidebar.warning(f"⚠️ Total = {total_poids}% (doit être 100%)")
else:
    st.sidebar.success("✅ Total = 100%")

# ─── CORPS PRINCIPAL ────────────────────────────────────────────────────────
st.subheader(f"📦 Offres disponibles pour : **{selected_name}**")

# Charge les offres de la matière sélectionnée
offers_df = load_offers_for_material(selected_id)

if offers_df.empty:
    st.warning("Aucune offre disponible pour cette matière.")
    st.stop()  # Arrête l'exécution si pas d'offres

# ─── CALCUL DU SCORE BI AVEC LES POIDS DES SLIDERS ─────────────────────────
# Convertit le DataFrame en liste de dictionnaires (comme rank_offers l'attend)
offers_list = offers_df.to_dict(orient="records")

# Calcule les scores avec les poids personnalisés des sliders
prix_max  = offers_df["prix"].max()
delai_max = offers_df["delai_livraison"].max()

for offer in offers_list:
    # Normalise chaque critère entre 0 et 1
    score_prix    = 1 - (offer["prix"] / prix_max) if prix_max > 0 else 0
    score_qualite = offer["qualite"] / 5
    score_delai   = 1 - (offer["delai_livraison"] / delai_max) if delai_max > 0 else 0
    score_dispo   = 1 if offer["disponible"] else 0

    # Applique les poids des sliders (convertit % en décimal)
    offer["score_bi"] = round(
        score_prix    * (w_prix    / 100) +
        score_qualite * (w_qualite / 100) +
        score_delai   * (w_delai   / 100) +
        score_dispo   * (w_dispo   / 100),
        4
    )

# Trie par score décroissant (meilleur en premier)
offers_list = sorted(offers_list, key=lambda x: x["score_bi"], reverse=True)

# ─── ALERTE QUALITÉ ─────────────────────────────────────────────────────────
# Vérifie si la meilleure offre en prix a une qualité < 3
cheapest = min(offers_list, key=lambda x: x["prix"])
if cheapest["qualite"] < 3:
    st.error(
        f"⚠️ **Alerte qualité** : Le fournisseur le moins cher "
        f"(**{cheapest['fournisseur']}** à {cheapest['prix']} TND) "
        f"a une qualité de **{cheapest['qualite']}/5** — insuffisante. "
        f"Le gain de prix ne compense pas la perte de qualité."
    )

# ─── MÉTRIQUES EN HAUT DE PAGE ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

best_offer = offers_list[0]  # Meilleure offre (score le plus élevé)

col1.metric(
    label="🏆 Meilleure offre",
    value=best_offer["fournisseur"],
    delta=f"Score BI : {best_offer['score_bi']}"
)
col2.metric(
    label="💰 Meilleur prix",
    value=f"{cheapest['prix']} TND",
    delta=cheapest["fournisseur"]
)
col3.metric(
    label="📊 Nombre d'offres",
    value=len(offers_list)
)

st.divider()

# ─── TABLEAU COMPARATIF ──────────────────────────────────────────────────────
st.subheader("📋 Tableau comparatif (trié par score BI)")

# Convertit en DataFrame pour l'affichage
result_df = pd.DataFrame(offers_list)

# Renomme les colonnes pour l'affichage
result_df = result_df.rename(columns={
    "fournisseur":      "Fournisseur",
    "ville":            "Ville",
    "prix":             "Prix (TND)",
    "qualite":          "Qualité /5",
    "delai_livraison":  "Délai (jours)",
    "disponible":       "Disponible",
    "score_bi":         "Score BI"
})

# Colonnes à afficher (on retire l'id technique)
cols_to_show = ["Fournisseur", "Ville", "Prix (TND)", "Qualité /5",
                "Délai (jours)", "Disponible", "Score BI"]

# Affiche le tableau avec mise en couleur du score BI
st.dataframe(
    result_df[cols_to_show],
    use_container_width=True,   # prend toute la largeur
    hide_index=True,
    column_config={
        # Affiche le Score BI comme une barre de progression
        "Score BI": st.column_config.ProgressColumn(
            "Score BI",
            min_value=0,
            max_value=1,
            format="%.4f"
        ),
        # Affiche la qualité comme des étoiles
        "Qualité /5": st.column_config.NumberColumn(
            "Qualité /5",
            format="⭐ %.1f"
        ),
    }
)

# ─── GRAPHIQUE PRIX vs QUALITÉ ──────────────────────────────────────────────
st.divider()
st.subheader("📈 Graphique : Prix vs Qualité")

# Streamlit a des graphiques intégrés
# On utilise st.bar_chart pour afficher les scores BI par fournisseur
chart_df = result_df[["Fournisseur", "Prix (TND)", "Qualité /5", "Score BI"]].set_index("Fournisseur")

tab1, tab2 = st.tabs(["Score BI par fournisseur", "Prix vs Qualité"])

with tab1:
    st.bar_chart(chart_df["Score BI"])

with tab2:
    # Affiche prix et qualité côte à côte pour comparer
    st.bar_chart(chart_df[["Prix (TND)", "Qualité /5"]])

# ─── DÉTAIL DU MEILLEUR FOURNISSEUR ─────────────────────────────────────────
st.divider()
st.subheader("🥇 Détail — Meilleure offre")

best = offers_list[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Fournisseur", best["fournisseur"])
c2.metric("Prix",        f"{best['prix']} TND")
c3.metric("Qualité",     f"{best['qualite']}/5")
c4.metric("Délai",       f"{best['delai_livraison']} jours")

st.info(
    f"💡 **{best['fournisseur']}** ({best['ville']}) obtient le meilleur score BI "
    f"de **{best['score_bi']}** avec une qualité de {best['qualite']}/5 "
    f"et un délai de {best['delai_livraison']} jours."
)

# ─── PIED DE PAGE ───────────────────────────────────────────────────────────
st.divider()
st.caption("RawFind Tunisia · Démo BI · Sprint 3 · Usage académique AGL")