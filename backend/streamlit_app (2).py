import streamlit as st
import mysql.connector
import pandas as pd
from bi_engine import rank_offers

def get_connection():
    return mysql.connector.connect(
        host="localhost", port=8889,
        user="root", password="root", database="rawfind"
    )

def load_materials():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM matieres", conn)
    conn.close()
    return df

def load_offers_for_material(matiere_id):
    conn = get_connection()
    query = """
    SELECT offres.id, fournisseurs.nomF AS fournisseur, fournisseurs.ville,
           offres.prix, offres.qualite, offres.delai_livraison, offres.disponible
    FROM offres
    JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
    WHERE offres.matiere_id = %s
    """
    df = pd.read_sql(query, conn, params=(matiere_id,))
    conn.close()
    return df

# ── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="RawFind Tunisia — Démo BI", page_icon="⬡", layout="wide")

st.title("⬡ RawFind Tunisia — Analyse BI")
st.caption("Plateforme de comparaison de matières premières · Tunisie")
st.divider()

# ── DONNÉES ──────────────────────────────────────────────────────────────────
materials_df = load_materials()
material_options = dict(zip(materials_df["nomM"], materials_df["id"]))

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Paramètres")

selected_name = st.sidebar.selectbox("Matière première", list(material_options.keys()))
selected_id   = material_options[selected_name]

st.sidebar.divider()
st.sidebar.subheader("Pondérations BI")

w_prix    = st.sidebar.slider("💰 Prix (%)",          0, 100, 35, 5)
w_qualite = st.sidebar.slider("⭐ Qualité (%)",        0, 100, 40, 5)
w_delai   = st.sidebar.slider("🚚 Délai (%)",          0, 100, 15, 5)
w_dispo   = st.sidebar.slider("✅ Disponibilité (%)",  0, 100, 10, 5)

total = w_prix + w_qualite + w_delai + w_dispo
if total != 100:
    st.sidebar.warning(f"⚠️ Total = {total}% (doit être 100%)")
else:
    st.sidebar.success("✅ Total = 100%")

# ── CHARGEMENT + CALCUL SCORE ────────────────────────────────────────────────
st.subheader(f"📦 Offres — {selected_name}")

offers_df = load_offers_for_material(selected_id)
if offers_df.empty:
    st.warning("Aucune offre disponible.")
    st.stop()

offers_list = offers_df.to_dict(orient="records")
prix_max  = offers_df["prix"].max()
delai_max = offers_df["delai_livraison"].max()

for o in offers_list:
    sp = 1 - (o["prix"] / prix_max)          if prix_max  > 0 else 0
    sq = o["qualite"] / 5
    sd = 1 - (o["delai_livraison"] / delai_max) if delai_max > 0 else 0
    sa = 1 if o["disponible"] else 0
    o["score_bi"] = round(sp*(w_prix/100) + sq*(w_qualite/100) + sd*(w_delai/100) + sa*(w_dispo/100), 4)

offers_list = sorted(offers_list, key=lambda x: x["score_bi"], reverse=True)

best    = offers_list[0]
cheapest = min(offers_list, key=lambda x: x["prix"])

# ── ALERTE QUALITÉ ────────────────────────────────────────────────────────────
if cheapest["qualite"] < 3:
    st.error(f"⚠️ **Alerte qualité** : {cheapest['fournisseur']} ({cheapest['prix']} TND) — qualité {cheapest['qualite']}/5 insuffisante.")

# ── MÉTRIQUES ─────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("🏆 Meilleure offre (BI)",  best["fournisseur"],       f"Score {best['score_bi']}")
c2.metric("💰 Moins cher",            f"{cheapest['prix']} TND", cheapest["fournisseur"])
c3.metric("📊 Offres comparées",      len(offers_list))

st.divider()

# ── TABLEAU ───────────────────────────────────────────────────────────────────
st.subheader("📋 Classement BI")

result_df = pd.DataFrame(offers_list).rename(columns={
    "fournisseur": "Fournisseur", "ville": "Ville",
    "prix": "Prix (TND)", "qualite": "Qualité /5",
    "delai_livraison": "Délai (j)", "disponible": "Dispo", "score_bi": "Score BI"
})

st.dataframe(
    result_df[["Fournisseur","Ville","Prix (TND)","Qualité /5","Délai (j)","Dispo","Score BI"]],
    use_container_width=True, hide_index=True,
    column_config={
        "Score BI":    st.column_config.ProgressColumn("Score BI", min_value=0, max_value=1, format="%.4f"),
        "Qualité /5":  st.column_config.NumberColumn("Qualité /5", format="⭐ %.1f"),
    }
)

# ── GRAPHIQUES ────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📈 Visualisations")

chart_df = result_df[["Fournisseur","Prix (TND)","Qualité /5","Score BI"]].set_index("Fournisseur")

