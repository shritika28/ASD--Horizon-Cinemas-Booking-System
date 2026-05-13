"""
src/utils/loyalty_manager.py
"""

import math
import datetime
from src.database.db_connection import get_connection

# ── Tier thresholds ────────────────────────────────────────────────────────────
TIER_BRONZE = "bronze"
TIER_SILVER = "silver"
TIER_GOLD = "gold"

TIER_COLOURS = {
    TIER_BRONZE: "#cd7f32",
    TIER_SILVER: "#94a3b8",
    TIER_GOLD: "#f59e0b",
}


def init_loyalty_db():
    """Create loyalty tables on startup if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_accounts (
            account_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name  TEXT    NOT NULL,
            customer_email TEXT    NOT NULL UNIQUE,
            total_points   INTEGER NOT NULL DEFAULT 0,
            tier           TEXT    NOT NULL DEFAULT 'bronze'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_transactions (
            tx_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id     INTEGER NOT NULL,
            booking_id     TEXT,
            points_earned  INTEGER NOT NULL DEFAULT 0,
            points_redeemed INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT    NOT NULL,
            FOREIGN KEY (account_id) REFERENCES loyalty_accounts(account_id)
        )
    """)
    conn.commit()


def calculate_tier(total_points: int) -> str:
    """Return tier string based on total_points."""
    if total_points >= 500:
        return TIER_GOLD
    elif total_points >= 200:
        return TIER_SILVER
    return TIER_BRONZE


def calculate_points(total_cost: float) -> int:
    """1 point per £1 spent, floored."""
    return math.floor(total_cost)


def award_points(customer_name: str, customer_email: str, booking_id: str, total_cost: float) -> dict:
    """
    Upsert a loyalty account for customer_email, award points, insert a transaction.
    Returns the updated account dict.
    """
    conn = get_connection()
    points = calculate_points(total_cost)
    now = datetime.datetime.now().isoformat()

    row = conn.execute(
        "SELECT * FROM loyalty_accounts WHERE customer_email = ?", (customer_email,)
    ).fetchone()

    if row:
        account_id = row["account_id"]
        new_total = row["total_points"] + points
        new_tier = calculate_tier(new_total)
        conn.execute(
            "UPDATE loyalty_accounts SET total_points = ?, tier = ?, customer_name = ? WHERE account_id = ?",
            (new_total, new_tier, customer_name, account_id)
        )
    else:
        new_total = points
        new_tier = calculate_tier(new_total)
        cur = conn.execute(
            "INSERT INTO loyalty_accounts (customer_name, customer_email, total_points, tier) VALUES (?, ?, ?, ?)",
            (customer_name, customer_email, new_total, new_tier)
        )
        account_id = cur.lastrowid

    conn.execute(
        """
        INSERT INTO loyalty_transactions (
            account_id, booking_id, points_earned, points_redeemed, created_at
        )
        VALUES (?, ?, ?, 0, ?)
        """,
        (account_id, booking_id, points, now)
    )
    conn.commit()

    return {
        "account_id": account_id,
        "total_points": new_total,
        "tier": new_tier,
        "points_earned": points
    }


def deduct_points(customer_email: str, booking_id: str, total_cost: float):
    """
    On cancellation, insert a negative transaction to deduct points.
    Clamps total_points to 0 minimum.
    """
    conn = get_connection()
    points_to_deduct = calculate_points(total_cost)
    now = datetime.datetime.now().isoformat()

    row = conn.execute(
        "SELECT * FROM loyalty_accounts WHERE customer_email = ?", (customer_email,)
    ).fetchone()
    if not row:
        return

    account_id = row["account_id"]
    new_total = max(0, row["total_points"] - points_to_deduct)
    new_tier = calculate_tier(new_total)

    conn.execute(
        "UPDATE loyalty_accounts SET total_points = ?, tier = ? WHERE account_id = ?",
        (new_total, new_tier, account_id)
    )
    conn.execute(
        """
        INSERT INTO loyalty_transactions (
            account_id, booking_id, points_earned, points_redeemed, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, booking_id, -points_to_deduct, 0, now)
    )
    conn.commit()


def get_account(customer_email: str) -> dict | None:
    """Return full account info plus last 5 transactions, or None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM loyalty_accounts WHERE customer_email = ?", (customer_email,)
    ).fetchone()
    if not row:
        return None

    txs = conn.execute(
        "SELECT * FROM loyalty_transactions WHERE account_id = ? ORDER BY created_at DESC LIMIT 5",
        (row["account_id"],)
    ).fetchall()

    return {
        "account_id": row["account_id"],
        "customer_name": row["customer_name"],
        "customer_email": row["customer_email"],
        "total_points": row["total_points"],
        "tier": row["tier"],
        "transactions": [dict(t) for t in txs]
    }
