"""
src/gui/staff_leaderboard_window.py
===================================
Staff Booking Leaderboard panel for the Admin Dashboard.
"""

from src.database.db_connection import get_connection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import calendar
import matplotlib
matplotlib.use("TkAgg")


# Style constants
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#162338"
ACCENT = "#4f8cff"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
FG = "#f8fafc"
FG2 = "#a7b4c8"
BORDER = "#26344a"

FF = "Segoe UI"
FONT_H2 = (FF, 13, "bold")
FONT_BODY = (FF, 10)
FONT_BTN = (FF, 10, "bold")


class StaffLeaderboardPanel:
    def __init__(self, parent):
        self.parent = parent
        self._data = []

        self._build_ui()
        self._generate()

    def _build_ui(self):
        # ── Controls row ──────────────────────────────────────────────────
        ctrl = tk.Frame(self.parent, bg=BG2, pady=10, padx=16)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Month:", bg=BG2, fg=FG2, font=FONT_BODY).pack(side="left", padx=(0, 4))
        month_names = ["All Months"] + [calendar.month_name[m] for m in range(1, 13)]
        self._month_var = tk.StringVar(value="All Months")
        self._month_cb = ttk.Combobox(ctrl, textvariable=self._month_var, values=month_names,
                                      state="readonly", font=FONT_BODY, width=12)
        self._month_cb.pack(side="left", padx=(0, 16))
        self._month_cb.bind("<<ComboboxSelected>>", lambda e: self._generate())

        tk.Label(ctrl, text="Year:", bg=BG2, fg=FG2, font=FONT_BODY).pack(side="left", padx=(0, 4))
        current_year = datetime.date.today().year
        years = ["All Years"] + [str(y) for y in range(current_year, current_year - 5, -1)]
        self._year_var = tk.StringVar(value="All Years")
        self._year_cb = ttk.Combobox(ctrl, textvariable=self._year_var, values=years,
                                     state="readonly", font=FONT_BODY, width=9)
        self._year_cb.pack(side="left", padx=(0, 16))
        self._year_cb.bind("<<ComboboxSelected>>", lambda e: self._generate())

        tk.Button(ctrl, text="↻ Refresh", bg=ACCENT, fg=FG, font=FONT_BTN, relief="flat",
                  cursor="hand2", padx=12, pady=4, command=self._generate).pack(side="left", padx=8)

        # ── Main Pane ─────────────────────────────────────────────────────
        self.pane = tk.PanedWindow(self.parent, orient="vertical", bg=BG, sashwidth=6, sashrelief="flat")
        self.pane.pack(fill="both", expand=True, padx=10, pady=8)

        # Table Frame (Top)
        self.table_frame = tk.Frame(self.pane, bg=BG)
        self.pane.add(self.table_frame, minsize=200, stretch="always")

        tk.Label(self.table_frame, text="Staff Booking Leaderboard",
                 font=FONT_H2, bg=BG, fg=FG).pack(anchor="w", pady=(4, 6))

        cols = ("rank", "name", "bookings", "cancels", "revenue", "avg")
        headings = {
            "rank": "Rank",
            "name": "Staff Name",
            "bookings": "Bookings Made",
            "cancels": "Cancellations Processed",
            "revenue": "Revenue Generated (£)",
            "avg": "Avg Ticket Value (£)"
        }
        widths = {
            "rank": 60, "name": 200, "bookings": 130,
            "cancels": 180, "revenue": 180, "avg": 180
        }

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Leader.Treeview", background=BG_CARD, foreground=FG,
                        fieldbackground=BG_CARD, borderwidth=0, font=FONT_BODY, rowheight=28)
        style.configure("Leader.Treeview.Heading", background=BG2, foreground=FG, font=FONT_BTN)
        style.map("Leader.Treeview", background=[("selected", ACCENT)], foreground=[("selected", FG)])

        self.tv = ttk.Treeview(self.table_frame, columns=cols, show="headings", style="Leader.Treeview")
        for c in cols:
            self.tv.heading(c, text=headings[c])
            self.tv.column(c, width=widths[c], anchor="center" if c != "name" else "w")

        # Tags for top rank
        self.tv.tag_configure("top_rank", background=WARNING, foreground="#000")

        sb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)

        # Chart Frame (Bottom)
        self.chart_frame = tk.Frame(self.pane, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self.pane.add(self.chart_frame, minsize=200, stretch="always")

        self.fig = Figure(figsize=(8, 3), dpi=144, facecolor=BG_CARD)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(BG_CARD)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    def _generate(self):
        month_s = self._month_var.get()
        year_s = self._year_var.get()

        month_num = None
        if month_s != "All Months":
            month_num = list(calendar.month_name).index(month_s)

        year_num = None
        if year_s != "All Years":
            year_num = int(year_s)

        try:
            conn = get_connection()
            params = []
            filters = []

            if month_num:
                filters.append("CAST(strftime('%m', b.booking_time) AS INTEGER) = ?")
                params.append(month_num)
            if year_num:
                filters.append("CAST(strftime('%Y', b.booking_time) AS INTEGER) = ?")
                params.append(year_num)

            join_filters = " AND " + " AND ".join(filters) if filters else ""

            query = f"""
                SELECT
                    u.full_name AS staff_name,
                    COUNT(b.booking_id) AS total_handled,
                    IFNULL(
                        SUM(CASE WHEN b.booking_status = 'Cancelled' THEN 1 ELSE 0 END),
                        0
                    ) AS cancellations_processed,
                    IFNULL(
                        SUM(CASE WHEN b.booking_status != 'Cancelled' THEN b.total_cost ELSE 0 END),
                        0
                    ) AS total_revenue
                FROM users u
                LEFT JOIN bookings b ON u.user_id = b.staff_id {join_filters}
                WHERE u.role = 'staff'
                GROUP BY u.user_id
                ORDER BY total_revenue DESC, total_handled DESC
            """
            rows = conn.execute(query, params).fetchall()

            self._data = []
            for i, r in enumerate(rows):
                bk = int(r["total_handled"])
                cn = int(r["cancellations_processed"])
                rev = float(r["total_revenue"])
                valid_bk = bk - cn
                avg = rev / valid_bk if valid_bk > 0 else 0.0

                self._data.append({
                    "rank": i + 1,
                    "name": r["staff_name"],
                    "bookings": bk,
                    "cancels": cn,
                    "revenue": rev,
                    "avg": avg
                })

            self._populate_table()
            self._draw_chart()

        except Exception as e:
            messagebox.showerror("Query Error", str(e))

    def _populate_table(self):
        for item in self.tv.get_children():
            self.tv.delete(item)

        for d in self._data:
            tag = "top_rank" if d["rank"] == 1 else ""
            self.tv.insert("", "end", values=(
                f"#{d['rank']}",
                d["name"],
                d["bookings"],
                d["cancels"],
                f"£{d['revenue']:,.2f}",
                f"£{d['avg']:,.2f}"
            ), tags=(tag,))

    def _draw_chart(self):
        self.ax.clear()
        self.ax.set_facecolor(BG_CARD)

        if not self._data:
            self.ax.text(0.5, 0.5, "No booking data found for the selected period.",
                         ha="center", va="center", color=FG2, fontsize=10, transform=self.ax.transAxes)
            self.canvas.draw()
            return

        # Prepare data for horizontal bar chart
        # Longest bar at top -> reverse list
        display_data = sorted(self._data, key=lambda x: x["rank"], reverse=True)

        names = [d["name"] for d in display_data]
        bookings = [d["bookings"] for d in display_data]

        bars = self.ax.barh(names, bookings, color=ACCENT, height=0.6)

        # Labels on bars
        for bar, val in zip(bars, bookings):
            self.ax.text(bar.get_width() + max(bookings) * 0.01, bar.get_y() + bar.get_height() / 2,
                         str(val), va="center", ha="left", color=FG, fontsize=9)

        # Formatting
        self.ax.set_xlabel("Total Bookings Handled", color=FG2, fontsize=9)
        self.ax.tick_params(axis="x", colors=FG2, labelsize=8)
        self.ax.tick_params(axis="y", colors=FG, labelsize=9)
        for sp in self.ax.spines.values():
            sp.set_color(BORDER)

        self.ax.set_title("Bookings by Staff Member", color=FG, fontsize=11, pad=10)
        self.fig.tight_layout()
        self.canvas.draw()
