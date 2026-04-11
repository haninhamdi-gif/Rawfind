from flask import Flask, jsonify, request, session, render_template, redirect, url_for, flash
from functools import wraps
from database import get_connection
from bi_engine import rank_offers
import random

app = Flask(__name__)
app.secret_key = "rawfind_secret_key"

# ── DÉCORATEUR ADMIN ────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"message": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES FRONTEND (servent les pages HTML)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Page d'accueil — affiche les matières et les stats"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM matieres LIMIT 4")
    matieres = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS n FROM matieres")
    nb_matieres = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM fournisseurs")
    nb_fournisseurs = cursor.fetchone()["n"]

    cursor.close()
    conn.close()

    stats = {"nb_matieres": nb_matieres, "nb_fournisseurs": nb_fournisseurs}
    return render_template("index.html", matieres=matieres, stats=stats)


@app.route("/catalogue")
def catalogue():
    """Page catalogue — liste toutes les matières"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM matieres")
    matieres = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("catalogue.html", matieres=matieres)


@app.route("/fiche/<int:id>")
def fiche(id):
    """Page fiche matière — détail + offres + suggestions"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM matieres WHERE id = %s", (id,))
    material = cursor.fetchone()
    if not material:
        cursor.close()
        conn.close()
        flash("Matière introuvable.", "error")
        return redirect(url_for("catalogue"))

    cursor.execute("""
        SELECT offres.*, fournisseurs.nomF, fournisseurs.ville, fournisseurs.site_web,
               COALESCE(offres.fiabilite, 3.5) AS fiabilite, offres.disponible
        FROM offres
        JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
        WHERE offres.matiere_id = %s
    """, (id,))
    offers = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM matieres
        WHERE categorie = %s AND id != %s
        LIMIT 5
    """, (material["categorie"], id))
    suggestions_pool = cursor.fetchall()
    suggestions = random.sample(suggestions_pool, min(3, len(suggestions_pool)))

    cursor.close()
    conn.close()

    return render_template("fiche.html", material=material, offers=offers, suggestions=suggestions)


@app.route("/analyse/<int:id>")
def analyse(id):
    """Page analyse BI — score et classement des offres"""

    if not session.get("user_id"):
        flash("Connectez-vous pour accéder à l'analyse.", "error")
        return redirect(url_for("login_page"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM matieres WHERE id = %s", (id,))
    material = cursor.fetchone()

    if not material:
        cursor.close()
        conn.close()
        flash("Matière non trouvée.", "error")
        return redirect(url_for("catalogue"))

    cursor.execute("""
        SELECT offres.*, fournisseurs.nomF AS fournisseur,
               fournisseurs.ville, fournisseurs.site_web,
               COALESCE(offres.fiabilite, 3.5) AS fiabilite,
               offres.disponible
        FROM offres
        JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
        WHERE offres.matiere_id = %s
    """, (id,))
    offers = cursor.fetchall()
    cursor.close()
    conn.close()

    if not offers:
        flash("Aucune offre disponible pour cette matière.", "info")
        return redirect(url_for("fiche", id=id))

    ranked = rank_offers(offers)

    cheapest = min(offers, key=lambda x: x["prix"])
    quality_alert = cheapest["qualite"] < 3

    return render_template("analyse.html",
                           material=material,
                           ranked=ranked,
                           cheapest=cheapest,
                           quality_alert=quality_alert)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Page et traitement du formulaire de connexion avec email"""
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Email et mot de passe requis.", "error")
            return render_template("login.html")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            session["role"] = user.get("role", "user")
            flash(f"Bienvenue, {user['username']} !", "success")
            return redirect(url_for("index"))
        else:
            flash("Email ou mot de passe incorrect.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    """Page et traitement du formulaire d'inscription avec email"""
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("Tous les champs sont requis.", "error")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            flash("Cet email est déjà utilisé.", "error")
            return render_template("register.html")

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            flash("Ce nom d'utilisateur est déjà pris.", "error")
            return render_template("register.html")

        try:
            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                (username, email, password, "user")
            )
            conn.commit()
            flash("Compte créé ! Vous pouvez vous connecter avec votre email.", "success")
            return redirect(url_for("login_page"))
        except Exception as e:
            conn.rollback()
            flash("Erreur lors de la création du compte.", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout_page():
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("index"))


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/materials")
def get_materials():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM matieres")
    materials = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(materials)


