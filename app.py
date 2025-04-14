from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from subDB import DBFILENAME, SubscriptionsDB, db_fetch, db_run, db_update
from functools import wraps
import smtplib
from email.mime.text import MIMEText

SMTP_EMAIL = "test@gmail.com"
SMTP_PASSWORD = "mnnq gwbi lqsb bbqz"

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
            token = db.create_reset_token(user["id"])
            reset_url = url_for("reset_password", token=token, _external=True)
            send_reset_email(user["email"], reset_url)  # tu peux utiliser SMTP ici

        flash("Si cet email existe, un lien de réinitialisation a été envoyé.", "info")
        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = db.get_user_by_token(token)

    if not user:
        flash("Lien expiré ou invalide", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            flash("Les mots de passe ne correspondent pas", "error")
            return redirect(request.url)

        db_update(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user["id"]),
            db_name=DBFILENAME,
        )
        db.invalidate_token(token)
        flash(
            "Mot de passe mis à jour avec succès. Vous pouvez vous connecter.",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


def send_reset_email(to_email, reset_url):
    subject = "Réinitialisation de votre mot de passe SubManager"
    body = f"""
Bonjour,

Vous avez demandé à réinitialiser votre mot de passe SubManager.

Cliquez ici pour créer un nouveau mot de passe :
{reset_url}

Ce lien expirera dans 1 heure.
Si vous n'avez pas demandé cette opération, ignorez cet email.

– L'équipe SubManager
    """

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"[ERREUR] Envoi email échoué : {e}")


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
    emails = db.get_emails(user_id)

    user_emails = []
    total_services = 0

    for email in emails:
        subscriptions = db.list_subscriptions_by_email(user_id, email["email"])
        services = [
            s for s in subscriptions if not s["monthly_cost"] or s["monthly_cost"] == 0
        ]
        total_services += len(services)

        user_emails.append(
            {
                "email": email["email"],
                "added_at": email["created_at"],
                "services": services,
            }
        )

    return render_template(
        "dashboard.html",
        user_emails=user_emails,
        email_count=len(emails),
        service_count=total_services,
    )


@app.route("/subscriptions")
@login_required
def subscriptions():
    user_id = session["user_id"]
    search = request.args.get("search", "").lower()
    sort = request.args.get(
        "sort", "renewal_date"
    )  # par défaut tri par date de renouvellement
    page = int(request.args.get("page", 1))
    per_page = 10

    # Récupération brute
    all_subs = db.list_subscriptions(user_id)

    # Filtrage
    if search:
        all_subs = [
            s
            for s in all_subs
            if search in s["service_name"].lower()
            or (s.get("category") and search in s["category"].lower())
        ]

    # Tri
    if sort == "cost":
        all_subs.sort(key=lambda s: s["monthly_cost"] or 0, reverse=True)
    elif sort == "service":
        all_subs.sort(key=lambda s: s["service_name"].lower())
    else:  # renewal_date
        all_subs.sort(key=lambda s: s["renewal_date"] or "")

    # Pagination
    total = len(all_subs)
    pages = (total + per_page - 1) // per_page
    subs = all_subs[(page - 1) * per_page : page * per_page]

    return render_template(
        "subscriptions.html",
        subscriptions=subs,
        total=total,
        page=page,
        pages=pages,
        search=search,
        sort=sort,
    )