tab1, tab2 = st.tabs(["Score BI", "Prix vs Qualité"])
with tab1:
    st.bar_chart(chart_df["Score BI"])
with tab2:
    st.bar_chart(chart_df[["Prix (TND)","Qualité /5"]])

# ════════════════════════════════════════════════════════════════════════════
# SECTION BI AVANCÉE
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("🔬 Analyse BI Avancée")

bi_tab1, bi_tab2, bi_tab3 = st.tabs([
    "📊 Analyse mathématique",
    "💰 Calculateur ROI",
    "🏗️ Scénarios d'utilisation"
])

# ── TAB 1 : ANALYSE MATHÉMATIQUE ─────────────────────────────────────────────
with bi_tab1:
    st.markdown("#### Comparaison chiffrée : meilleur prix vs meilleure offre BI")

    # Compare cheapest vs best BI offer
    if cheapest["fournisseur"] != best["fournisseur"]:
        price_diff_pct  = ((best["prix"] - cheapest["prix"]) / cheapest["prix"]) * 100
        quality_diff_pct = ((best["qualite"] - cheapest["qualite"]) / cheapest["qualite"]) * 100 if cheapest["qualite"] > 0 else 0
        delay_diff      = cheapest["delai_livraison"] - best["delai_livraison"]

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Surcoût prix",
            f"+{price_diff_pct:.1f}%",
            f"{best['fournisseur']} coûte {price_diff_pct:.1f}% de plus",
            delta_color="inverse"
        )
        col2.metric(
            "Gain qualité",
            f"+{quality_diff_pct:.1f}%",
            f"Qualité {best['qualite']}/5 vs {cheapest['qualite']}/5",
            delta_color="normal"
        )
        col3.metric(
            "Délai",
            f"{abs(delay_diff)} j",
            f"{'Plus rapide' if delay_diff > 0 else 'Plus lent'} que le moins cher",
            delta_color="normal" if delay_diff >= 0 else "inverse"
        )

        st.divider()

        # Verdict automatique
        worth_it = quality_diff_pct > price_diff_pct * 1.5

        if worth_it:
            st.success(
                f"✅ **Verdict BI** : Le surcoût de **{price_diff_pct:.1f}%** est justifié. "
                f"**{best['fournisseur']}** offre **{quality_diff_pct:.1f}%** de qualité en plus — "
                f"un gain de qualité {quality_diff_pct/price_diff_pct:.1f}× supérieur au surcoût. "
                f"Pour une utilisation professionnelle ou à grande échelle, ce choix est économiquement rationnel."
            )
        else:
            st.warning(
                f"⚠️ **Verdict BI** : **{cheapest['fournisseur']}** est {price_diff_pct:.1f}% moins cher, "
                f"mais sa qualité est {quality_diff_pct:.1f}% inférieure. "
                f"Pour des petits projets ponctuels, le prix peut primer. "
                f"Pour une production continue ou des projets critiques, la qualité inférieure "
                f"génèrera davantage de pertes que l'économie réalisée."
            )
    else:
        st.info(f"✅ **{best['fournisseur']}** est à la fois la meilleure offre BI ET la moins chère. Décision simple !")

# ── TAB 2 : CALCULATEUR ROI ───────────────────────────────────────────────────
with bi_tab2:
    st.markdown("#### Coût Total de Possession (TCO) — ce que paient vraiment les entreprises")
    st.caption("Le prix d'achat n'est que la partie visible. Les défauts et retards coûtent souvent plus cher.")

    col1, col2 = st.columns(2)
    with col1:
        volume = st.number_input(
            "Volume de production mensuel (unités)",
            min_value=100, max_value=500000, value=5000, step=500,
            help="Combien d'unités de cette matière vous utilisez par mois"
        )
    with col2:
        cout_defaut = st.number_input(
            "Coût d'un défaut / rebut (TND par unité)",
            min_value=5, max_value=1000, value=50, step=5,
            help="Coût de remplacement + main d'oeuvre perdue quand une pièce est défectueuse"
        )

    st.divider()

    # Calcul TCO pour chaque fournisseur
    tco_results = []
    for o in offers_list:
        # Taux de défaut estimé inversement proportionnel à la qualité
        # qualite 5/5 → 2% défauts | qualite 1/5 → 18% défauts
        taux_defaut = max(0.02, 0.20 - (o["qualite"] / 5) * 0.18)

        # Coût des défauts sur le volume
        cout_defauts_total = volume * taux_defaut * cout_defaut

        # Pénalité retard : chaque jour au-delà de 3j coûte 0.5% du lot
        penalite_retard = max(0, (o["delai_livraison"] - 3)) * (o["prix"] * volume * 0.005)

        # Coût total
        cout_achat = o["prix"] * volume
        tco_total  = cout_achat + cout_defauts_total + penalite_retard

        tco_results.append({
            "Fournisseur":     o["fournisseur"],
            "Qualité":         f"{o['qualite']}/5",
            "Prix achat (TND)": int(cout_achat),
            "Coût défauts (TND)": int(cout_defauts_total),
            "Pénalité retard (TND)": int(penalite_retard),
            "TCO Total (TND)": int(tco_total),
            "Taux défaut estimé": f"{taux_defaut*100:.1f}%"
        })

    tco_df = pd.DataFrame(tco_results).sort_values("TCO Total (TND)")

    st.dataframe(tco_df, use_container_width=True, hide_index=True,
        column_config={
            "TCO Total (TND)": st.column_config.NumberColumn("TCO Total (TND)", format="%d TND"),
        }
    )

    best_tco   = tco_results[0] if tco_results else None
    worst_tco  = max(tco_results, key=lambda x: x["TCO Total (TND)"]) if tco_results else None

    if best_tco and worst_tco and best_tco["Fournisseur"] != worst_tco["Fournisseur"]:
        economies = worst_tco["TCO Total (TND)"] - best_tco["TCO Total (TND)"]
        st.success(
            f"💡 **Recommandation TCO** : En choisissant **{best_tco['Fournisseur']}**, "
            f"vous économisez **{economies:,} TND/mois** par rapport à "
            f"**{worst_tco['Fournisseur']}** — soit **{economies*12:,} TND/an** — "
            f"en tenant compte des coûts de défauts et de retards."
        )

    st.caption("📐 Formule TCO = Prix achat + Coût défauts (taux estimé × volume × coût unitaire) + Pénalité retard (jours × 0.5% du lot)")

