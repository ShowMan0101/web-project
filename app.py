from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "votre_clé_secrète"  # À changer en production
app.config["DATABASE"] = os.path.join(app.instance_path, "database.db")

# Assurez-vous que le dossier instance existe
try:
    os.makedirs(app.instance_path)
except OSError:
    pass


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


@app.cli.command("init-db")
def init_db_command():
    """Commande Flask pour initialiser la base de données."""
    init_db()
    print("Base de données initialisée!")


# Enregistrement de la fonction de fermeture de la base de données
app.teardown_appcontext(close_db)


# Routes pour la gestion des utilisateurs
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        db = get_db()
        error = None

        if not email:
            error = "Email requis."
        elif not password:
            error = "Mot de passe requis."
        elif (
            db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            is not None
        ):
            error = f"L'utilisateur {email} est déjà enregistré."

        if error is None:
            db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            db.commit()
            return redirect(url_for("login"))

        flash(error)

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user is None:
            error = "Email incorrect."
        elif not check_password_hash(user["password_hash"], password):
            error = "Mot de passe incorrect."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

        flash(error)

    return render_template("login.html")


# Routes pour la gestion des abonnements
@app.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    subscriptions = db.execute(
        "SELECT * FROM subscriptions WHERE user_id = ?", (session["user_id"],)
    ).fetchall()
    return render_template("subscriptions.html", subscriptions=subscriptions)


@app.route("/add_subscription", methods=["POST"])
def add_subscription():
    if "user_id" not in session:
        return redirect(url_for("login"))

    service_name = request.form["service_name"]
    category = request.form["category"]
    start_date = request.form["start_date"]
    renewal_date = request.form["renewal_date"]

    db = get_db()
    db.execute(
        """INSERT INTO subscriptions
           (user_id, service_name, category, start_date, renewal_date)
           VALUES (?, ?, ?, ?, ?)""",
        (session["user_id"], service_name, category, start_date, renewal_date),
    )
    db.commit()
    return redirect(url_for("get_subscriptions"))


# Route pour le tableau de bord
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    subscriptions = db.execute(
        "SELECT * FROM subscriptions WHERE user_id = ?", (session["user_id"],)
    ).fetchall()

    newsletters = db.execute(
        "SELECT * FROM newsletters WHERE user_id = ?", (session["user_id"],)
    ).fetchall()

    return render_template(
        "dashboard.html",
        user=user,
        subscriptions=subscriptions,
        newsletters=newsletters,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
