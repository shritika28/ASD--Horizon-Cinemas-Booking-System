"""
src/models/booking.py
=====================
Booking model and management layer for HCBS.
"""

import sqlite3
import datetime
from datetime import date
from typing import Dict, Any, Optional, List

from src.models.showing import Showing


class BookingError(Exception):
    """Custom exception for booking validation errors."""


class BookingManager:
    """
    Manages bookings, generating references, and atomicity for ticket creation.
    """

    @staticmethod
    def validate_booking_date(show_date: date, show_time: Optional[str] = None) -> None:
        """
        Validates that the show_date (and optionally show_time) is in the future.
        """
        if isinstance(show_date, str):
            show_date = datetime.date.fromisoformat(show_date)
        elif isinstance(show_date, datetime.datetime):
            show_date = show_date.date()

        today = datetime.date.today()
        difference = (show_date - today).days

        if difference < 0:
            raise BookingError('Cannot book for a past showing')

        if difference == 0 and show_time:
            # If it's today, check the time
            try:
                now_time = datetime.datetime.now().time()
                # Parse show_time (HH:MM)
                h, m = map(int, show_time.split(':'))
                show_t = datetime.time(h, m)

                if now_time >= show_t:
                    raise BookingError('This showing has already started or passed')
            except ValueError:
                pass  # If time format is weird, fallback to date-only check

        if difference > 7:
            raise BookingError('Advance booking limit is 7 days')
        return None

    @staticmethod
    def generate_booking_ref(db_connection: sqlite3.Connection) -> str:
        """
        Queries the bookings table to find today's highest sequence number,
        increments it, and returns a new ref in format HCBS-YYYYMMDD-XXXX.

        Args:
            db_connection: Active database connection.

        Returns:
            str: Generated booking reference.
        """
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        prefix = f"HCBS-{today_str}"

        cursor = db_connection.execute(
            """
            SELECT booking_ref
            FROM bookings
            WHERE booking_ref LIKE ?
            ORDER BY booking_id DESC
            LIMIT 1
            """,
            (f"{prefix}-%",)
        )
        row = cursor.fetchone()

        if row:
            # e.g., 'HCBS-20250501-0004' -> last part is '0004'
            last_seq = int(row["booking_ref"].split("-")[-1])
            seq = last_seq + 1
        else:
            seq = 1

        return f"{prefix}-{seq:04d}"

    @staticmethod
    def check_duplicate(customer_email: str, film_id: int, show_date: datetime.date,
                        db_connection) -> Optional[Dict[str, Any]]:
        """
        Check if the customer already has a confirmed booking for the same film on the same date.
        """
        if not customer_email:
            return None

        cursor = db_connection.execute(
            """
            SELECT b.booking_ref, s.show_time, b.booking_id
            FROM bookings b
            JOIN showings s ON b.showing_id = s.showing_id
            WHERE b.customer_email = ?
              AND s.film_id = ?
              AND s.show_date = ?
              AND b.booking_status = 'Active'
            LIMIT 1
            """,
            (customer_email, film_id, str(show_date))
        )
        row = cursor.fetchone()
        if row:
            b_id = row["booking_id"]
            # get seat numbers separately to avoid group_concat issues across sqlite versions if needed,
            # or just do group concat. Let's do a fast second query.
            seat_cursor = db_connection.execute("SELECT seat_number FROM tickets WHERE booking_id = ?", (b_id,))
            seats = [r["seat_number"] for r in seat_cursor.fetchall()]

            return {
                "booking_ref": row["booking_ref"],
                "show_time": row["show_time"],
                "seat_numbers": ", ".join(seats)
            }
        return None

    @staticmethod
    def create_booking(showing_id: int, staff_user_id: int, ticket_type: str,
                       quantity: int, customer_name: str, customer_email: str,
                       customer_phone: str, unit_price: float,
                       db_connection: sqlite3.Connection,
                       booked_by_agent: bool = False,
                       selected_seats: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Creates a booking and its tickets atomically.

        Args:
            showing_id: FK to showing.
            staff_user_id: ID of the staff creating the booking.
            ticket_type: 'lower_hall', 'upper_gallery', or 'vip'.
            quantity: Number of tickets.
            customer_name: Customer's name.
            customer_email: Customer's email.
            customer_phone: Customer's phone.
            unit_price: Unit price for the ticket.
            db_connection: Active database connection.
            booked_by_agent: True if booked by LLM agent, False otherwise.

        Returns:
            dict: Summary of the created booking.
        """
        showing = Showing.get_by_id(showing_id)
        if not showing:
            raise ValueError(f"Showing {showing_id} not found")

        if quantity <= 0:
            raise ValueError("Ticket quantity must be at least 1")

        BookingManager.validate_booking_date(showing.show_date, showing.show_time)

        # Fetch user role and home cinema
        cursor = db_connection.execute("SELECT role, cinema_id FROM users WHERE user_id = ?", (staff_user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise ValueError("Invalid staff_user_id")

        is_admin = user_row["role"] in ("admin", "manager")
        user_cinema_id = user_row["cinema_id"]

        # Permission check
        if showing.cinema_id != user_cinema_id and not is_admin:
            raise PermissionError("Staff can only book at their home cinema")

        if not showing.is_available(showing_id, quantity):
            raise ValueError(f"Showing {showing_id} does not have {quantity} seats available.")

        try:
            db_connection.execute('BEGIN')

            booking_ref = BookingManager.generate_booking_ref(db_connection)
            total_cost = unit_price * quantity

            # 1. Insert into bookings
            now_iso = datetime.datetime.now().isoformat()
            cursor = db_connection.execute(
                """
                INSERT INTO bookings (
                    showing_id, booking_ref, customer_name, customer_email,
                    total_cost, booking_status, booked_by_agent, staff_id, booking_time
                )
                VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?)
                """,
                (showing_id, booking_ref, customer_name, customer_email,
                 total_cost, booked_by_agent, staff_user_id, now_iso)
            )
            booking_id = cursor.lastrowid

            # 2. Find existing tickets count to auto-assign sequential seat numbers
            cursor = db_connection.execute(
                """
                SELECT COUNT(*) as c
                FROM tickets t
                JOIN bookings b ON t.booking_id = b.booking_id
                WHERE b.showing_id = ? AND t.ticket_type = ?
                """,
                (showing_id, ticket_type)
            )
            existing_count = cursor.fetchone()["c"]

            # Use provided seats or auto-assign seat letters
            if selected_seats and len(selected_seats) == quantity:
                seat_numbers = selected_seats
            else:
                if ticket_type == "lower_hall":
                    prefix = "A"
                elif ticket_type == "upper_gallery":
                    prefix = "B"
                elif ticket_type == "vip":
                    prefix = "V"
                else:
                    prefix = "T"

                seat_numbers = []
                for i in range(quantity):
                    seat_num = f"{prefix}{existing_count + i + 1}"
                    seat_numbers.append(seat_num)

            for seat_num in seat_numbers:
                # 3. Insert into tickets
                db_connection.execute(
                    """
                    INSERT INTO tickets (booking_id, seat_number, ticket_type, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (booking_id, seat_num, ticket_type, unit_price)
                )

            # 4. Decrement seats
            Showing.decrement_seats(showing_id, quantity)

            db_connection.commit()

            showing = Showing.get_by_id(showing_id)

            return {
                "booking_ref": booking_ref,
                "customer_name": customer_name,
                "total_cost": total_cost,
                "seat_numbers": seat_numbers,
                "showing": showing
            }

        except Exception as e:
            db_connection.rollback()
            raise e

    @staticmethod
    def get_by_ref(booking_ref: str, db_connection: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        """
        Retrieves a full booking and its tickets by reference.

        Args:
            booking_ref: The string reference (e.g., HCBS-YYYYMMDD-XXXX).
            db_connection: Active database connection.

        Returns:
            dict: Full booking and ticket details, or None if not found.
        """
        cursor = db_connection.execute(
            "SELECT * FROM bookings WHERE booking_ref = ?",
            (booking_ref,)
        )
        b_row = cursor.fetchone()

        if not b_row:
            return None

        cursor = db_connection.execute(
            "SELECT * FROM tickets WHERE booking_id = ?",
            (b_row["booking_id"],)
        )
        t_rows = cursor.fetchall()

        return {
            "booking_id": b_row["booking_id"],
            "showing_id": b_row["showing_id"],
            "booking_ref": b_row["booking_ref"],
            "customer_name": b_row["customer_name"],
            "total_cost": b_row["total_cost"],
            "booking_status": b_row["booking_status"],
            "booked_by_agent": bool(b_row["booked_by_agent"]),
            "tickets": [dict(t) for t in t_rows]
        }
