"""
src/utils/waitlist_manager.py
"""

import datetime
from src.database.db_connection import get_connection


def init_waitlist_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            waitlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            showing_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            num_tickets INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting', -- 'waiting', 'offered', 'confirmed', 'expired'
            offered_at TEXT,
            FOREIGN KEY (showing_id) REFERENCES showings(showing_id)
        )
    """)
    conn.commit()


def join_waitlist(showing_id: int, name: str, email: str, phone: str, num_tickets: int):
    conn = get_connection()
    now = datetime.datetime.now().isoformat()
    conn.execute("""
        INSERT INTO waitlist (showing_id, customer_name, customer_email, customer_phone, num_tickets, joined_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'waiting')
    """, (showing_id, name, email, phone, num_tickets, now))
    conn.commit()


def process_waitlist(showing_id: int, freed_seats: int):
    """
    Called when a booking is cancelled.
    Expires old offers and then checks if we can offer seats to the next person.
    """
    conn = get_connection()
    now = datetime.datetime.now()

    # 1. Expire offers older than 30 minutes globally
    conn.execute("""
        UPDATE waitlist
        SET status = 'expired'
        WHERE status = 'offered' AND offered_at IS NOT NULL
        AND (julianday(?) - julianday(offered_at)) * 24 * 60 > 30
    """, (now.isoformat(),))
    conn.commit()

    # 2. Query waiting entries for this showing
    waiting = conn.execute("""
        SELECT waitlist_id, customer_name, num_tickets
        FROM waitlist
        WHERE showing_id = ? AND status = 'waiting'
        ORDER BY joined_at ASC
    """, (showing_id,)).fetchall()

    film_info = conn.execute("""
        SELECT f.title, sh.show_time
        FROM showings sh
        JOIN films f ON sh.film_id = f.film_id
        WHERE sh.showing_id = ?
    """, (showing_id,)).fetchone()

    film_title = film_info["title"] if film_info else "Unknown Film"
    show_time = film_info["show_time"] if film_info else "Unknown Time"

    for w in waiting:
        if w["num_tickets"] <= freed_seats:
            # Offer seats
            conn.execute("""
                UPDATE waitlist
                SET status = 'offered', offered_at = ?
                WHERE waitlist_id = ?
            """, (now.isoformat(), w["waitlist_id"]))
            conn.commit()

            print(
                f"WAITLIST OFFER: {w['customer_name']} offered {w['num_tickets']} "
                f"seat(s) for {film_title} at {show_time}"
            )

            freed_seats -= w["num_tickets"]
            if freed_seats <= 0:
                break
