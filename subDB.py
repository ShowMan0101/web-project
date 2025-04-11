import sqlite3
import json
from datetime import datetime

DBFILENAME = "subscriptions.sqlite"


def db_fetch(query, args=(), all=False, db_name=DBFILENAME):
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, args)
        if all:
            res = cur.fetchall()
            if res:
                res = [dict(e) for e in res]
        else:
            res = cur.fetchone()
            if res:
                res = dict(res)
    return res


def db_insert(query, args=(), db_name=DBFILENAME):
    with sqlite3.connect(db_name) as conn:
        cur = conn.execute(query, args)
        conn.commit()
        return cur.lastrowid


def db_run(query, args=(), db_name=DBFILENAME):
    with sqlite3.connect(db_name) as conn:
        cur = conn.execute(query, args)
        conn.commit()


def db_update(query, args=(), db_name=DBFILENAME):
    with sqlite3.connect(db_name) as conn:
        cur = conn.execute(query, args)
        conn.commit()
        return cur.rowcount


class SubscriptionsDB:
    def __init__(self, db_path=None, json_path=None):
        self.db_path = db_path if db_path else DBFILENAME
        self.json_path = json_path if json_path else "subscriptions.json"

        # Drop existing tables
        db_run("DROP TABLE IF EXISTS users", db_name=self.db_path)
        db_run("DROP TABLE IF EXISTS subscriptions", db_name=self.db_path)
        db_run("DROP TABLE IF EXISTS newsletters", db_name=self.db_path)

        # Create tables
        db_run(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                firstname TEXT,
                lastname TEXT,
                email_notifications BOOLEAN DEFAULT 1,
                renewal_reminders BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            db_name=self.db_path,
        )

        db_run(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                category TEXT,
                status TEXT DEFAULT 'active',
                start_date DATE,
                renewal_date DATE,
                monthly_cost REAL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """,
            db_name=self.db_path,
        )

        db_run(
            """
            CREATE TABLE newsletters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                newsletter_name TEXT NOT NULL,
                subscription_date DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """,
            db_name=self.db_path,
        )

    # User Management
    def create_user(self, email, password_hash):
        query = "INSERT INTO users (email, password_hash) VALUES (?, ?)"
        return db_insert(query, (email, password_hash), db_name=self.db_path)

    def get_user(self, email):
        query = "SELECT * FROM users WHERE email = ?"
        return db_fetch(query, (email,), db_name=self.db_path)

    def get_user_by_id(self, user_id):
        """Récupère un utilisateur par son ID."""
        query = "SELECT * FROM users WHERE id = ?"
        return db_fetch(query, (user_id,), db_name=self.db_path)

    def get_recent_activities(self, user_id, limit=5):
        """Récupère les activités récentes d'un utilisateur."""
        query = """
        SELECT * FROM logs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """
        return db_fetch(query, (user_id, limit), all=True, db_name=self.db_path)

    def list_newsletters(self, user_id):
        """Récupère les newsletters d'un utilisateur."""
        query = "SELECT * FROM newsletters WHERE user_id = ?"
        return db_fetch(query, (user_id,), all=True, db_name=self.db_path)

    def get_subscription_stats(self, user_id):
        """Récupère les statistiques des abonnements."""
        # Total des abonnements actifs
        active_query = """
        SELECT COUNT(*) as count, SUM(monthly_cost) as total_cost
        FROM subscriptions
        WHERE user_id = ? AND status = 'active'
        """
        active_stats = db_fetch(active_query, (user_id,), db_name=self.db_path)

        # Tendance (comparaison avec le mois précédent)
        trend_query = """
        SELECT COUNT(*) as count, SUM(monthly_cost) as total_cost
        FROM subscriptions
        WHERE user_id = ?
        AND created_at >= date('now', '-1 month')
        """
        trend_stats = db_fetch(trend_query, (user_id,), db_name=self.db_path)

        return {
            "active_count": active_stats["count"] if active_stats else 0,
            "total_cost": active_stats["total_cost"] if active_stats else 0,
            "trend_count": trend_stats["count"] if trend_stats else 0,
            "trend_cost": trend_stats["total_cost"] if trend_stats else 0,
        }

    def get_upcoming_renewals(self, user_id, days=7):
        """Récupère les abonnements à renouveler prochainement."""
        query = """
        SELECT * FROM subscriptions
        WHERE user_id = ?
        AND status = 'active'
        AND renewal_date <= date('now', '+? days')
        ORDER BY renewal_date
        """
        return db_fetch(query, (user_id, days), all=True, db_name=self.db_path)

    # Subscription Management
    def list_subscriptions(self, user_id):
        query = "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY renewal_date"
        subs = db_fetch(query, (user_id,), all=True, db_name=self.db_path)
        return subs if subs else []

    def create_subscription(
        self, user_id, service_name, category, start_date, renewal_date, monthly_cost
    ):
        query = """
        INSERT INTO subscriptions
        (user_id, service_name, category, start_date, renewal_date, monthly_cost)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        args = (user_id, service_name, category, start_date, renewal_date, monthly_cost)
        return db_insert(query, args, db_name=self.db_path)

    def get_subscription(self, id):
        query = "SELECT * FROM subscriptions WHERE id = ?"
        return db_fetch(query, (id,), db_name=self.db_path)

    def update_subscription(
        self, id, service_name, category, start_date, renewal_date, monthly_cost
    ):
        query = """
        UPDATE subscriptions
        SET service_name = ?, category = ?, start_date = ?,
            renewal_date = ?, monthly_cost = ?
        WHERE id = ?
        """
        args = (service_name, category, start_date, renewal_date, monthly_cost, id)
        return db_update(query, args, db_name=self.db_path) > 0

    def delete_subscription(self, id):
        query = "DELETE FROM subscriptions WHERE id = ?"
        return db_update(query, (id,), db_name=self.db_path) > 0

    # Newsletter Management
    def list_newsletters(self, user_id):
        query = "SELECT * FROM newsletters WHERE user_id = ?"
        news = db_fetch(query, (user_id,), all=True, db_name=self.db_path)
        return news if news else []

    def add_newsletter(self, user_id, newsletter_name):
        query = "INSERT INTO newsletters (user_id, newsletter_name) VALUES (?, ?)"
        return db_insert(query, (user_id, newsletter_name), db_name=self.db_path)

    def delete_newsletter(self, id):
        query = "DELETE FROM newsletters WHERE id = ?"
        return db_update(query, (id,), db_name=self.db_path) > 0

    # Data Export/Import
    def save(self, json_path=None):
        if not json_path:
            json_path = self.json_path

        data = {
            "users": db_fetch("SELECT * FROM users", all=True, db_name=self.db_path),
            "subscriptions": db_fetch(
                "SELECT * FROM subscriptions", all=True, db_name=self.db_path
            ),
            "newsletters": db_fetch(
                "SELECT * FROM newsletters", all=True, db_name=self.db_path
            ),
        }

        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=4, default=str)
            return True
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            return False

    def load(self, json_path=None):
        if not json_path:
            json_path = self.json_path

        try:
            with open(json_path, "r") as fh:
                data = json.load(fh)

                # Load users
                for user in data.get("users", []):
                    db_insert(
                        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                        (user["id"], user["email"], user["password_hash"]),
                        db_name=self.db_path,
                    )

                # Load subscriptions
                for sub in data.get("subscriptions", []):
                    db_insert(
                        """INSERT INTO subscriptions
                           (id, user_id, service_name, category, status,
                            start_date, renewal_date, monthly_cost)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sub["id"],
                            sub["user_id"],
                            sub["service_name"],
                            sub["category"],
                            sub["status"],
                            sub["start_date"],
                            sub["renewal_date"],
                            sub["monthly_cost"],
                        ),
                        db_name=self.db_path,
                    )

                # Load newsletters
                for news in data.get("newsletters", []):
                    db_insert(
                        "INSERT INTO newsletters (id, user_id, newsletter_name) VALUES (?, ?, ?)",
                        (news["id"], news["user_id"], news["newsletter_name"]),
                        db_name=self.db_path,
                    )
                return True
        except Exception as e:
            print(f"Error loading from JSON: {e}")
            return False