@app.route("/api/materials/<int:id>/analysis")
def analyze_material(id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT offres.*, fournisseurs.nomF AS fournisseur, fournisseurs.ville,
               COALESCE(offres.fiabilite, 3.5) AS fiabilite
        FROM offres
        JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
        WHERE offres.matiere_id = %s
    """, (id,))
    offers = cursor.fetchall()
    cursor.close()
    conn.close()
    if not offers:
        return jsonify({"message": "No offers found"}), 404
    ranked = rank_offers(offers)
    return jsonify({"matiere_id": id, "total": len(ranked), "ranked": ranked})


@app.route("/api/offers")
def get_offers():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT offres.id, matieres.nomM AS matiere,
               fournisseurs.nomF AS fournisseur,
               offres.prix, offres.qualite, offres.delai_livraison,
               COALESCE(offres.fiabilite, 3.5) AS fiabilite
        FROM offres
        JOIN matieres ON offres.matiere_id = matieres.id
        JOIN fournisseurs ON offres.fournisseur_id = fournisseurs.id
    """)
    offers = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(offers)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES ADMIN CRUD
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/materials", methods=["POST"])
@admin_required
def create_material():
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO matieres (nomM, categorie, unite) VALUES (%s, %s, %s)",
        (data["nomM"], data["categorie"], data["unite"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Material created"}), 201


@app.route("/admin/materials/<int:id>", methods=["PUT"])
@admin_required
def update_material(id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE matieres SET nomM=%s, categorie=%s, unite=%s WHERE id=%s",
        (data["nomM"], data["categorie"], data["unite"], id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Material updated"})


@app.route("/admin/materials/<int:id>", methods=["DELETE"])
@admin_required
def delete_material(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM matieres WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Material deleted"})


@app.route("/admin/suppliers", methods=["POST"])
@admin_required
def create_supplier():
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO fournisseurs (nomF, ville, site_web) VALUES (%s, %s, %s)",
        (data["nomF"], data["ville"], data.get("site_web", ""))
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Supplier created"}), 201


@app.route("/admin/suppliers/<int:id>", methods=["PUT"])
@admin_required
def update_supplier(id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE fournisseurs SET nomF=%s, ville=%s, site_web=%s WHERE id=%s",
        (data["nomF"], data["ville"], data.get("site_web", ""), id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Supplier updated"})


@app.route("/admin/suppliers/<int:id>", methods=["DELETE"])
@admin_required
def delete_supplier(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fournisseurs WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Supplier deleted"})


@app.route("/admin/offers", methods=["POST"])
@admin_required
def create_offer():
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO offres (matiere_id, fournisseur_id, prix, qualite, delai_livraison, disponible, fiabilite) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (data["matiere_id"], data["fournisseur_id"], data["prix"],
         data["qualite"], data["delai_livraison"], data.get("disponible", True),
         data.get("fiabilite", 3.5))
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Offer created"}), 201


@app.route("/admin/offers/<int:id>", methods=["PUT"])
@admin_required
def update_offer(id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE offres SET prix=%s, qualite=%s, delai_livraison=%s, disponible=%s, fiabilite=%s WHERE id=%s",
        (data["prix"], data["qualite"], data["delai_livraison"],
         data.get("disponible", True), data.get("fiabilite", 3.5), id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Offer updated"})


@app.route("/admin/offers/<int:id>", methods=["DELETE"])
@admin_required
def delete_offer(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM offres WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Offer deleted"})


if __name__ == "__main__":
    app.run(debug=True)