@app.route("/scan-email", methods=["POST"])
@login_required
def scan_email():
    import imaplib, email, re
    from datetime import datetime
    from email.header import decode_header

    email_to_scan = request.form.get("scan_email")
    email_password = request.form.get("scan_password")
    since_date = request.form.get("scan_since")  # format YYYY-MM-DD

    keywords = [
        "inscription",
        "confirmation",
        "activation",
        "bienvenue",
        "account created",
        "welcome",
    ]
    domain_to_category = {
        "netflix": "Streaming",
        "spotify": "Musique",
        "deezer": "Musique",
        "youtube": "Streaming",
        "dropbox": "Cloud",
        "adobe": "Design",
        "amazon": "E-commerce",
        "paypal": "Finance",
        "revolut": "Finance",
        "notion": "Productivité",
        "steam": "Gaming",
        "xbox": "Gaming",
        "playstation": "Gaming",
    }

    try:
        # Connexion IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_to_scan, email_password)
        mail.select("inbox")

        # Générer la requête de recherche IMAP
        search_parts = [f'SUBJECT "{kw}"' for kw in keywords]
        search_query = "OR " * (len(keywords) - 1) + " ".join(search_parts)

        # Ajouter la date si précisée
        if since_date:
            imap_date = datetime.strptime(since_date, "%Y-%m-%d").strftime(
                "%d-%b-%Y"
            )  # ex: 14-Apr-2025
            search_query += f" SINCE {imap_date}"

        typ, data = mail.search(None, f"({search_query})")

        found_services = set()
        for num in data[0].split():
            typ, msg_data = mail.fetch(num, "(RFC822)")
            raw_msg = msg_data[0][1]
            msg = email.message_from_bytes(raw_msg)

            # Décodage de l’expéditeur
            sender = msg.get("From", "")
            match = re.search(r"@([a-z0-9.-]+)", sender)
            if match:
                domain = match.group(1).split(".")[0].lower()
                service_name = domain.capitalize()
                category = domain_to_category.get(domain, "Autre")
                found_services.add((service_name, category))

        # Enregistrer l'email si pas encore connue
        db.save_email(session["user_id"], email_to_scan)

        # Enregistrer les services (éviter doublons)
        for service_name, category in found_services:
            existing = db_fetch(
                """SELECT id FROM subscriptions
                   WHERE user_id = ? AND email = ? AND service_name = ?""",
                (session["user_id"], email_to_scan, service_name),
                db_name=DBFILENAME,
            )
            if not existing:
                db.create_subscription(
                    user_id=session["user_id"],
                    service_name=service_name,
                    category=category,
                    start_date=datetime.now().strftime("%Y-%m-%d"),
                    renewal_date=datetime.now().strftime("%Y-%m-%d"),
                    monthly_cost=0.00,
                    email=email_to_scan,
                )

        flash(
            f"{len(found_services)} service(s) détecté(s) à partir de {email_to_scan}.",
            "success",
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        flash(f"Erreur lors du scan : {str(e)}", "danger")

    return redirect(url_for("subscriptions"))


@app.route("/delete_email", methods=["POST"])
@login_required
def delete_email():
    email_to_delete = request.form.get("email")
    user_id = session["user_id"]

    # Supprimer d'abord les abonnements liés à cet email
    db_run(
        "DELETE FROM subscriptions WHERE user_id = ? AND email = ?",
        (user_id, email_to_delete),
        db_name=DBFILENAME,
    )

    # Supprimer l'adresse email de la table emails
    db_run(
        "DELETE FROM emails WHERE user_id = ? AND email = ?",
        (user_id, email_to_delete),
        db_name=DBFILENAME,
    )

    flash(f"L'adresse {email_to_delete} a été supprimée avec succès.", "success")
    return redirect(url_for("dashboard"))


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


@app.route("/subscription/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_subscription(id):
    sub = db.get_subscription(id)

    if not sub or sub["user_id"] != session["user_id"]:
        flash("Abonnement introuvable ou accès interdit", "danger")
        return redirect(url_for("subscriptions"))

    if request.method == "POST":
        service_name = request.form.get("service_name")
        category = request.form.get("category")
        start_date = request.form.get("start_date")
        renewal_date = request.form.get("renewal_date")
        monthly_cost = float(request.form.get("monthly_cost"))

        db.update_subscription(
            id, service_name, category, start_date, renewal_date, monthly_cost
        )
        flash("Abonnement mis à jour avec succès", "success")
        return redirect(url_for("subscriptions"))

    return render_template("edit_subscription.html", subscription=sub)


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
