from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from subDB import DBFILENAME, SubscriptionsDB, db_run, db_update
from functools import wraps

app = Flask(__name__)
app.secret_key = "secret key"  # À changer en production
db = SubscriptionsDB()


@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}


# Décorateur pour vérifier si l'utilisateur est connecté
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = db.get_user(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Connexion réussie!", "success")
            return redirect(url_for("dashboard"))

        flash("Email ou mot de passe incorrect", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas", "error")
            return redirect(url_for("register"))

        if db.get_user(email):
            flash("Cet email est déjà utilisé", "error")
            return redirect(url_for("register"))

        db.create_user(email, generate_password_hash(password))
        flash("Inscription réussie! Vous pouvez maintenant vous connecter", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        user = db.get_user(email)
        if user:
            # Ici vous devriez générer un token et envoyer un email
            flash(
                "Un email de réinitialisation a été envoyé si cet email existe dans notre système.",
                "info",
            )
        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/profile")
@login_required
def profile():
    user = db.get_user_by_id(session["user_id"])
    return render_template("profile.html", user=user)


@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    user_id = session["user_id"]
    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")

    db_update(
        "UPDATE users SET firstname = ?, lastname = ? WHERE id = ?",
        (firstname, lastname, user_id),
        db_name=DBFILENAME,
    )
    flash("Profil mis à jour avec succès!", "success")
    return redirect(url_for("profile"))


@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    user_id = session["user_id"]
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    user = db.get_user_by_id(user_id)

    if not check_password_hash(user["password_hash"], current_password):
        flash("Mot de passe actuel incorrect", "error")
        return redirect(url_for("profile"))

    if new_password != confirm_password:
        flash("Les nouveaux mots de passe ne correspondent pas", "error")
        return redirect(url_for("profile"))

    db_update(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id),
        db_name=DBFILENAME,
    )
    flash("Mot de passe changé avec succès!", "success")
    return redirect(url_for("profile"))


@app.route("/update_notifications", methods=["POST"])
@login_required
def update_notifications():
    user_id = session["user_id"]
    email_notifications = "email_notifications" in request.form
    renewal_reminders = "renewal_reminders" in request.form

    db_update(
        "UPDATE users SET email_notifications = ?, renewal_reminders = ? WHERE id = ?",
        (email_notifications, renewal_reminders, user_id),
        db_name=DBFILENAME,
    )

    flash("Préférences mises à jour avec succès !", "success")
    return redirect(url_for("settings"))


@app.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    user_id = session["user_id"]

    # Supprimer d'abord les abonnements et newsletters
    db_run(
        "DELETE FROM subscriptions WHERE user_id = ?", (user_id,), db_name=DBFILENAME
    )
    db_run("DELETE FROM newsletters WHERE user_id = ?", (user_id,), db_name=DBFILENAME)

    # Puis supprimer l'utilisateur
    db_run("DELETE FROM users WHERE id = ?", (user_id,), db_name=DBFILENAME)

    session.clear()
    flash("Votre compte a été supprimé avec succès.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    # Récupérer l'utilisateur
    user = db.get_user_by_id(user_id)

    # Récupérer les statistiques
    stats = db.get_subscription_stats(user_id)

    # Calculer les tendances
    subscription_trend = (
        ((stats["trend_count"] - stats["active_count"]) / stats["active_count"] * 100)
        if stats["active_count"] > 0
        else 0
    )

    cost_trend = (
        ((stats["trend_cost"] - stats["total_cost"]) / stats["total_cost"] * 100)
        if stats["total_cost"] > 0
        else 0
    )

    # Récupérer les autres données
    upcoming_renewals = db.get_upcoming_renewals(user_id)
    newsletters = db.list_newsletters(user_id)
    recent_activities = db.get_recent_activities(user_id)

    return render_template(
        "dashboard.html",
        user=user,
        active_subscriptions=stats["active_count"],
        total_monthly_cost=stats["total_cost"],
        subscription_trend=subscription_trend,
        cost_trend=cost_trend,
        upcoming_renewals=upcoming_renewals,
        newsletters=newsletters,
        total_emails=len(newsletters),
        recent_activities=recent_activities,
    )


@app.route("/subscriptions")
@login_required
def subscriptions():
    user_subscriptions = db.list_subscriptions(session["user_id"])
    total_cost = sum(sub["monthly_cost"] for sub in user_subscriptions)
    upcoming_renewals = len(
        [s for s in user_subscriptions if is_upcoming_renewal(s["renewal_date"])]
    )
    categories = list(set(sub["category"] for sub in user_subscriptions))

    return render_template(
        "subscriptions.html",
        subscriptions=user_subscriptions,
        total_cost=total_cost,
        upcoming_renewals=upcoming_renewals,
        categories=categories,
    )


@app.route("/scan-email", methods=["POST"])
@login_required
def scan_email():
    from datetime import datetime
    import imaplib
    import email
    import re

    email_to_scan = request.form.get("scan_email")
    email_password = request.form.get("scan_password")

    # Dictionnaire de correspondance domaine → catégorie
    domain_to_category = {
        "netflix": "Streaming",
        "youtube": "Streaming",
        "spotify": "Musique",
        "deezer": "Musique",
        "playstation": "Gaming",
        "xbox": "Gaming",
        "steam": "Gaming",
        "dropbox": "Cloud",
        "google": "Cloud",
        "icloud": "Cloud",
        "paypal": "Finance",
        "revolut": "Finance",
        "notion": "Productivité",
        "adobe": "Design",
        "amazon": "E-commerce",
    }

    try:
        # Connexion Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_to_scan, email_password)
        mail.select("inbox")

        # Recherche d’e-mails de confirmation
        typ, data = mail.search(None, '(SUBJECT "confirme" SUBJECT "bienvenue" SUBJECT "activation")')
        ids = data[0].split()

        found_services = set()

        for num in ids:
            typ, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg.get("From", "")
            match = re.search(r'@([a-z0-9.-]+)', sender)

            if match:
                domain = match.group(1).split(".")[0].lower()
                service_name = domain.capitalize()
                category = domain_to_category.get(domain, "Autre")
                found_services.add((service_name, category))

        # Ajout des abonnements trouvés
        for service_name, category in found_services:
            db.create_subscription(
                user_id=session["user_id"],
                service_name=service_name,
                category=category,
                start_date=datetime.now().strftime("%Y-%m-%d"),
                renewal_date=datetime.now().strftime("%Y-%m-%d"),
                monthly_cost=0.00
            )

        flash(f"{len(found_services)} abonnement(s) détecté(s) depuis {email_to_scan}.", "success")

    except Exception as e:
        flash(f"Erreur lors du scan IMAP : {str(e)}", "danger")

    return redirect(url_for("subscriptions"))



@app.route("/subscription/add", methods=["GET", "POST"])
@login_required
def add_subscription():
    if request.method == "POST":
        db.create_subscription(
            user_id=session["user_id"],
            service_name=request.form["service_name"],
            category=request.form["category"],
            start_date=request.form["start_date"],
            renewal_date=request.form["renewal_date"],
            monthly_cost=float(request.form["monthly_cost"]),
        )
        flash("Abonnement ajouté avec succès!")
        return redirect(url_for("subscriptions"))

    return render_template("add_subscription.html")


@app.route("/subscription/delete/<int:id>", methods=["POST"])
@login_required
def delete_subscription(id):
    if db.delete_subscription(id):
        flash("Abonnement supprimé avec succès!")
    else:
        flash("Erreur lors de la suppression.")
    return redirect(url_for("subscriptions"))


@app.route("/settings")
@login_required
def settings():
    user = db.get_user_by_id(session["user_id"])
    return render_template("settings.html", user=user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # Traitement du formulaire de contact ici
        # Par exemple, envoi d'email ou enregistrement dans la base de données
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        # Code pour traiter le message

        flash(
            "Votre message a été envoyé avec succès. Nous vous répondrons bientôt.",
            "success",
        )
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Vous avez été déconnecté.")
    return redirect(url_for("index"))


def is_upcoming_renewal(renewal_date):
    from datetime import datetime, timedelta

    renewal = datetime.strptime(renewal_date, "%Y-%m-%d")
    return datetime.now() <= renewal <= datetime.now() + timedelta(days=7)


if __name__ == "__main__":
    app.run(debug=True)
