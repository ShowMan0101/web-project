import sqlite3
import json
from datetime import datetime, timedelta

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

        # Création des tables (sans suppression en dur)
        db_run(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                firstname TEXT,
                lastname TEXT,
                email_notifications BOOLEAN DEFAULT 1,
                renewal_reminders BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """, db_name=self.db_path
        )

        db_run(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                category TEXT,
                status TEXT DEFAULT 'active',
                start_date DATE,
                renewal_date DATE,
                monthly_cost REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """, db_name=self.db_path
        )

        db_run(
            """
            CREATE TABLE IF NOT EXISTS newsletters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                newsletter_name TEXT NOT NULL,
                subscription_date DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """, db_name=self.db_path
        )

    # Users
    def create_user(self, email, password_hash):
        return db_insert(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
            db_name=self.db_path
        )

    def get_user(self, email):
        return db_fetch("SELECT * FROM users WHERE email = ?", (email,), db_name=self.db_path)

    def get_user_by_id(self, user_id):
        return db_fetch("SELECT * FROM users WHERE id = ?", (user_id,), db_name=self.db_path)

    # Subscriptions
    def list_subscriptions(self, user_id):
        return db_fetch(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY renewal_date",
            (user_id,), all=True, db_name=self.db_path
        ) or []

    def create_subscription(self, user_id, service_name, category, start_date, renewal_date, monthly_cost):
        return db_insert(
            """
            INSERT INTO subscriptions (user_id, service_name, category, start_date, renewal_date, monthly_cost)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, service_name, category, start_date, renewal_date, monthly_cost),
            db_name=self.db_path
        )

    def update_subscription(self, id, service_name, category, start_date, renewal_date, monthly_cost):
        return db_update(
            """
            UPDATE subscriptions
            SET service_name = ?, category = ?, start_date = ?, renewal_date = ?, monthly_cost = ?
            WHERE id = ?
            """,
            (service_name, category, start_date, renewal_date, monthly_cost, id),
            db_name=self.db_path
        ) > 0

    def delete_subscription(self, id):
        return db_update("DELETE FROM subscriptions WHERE id = ?", (id,), db_name=self.db_path) > 0

    def get_subscription(self, id):
        return db_fetch("SELECT * FROM subscriptions WHERE id = ?", (id,), db_name=self.db_path)

    def get_subscription_stats(self, user_id):
        active_query = """
        SELECT COUNT(*) as count, SUM(monthly_cost) as total_cost
        FROM subscriptions
        WHERE user_id = ? AND status = 'active'
        """
        trend_query = """
        SELECT COUNT(*) as count, SUM(monthly_cost) as total_cost
        FROM subscriptions
        WHERE user_id = ? AND created_at >= date('now', '-1 month')
        """
        active_stats = db_fetch(active_query, (user_id,), db_name=self.db_path)
        trend_stats = db_fetch(trend_query, (user_id,), db_name=self.db_path)

        return {
            "active_count": active_stats["count"] or 0 if active_stats else 0,
            "total_cost": active_stats["total_cost"] or 0 if active_stats else 0,
            "trend_count": trend_stats["count"] or 0 if trend_stats else 0,
            "trend_cost": trend_stats["total_cost"] or 0 if trend_stats else 0,
        }

    def get_upcoming_renewals(self, user_id, days=7):
        target_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        return db_fetch(
            """
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active' AND renewal_date <= ?
            ORDER BY renewal_date
            """,
            (user_id, target_date),
            all=True, db_name=self.db_path
        ) or []

    # Newsletters
    def list_newsletters(self, user_id):
        return db_fetch(
            "SELECT * FROM newsletters WHERE user_id = ?",
            (user_id,), all=True, db_name=self.db_path
        ) or []

    def add_newsletter(self, user_id, newsletter_name):
        return db_insert(
            "INSERT INTO newsletters (user_id, newsletter_name) VALUES (?, ?)",
            (user_id, newsletter_name), db_name=self.db_path
        )

    def delete_newsletter(self, id):
        return db_update("DELETE FROM newsletters WHERE id = ?", (id,), db_name=self.db_path) > 0

    # Export / import
    def save(self, json_path=None):
        json_path = json_path or self.json_path
        data = {
            "users": db_fetch("SELECT * FROM users", all=True, db_name=self.db_path),
            "subscriptions": db_fetch("SELECT * FROM subscriptions", all=True, db_name=self.db_path),
            "newsletters": db_fetch("SELECT * FROM newsletters", all=True, db_name=self.db_path),
        }
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=4, default=str)
            return True
        except Exception as e:
            print(f"Erreur lors de l'export : {e}")
            return False

    def load(self, json_path=None):
        json_path = json_path or self.json_path
        try:
            with open(json_path, "r") as fh:
                data = json.load(fh)
            for user in data.get("users", []):
                db_insert("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                          (user["id"], user["email"], user["password_hash"]),
                          db_name=self.db_path)
            for sub in data.get("subscriptions", []):
                db_insert(
                    """INSERT INTO subscriptions
                    (id, user_id, service_name, category, status, start_date, renewal_date, monthly_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sub["id"], sub["user_id"], sub["service_name"], sub["category"],
                     sub["status"], sub["start_date"], sub["renewal_date"], sub["monthly_cost"]),
                    db_name=self.db_path
                )
            for news in data.get("newsletters", []):
                db_insert("INSERT INTO newsletters (id, user_id, newsletter_name) VALUES (?, ?, ?)",
                          (news["id"], news["user_id"], news["newsletter_name"]),
                          db_name=self.db_path)
            return True
        except Exception as e:
            print(f"Erreur lors de l'import JSON : {e}")
            return False