# ── TAB 3 : SCÉNARIOS ─────────────────────────────────────────────────────────
with bi_tab3:
    st.markdown("#### Pour quel usage, quel fournisseur ?")
    st.caption("Basé sur l'analyse BI des offres disponibles.")

    best_quality_offer = max(offers_list, key=lambda x: x["qualite"])
    best_price_offer   = min(offers_list, key=lambda x: x["prix"])
    best_bi_offer      = offers_list[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style='background:#f0fdf4;border-radius:12px;padding:20px;border:1px solid #bbf7d0;height:280px;'>
            <div style='font-size:32px;margin-bottom:10px;'>🏗️</div>
            <h4 style='font-weight:700;margin-bottom:8px;color:#065f46;'>Grands projets</h4>
            <p style='font-size:12px;color:#166534;margin-bottom:10px;'>
            Construction, infrastructure, production industrielle continue, 
            projets à haute valeur ajoutée.
            </p>
            <div style='background:#dcfce7;padding:10px;border-radius:8px;font-size:12px;color:#15803d;'>
            <strong>✅ Recommandé :</strong> Qualité ≥ 4.5/5<br>
            Un matériau de moindre qualité génère plus de pertes que d'économies.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"**→ {best_quality_offer['fournisseur']}** ({best_quality_offer['qualite']}/5)")

    with col2:
        st.markdown("""
        <div style='background:#fffbeb;border-radius:12px;padding:20px;border:1px solid #fde68a;height:280px;'>
            <div style='font-size:32px;margin-bottom:10px;'>🔧</div>
            <h4 style='font-weight:700;margin-bottom:8px;color:#92400e;'>Petits projets</h4>
            <p style='font-size:12px;color:#a16207;margin-bottom:10px;'>
            Prototypage, petites séries, réparations ponctuelles, 
            projets non critiques à budget serré.
            </p>
            <div style='background:#fef3c7;padding:10px;border-radius:8px;font-size:12px;color:#b45309;'>
            <strong>✅ Acceptable :</strong> Prix minimum<br>
            Économie immédiate justifiée si la qualité n'est pas critique.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"**→ {best_price_offer['fournisseur']}** ({best_price_offer['prix']} TND)")

    with col3:
        st.markdown("""
        <div style='background:#eff6ff;border-radius:12px;padding:20px;border:1px solid #bfdbfe;height:280px;'>
            <div style='font-size:32px;margin-bottom:10px;'>⚖️</div>
            <h4 style='font-weight:700;margin-bottom:8px;color:#1e40af;'>Usage mixte</h4>
            <p style='font-size:12px;color:#1d4ed8;margin-bottom:10px;'>
            Approvisionnement régulier, production standard, 
            besoin d'équilibre entre coût et fiabilité.
            </p>
            <div style='background:#dbeafe;padding:10px;border-radius:8px;font-size:12px;color:#2563eb;'>
            <strong>✅ Optimal :</strong> Meilleur score BI<br>
            Meilleur équilibre prix / qualité / délai / fiabilité.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"**→ {best_bi_offer['fournisseur']}** (score {best_bi_offer['score_bi']})")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("RawFind Tunisia · Démo BI · Sprint 3 · Usage académique AGL")