import csv
import os


class ReportManager:
    @staticmethod
    def bookings_per_listing(cinema_id: int, db_connection) -> list[dict]:
        """
        Returns rows with columns: film_title, show_date, show_time, total_bookings, total_revenue,
        by joining bookings, showings, and films tables, filtered by cinema_id, ordered by show_date DESC.
        """
        query = """
            SELECT
                f.title as film_title,
                s.show_date,
                s.show_time,
                COUNT(b.booking_id) as total_bookings,
                SUM(b.total_cost) as total_revenue
            FROM showings s
            JOIN films f ON s.film_id = f.film_id
            JOIN screens sc ON s.screen_id = sc.screen_id
            LEFT JOIN bookings b ON s.showing_id = b.showing_id AND b.booking_status = 'Active'
            WHERE sc.cinema_id = ?
            GROUP BY s.showing_id
            ORDER BY s.show_date DESC, s.show_time DESC
        """
        cursor = db_connection.execute(query, (cinema_id,))
        results = []
        for row in cursor.fetchall():
            results.append({
                "film_title": row["film_title"],
                "show_date": row["show_date"],
                "show_time": row["show_time"],
                "total_bookings": row["total_bookings"] or 0,
                "total_revenue": row["total_revenue"] or 0.0
            })
        return results

    @staticmethod
    def monthly_revenue(cinema_id: int, year: int, month: int, db_connection) -> dict:
        """
        Returns monthly booking, revenue, show-type, and occupancy metrics.
        """
        # Format year and month for LIKE comparison
        month_str = f"{year}-{month:02d}"

        query_bookings = """
            SELECT
                COUNT(b.booking_id) as t_bookings,
                SUM(b.total_cost) as t_revenue,
                s.show_type,
                SUM(b.total_cost) as type_revenue
            FROM bookings b
            JOIN showings s ON b.showing_id = s.showing_id
            JOIN screens sc ON s.screen_id = sc.screen_id
            WHERE sc.cinema_id = ? AND b.booking_status = 'Active'
              AND s.show_date LIKE ?
            GROUP BY s.show_type
        """
        cursor = db_connection.execute(query_bookings, (cinema_id, f"{month_str}%"))
        rows = cursor.fetchall()

        total_bookings = sum(r["t_bookings"] for r in rows) if rows else 0
        total_revenue = sum(r["type_revenue"] for r in rows) if rows else 0.0

        revenue_by_show_type = {
            "morning": 0.0,
            "afternoon": 0.0,
            "evening": 0.0
        }
        for r in rows:
            revenue_by_show_type[r["show_type"]] = r["type_revenue"]

        # Calculate average occupancy
        query_occupancy = """
            SELECT
                SUM(sc.total_capacity) as total_seats,
                SUM(sc.total_capacity - s.seats_remaining) as occupied_seats
            FROM showings s
            JOIN screens sc ON s.screen_id = sc.screen_id
            WHERE sc.cinema_id = ? AND s.show_date LIKE ?
        """
        occ_row = db_connection.execute(query_occupancy, (cinema_id, f"{month_str}%")).fetchone()

        average_occupancy_percent = 0.0
        if occ_row and occ_row["total_seats"] and occ_row["total_seats"] > 0:
            occ_seats = occ_row["occupied_seats"] or 0
            average_occupancy_percent = (occ_seats / occ_row["total_seats"]) * 100.0

        return {
            "total_bookings": total_bookings,
            "total_revenue": total_revenue,
            "revenue_by_show_type": revenue_by_show_type,
            "average_occupancy_percent": average_occupancy_percent
        }

    @staticmethod
    def top_revenue_films(cinema_id: int, limit: int = 10, db_connection=None) -> list[dict]:
        """
        Returns rows with: film_title, total_bookings, total_revenue, ordered by total_revenue DESC.
        """
        query = """
            SELECT
                f.title as film_title,
                COUNT(b.booking_id) as total_bookings,
                SUM(b.total_cost) as total_revenue
            FROM bookings b
            JOIN showings s ON b.showing_id = s.showing_id
            JOIN screens sc ON s.screen_id = sc.screen_id
            JOIN films f ON s.film_id = f.film_id
            WHERE sc.cinema_id = ? AND b.booking_status = 'Active'
            GROUP BY f.film_id
            ORDER BY total_revenue DESC
            LIMIT ?
        """
        cursor = db_connection.execute(query, (cinema_id, limit))
        results = []
        for row in cursor.fetchall():
            results.append({
                "film_title": row["film_title"],
                "total_bookings": row["total_bookings"] or 0,
                "total_revenue": row["total_revenue"] or 0.0
            })
        return results

    @staticmethod
    def staff_booking_leaderboard(cinema_id: int, year: int, month: int, db_connection) -> list[dict]:
        """
        Returns rows with: staff_full_name, total_bookings, total_revenue, rank, ordered by total_bookings DESC.
        """
        month_str = f"{year}-{month:02d}"
        query = """
            SELECT
                u.full_name as staff_full_name,
                COUNT(b.booking_id) as total_bookings,
                IFNULL(SUM(b.total_cost), 0) as total_revenue
            FROM users u
            LEFT JOIN bookings b ON u.user_id = b.staff_id AND b.booking_status = 'Active'
            LEFT JOIN showings s ON b.showing_id = s.showing_id AND s.show_date LIKE ?
            WHERE u.cinema_id = ? AND u.role = 'staff'
            GROUP BY u.user_id
            ORDER BY total_bookings DESC
        """
        cursor = db_connection.execute(query, (f"{month_str}%", cinema_id))
        results = []
        for rank, row in enumerate(cursor.fetchall(), start=1):
            results.append({
                "rank": rank,
                "staff_full_name": row["staff_full_name"],
                "total_bookings": row["total_bookings"] or 0,
                "total_revenue": row["total_revenue"] or 0.0
            })
        return results

    @staticmethod
    def export_to_csv(data: list[dict], filename: str) -> str:
        """
        Saves the data to a CSV file in the exports/ folder and returns the file path.
        """
        if not data:
            return ""

        export_dir = "exports"
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        filepath = os.path.join(export_dir, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as file:
            keys = list(data[0].keys())
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

        return os.path.abspath(filepath)
