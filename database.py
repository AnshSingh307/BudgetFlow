"""SQLite storage. Connections are short-lived; multi-step changes are atomic."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from utils.validators import (
    CURRENCIES,
    EXPENSE_CATEGORIES,
    clean_text,
    iso_date,
    month_key,
    transaction_values,
    validate_paise,
)

DEFAULT_DATABASE = Path(__file__).parent / "data" / "budgetflow.db"


class Database:
    def __init__(self, path=None):
        self.path = Path(
            path or os.environ.get("BUDGETFLOW_DB", DEFAULT_DATABASE)
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
                    amount_paise INTEGER NOT NULL
                        CHECK(typeof(amount_paise)='integer' AND amount_paise>0),
                    category TEXT NOT NULL,
                    transaction_date TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    payment_method TEXT NOT NULL,
                    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_transactions_date
                    ON transactions(transaction_date, kind);
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount_paise INTEGER NOT NULL
                        CHECK(typeof(amount_paise)='integer' AND amount_paise>0),
                    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
                    UNIQUE(month, category)
                );
                CREATE TABLE IF NOT EXISTS savings_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    target_paise INTEGER NOT NULL
                        CHECK(typeof(target_paise)='integer' AND target_paise>0),
                    target_date TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
                    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS goal_contributions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER NOT NULL REFERENCES savings_goals(id)
                        ON DELETE CASCADE,
                    amount_paise INTEGER NOT NULL
                        CHECK(typeof(amount_paise)='integer' AND amount_paise>0),
                    contribution_date TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))
                );
                CREATE INDEX IF NOT EXISTS idx_contributions_goal
                    ON goal_contributions(goal_id);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO settings(key,value) VALUES ('currency','INR');
                PRAGMA user_version = 1;
            """)

    def transactions(self, *, kind=None, start=None, end=None):
        clauses, parameters = [], []
        if kind is not None:
            if kind not in ("income", "expense"):
                raise ValueError("Invalid transaction type.")
            clauses.append("kind=?")
            parameters.append(kind)
        if start is not None:
            clauses.append("transaction_date>=?")
            parameters.append(iso_date(start))
        if end is not None:
            clauses.append("transaction_date<=?")
            parameters.append(iso_date(end))
        if start and end and iso_date(start) > iso_date(end):
            raise ValueError("Start date must be on or before end date.")
        # Only fixed SQL fragments are joined; all values are parameters.
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM transactions"
                + where
                + " ORDER BY transaction_date DESC, id DESC",
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def add_transaction(
        self,
        kind,
        amount_paise,
        category,
        transaction_date,
        description="",
        payment_method="UPI",
    ):
        values = transaction_values(
            kind,
            amount_paise,
            category,
            transaction_date,
            description,
            payment_method,
        )
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transactions(kind,amount_paise,category,
                    transaction_date,description,payment_method)
                VALUES (?,?,?,?,?,?)
            """,
                values,
            )
            return cursor.lastrowid

    def update_transaction(
        self,
        transaction_id,
        kind,
        amount_paise,
        category,
        transaction_date,
        description="",
        payment_method="UPI",
    ):
        values = transaction_values(
            kind,
            amount_paise,
            category,
            transaction_date,
            description,
            payment_method,
        )
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE transactions SET kind=?,amount_paise=?,category=?,
                    transaction_date=?,description=?,payment_method=?,is_demo=0
                WHERE id=?
            """,
                (*values, transaction_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    "Transaction no longer exists. Refresh the page."
                )

    def delete_transaction(self, transaction_id):
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM transactions WHERE id=?", (transaction_id,)
            )
            if cursor.rowcount != 1:
                raise ValueError("Transaction no longer exists.")

    def import_transactions(self, records):
        # Validate the entire file before inserting a single row.
        values = [transaction_values(**record) for record in records]
        with self.connection() as connection:
            connection.executemany(
                """
                INSERT INTO transactions(kind,amount_paise,category,
                    transaction_date,description,payment_method) VALUES (?,?,?,?,?,?)
            """,
                values,
            )
        return len(values)

    def budgets(self, month):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM budgets WHERE month=? ORDER BY category",
                (month_key(month),),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_budget_plan(self, month, total_paise, allocations):
        month = month_key(month)
        validate_paise(total_paise)
        for category, amount in allocations.items():
            if category not in EXPENSE_CATEGORIES:
                raise ValueError("Unknown expense category.")
            validate_paise(amount, allow_zero=True)
        if sum(allocations.values()) > total_paise:
            raise ValueError(
                "Category allocations cannot exceed the monthly limit."
            )
        values = [(month, "Overall", total_paise)]
        values += [
            (month, category, amount)
            for category, amount in allocations.items()
            if amount > 0
        ]
        with self.connection() as connection:
            connection.execute("DELETE FROM budgets WHERE month=?", (month,))
            connection.executemany(
                """
                INSERT INTO budgets(month,category,amount_paise) VALUES (?,?,?)
            """,
                values,
            )

    def delete_budget_plan(self, month):
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM budgets WHERE month=?", (month_key(month),)
            )

    def goals(self):
        with self.connection() as connection:
            rows = connection.execute("""
                SELECT g.*, COALESCE(SUM(c.amount_paise),0) AS saved_paise
                FROM savings_goals g LEFT JOIN goal_contributions c ON g.id=c.goal_id
                GROUP BY g.id ORDER BY g.completed, g.target_date, g.id
            """).fetchall()
        return [dict(row) for row in rows]

    def add_goal(self, name, target_paise, target_date):
        values = (
            clean_text(name, label="Goal name", maximum=80, required=True),
            validate_paise(target_paise),
            iso_date(target_date),
        )
        with self.connection() as connection:
            return connection.execute(
                """
                INSERT INTO savings_goals(name,target_paise,target_date) VALUES (?,?,?)
            """,
                values,
            ).lastrowid

    def update_goal(self, goal_id, name, target_paise, target_date):
        values = (
            clean_text(name, label="Goal name", maximum=80, required=True),
            validate_paise(target_paise),
            iso_date(target_date),
            goal_id,
        )
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT completed FROM savings_goals WHERE id=?",
                (goal_id,),
            ).fetchone()
            if not existing:
                raise ValueError("Goal no longer exists.")
            saved = connection.execute(
                "SELECT COALESCE(SUM(amount_paise),0) FROM goal_contributions WHERE goal_id=?",
                (goal_id,),
            ).fetchone()[0]
            if existing["completed"] and saved < target_paise:
                raise ValueError(
                    "Reopen the goal before raising its target above contributions."
                )
            connection.execute(
                """
                UPDATE savings_goals SET name=?,target_paise=?,target_date=?,is_demo=0
                WHERE id=?
            """,
                values,
            )

    def complete_goal(self, goal_id, completed=True):
        with self.connection() as connection:
            goal = connection.execute(
                "SELECT target_paise FROM savings_goals WHERE id=?",
                (goal_id,),
            ).fetchone()
            if not goal:
                raise ValueError("Goal no longer exists.")
            saved = connection.execute(
                "SELECT COALESCE(SUM(amount_paise),0) FROM goal_contributions WHERE goal_id=?",
                (goal_id,),
            ).fetchone()[0]
            if completed and saved < goal["target_paise"]:
                raise ValueError(
                    "Reach the target before marking the goal complete."
                )
            connection.execute(
                "UPDATE savings_goals SET completed=?,is_demo=0 WHERE id=?",
                (int(bool(completed)), goal_id),
            )

    def delete_goal(self, goal_id):
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM savings_goals WHERE id=?", (goal_id,)
            )
            if cursor.rowcount != 1:
                raise ValueError("Goal no longer exists.")

    def contributions(self, goal_id):
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM goal_contributions WHERE goal_id=?
                ORDER BY contribution_date DESC, id DESC
            """,
                (goal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_contribution(
        self, goal_id, amount_paise, contribution_date, note=""
    ):
        validate_paise(amount_paise)
        contribution_date = iso_date(contribution_date)
        note = clean_text(note)
        with self.connection() as connection:
            goal = connection.execute(
                "SELECT completed FROM savings_goals WHERE id=?",
                (goal_id,),
            ).fetchone()
            if not goal:
                raise ValueError("Goal no longer exists.")
            if goal["completed"]:
                raise ValueError(
                    "Reopen this completed goal to add contributions."
                )
            cursor = connection.execute(
                """
                INSERT INTO goal_contributions(goal_id,amount_paise,contribution_date,note)
                VALUES (?,?,?,?)
            """,
                (goal_id, amount_paise, contribution_date, note),
            )
            # A personal contribution makes a demo goal personal, preserving it on reset.
            connection.execute(
                "UPDATE savings_goals SET is_demo=0 WHERE id=?", (goal_id,)
            )
            return cursor.lastrowid

    def delete_contribution(self, contribution_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT goal_id FROM goal_contributions WHERE id=?",
                (contribution_id,),
            ).fetchone()
            if not row:
                raise ValueError("Contribution no longer exists.")
            connection.execute(
                "DELETE FROM goal_contributions WHERE id=?", (contribution_id,)
            )
            # Reopen after correcting history so completion cannot become misleading.
            connection.execute(
                "UPDATE savings_goals SET completed=0,is_demo=0 WHERE id=?",
                (row[0],),
            )

    def setting(self, key):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set_currency(self, code):
        if code not in CURRENCIES:
            raise ValueError("Unsupported currency.")
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO settings(key,value) VALUES ('currency',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
                (code,),
            )

    def demo_counts(self):
        with self.connection() as connection:
            return {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE is_demo=1",
                ).fetchone()[0]
                for table in (
                    "transactions",
                    "budgets",
                    "savings_goals",
                    "goal_contributions",
                )
            }

    def load_demo(self, today=None):
        """Insert a visibly synthetic, deterministic four-month demonstration once."""
        today = today or date.today()
        with self.connection() as connection:
            if connection.execute(
                "SELECT value FROM settings WHERE key='demo_loaded'",
            ).fetchone():
                raise ValueError(
                    "Demo already loaded. Remove demo records before loading again."
                )
            for offset in range(3, -1, -1):
                ordinal = today.year * 12 + today.month - 1 - offset
                year, month = divmod(ordinal, 12)
                month += 1
                key = f"{year:04d}-{month:02d}"
                # For the current month use only dates on or before today.
                max_day = today.day if offset == 0 else 28
                records = [
                    (
                        "income",
                        3_800_000,
                        "Salary",
                        1,
                        "Demo · Monthly income",
                        "Bank Transfer",
                    ),
                    (
                        "income",
                        450_000 + offset * 25_000,
                        "Freelancing",
                        5,
                        "Demo · Design project",
                        "UPI",
                    ),
                ]
                expense_data = [
                    ("Rent", 950_000),
                    ("Food", 280_000 + (3 - offset) * 30_000),
                    ("Transportation", 140_000),
                    ("Shopping", 220_000),
                    ("Education", 180_000),
                    ("Entertainment", 160_000),
                    ("Healthcare", 70_000),
                    ("Bills", 190_000),
                    ("Subscriptions", 89_900),
                    ("Travel", 120_000),
                ]
                for index, (category, amount) in enumerate(expense_data):
                    for split in range(2):
                        day = min(2 + index * 2 + split * 3, max_day)
                        records.append(
                            (
                                "expense",
                                amount // 2,
                                category,
                                day,
                                f"Demo · {category.lower()}",
                                ("UPI", "Debit Card", "Cash")[index % 3],
                            )
                        )
                connection.executemany(
                    """
                    INSERT INTO transactions(kind,amount_paise,category,
                        transaction_date,description,payment_method,is_demo)
                    VALUES (?,?,?,?,?,?,1)
                """,
                    [
                        (
                            kind,
                            amount,
                            category,
                            f"{key}-{min(day, max_day):02d}",
                            description,
                            method,
                        )
                        for kind, amount, category, day, description, method in records
                    ],
                )
                existing_plan = connection.execute(
                    "SELECT 1 FROM budgets WHERE month=? LIMIT 1", (key,)
                ).fetchone()
                demo_limits = (
                    ()
                    if existing_plan
                    else (
                        ("Overall", 3_000_000),
                        ("Food", 500_000),
                        ("Entertainment", 180_000),
                        ("Shopping", 300_000),
                    )
                )
                for category, limit in demo_limits:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO budgets(month,category,amount_paise,is_demo)
                        VALUES (?,?,?,1)
                    """,
                        (key, category, limit),
                    )
            for name, target, saved, days in (
                ("New Laptop", 6_000_000, 2_100_000, 120),
                ("Vacation", 2_500_000, 850_000, 90),
                ("Emergency Fund", 5_000_000, 1_650_000, 180),
            ):
                goal_id = connection.execute(
                    """
                    INSERT INTO savings_goals(name,target_paise,target_date,is_demo)
                    VALUES (?,?,?,1)
                """,
                    (name, target, (today + timedelta(days=days)).isoformat()),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO goal_contributions(goal_id,amount_paise,
                        contribution_date,note,is_demo) VALUES (?,?,?,?,1)
                """,
                    (goal_id, saved, today.isoformat(), "Demo contribution"),
                )
            connection.execute(
                "INSERT INTO settings VALUES ('demo_loaded','1')"
            )

    def remove_demo(self):
        with self.connection() as connection:
            connection.execute("DELETE FROM transactions WHERE is_demo=1")
            connection.execute("DELETE FROM budgets WHERE is_demo=1")
            connection.execute(
                "DELETE FROM goal_contributions WHERE is_demo=1"
            )
            connection.execute("DELETE FROM savings_goals WHERE is_demo=1")
            connection.execute(
                "UPDATE savings_goals SET completed=0 WHERE completed=1 AND "
                "target_paise > (SELECT COALESCE(SUM(amount_paise),0) "
                "FROM goal_contributions WHERE goal_id=savings_goals.id)"
            )
            connection.execute("DELETE FROM settings WHERE key='demo_loaded'")
