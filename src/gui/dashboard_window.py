"""
src/gui/dashboard_window.py
===========================
Student ID: 1234567 | Name: Alex Smith

Live Dashboard module for the Horizon Cinemas Booking System.
Accessible by Managers and Admins.
Auto-refreshes every 60 seconds.
"""

from src.gui.login_window import SessionManager
from src.utils.rbac import require_role
from src.database.db_connection import get_connection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk
import datetime
import threading

import matplotlib
matplotlib.use("TkAgg")


# Style Constants
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#162338"
ACCENT = "#4f8cff"
TEXT = "#f8fafc"
TEXT2 = "#a7b4c8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"
BORDER = "#26344a"

FONT_H1 = ("Segoe UI", 20, "bold")
FONT_H2 = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 11)
FONT_BTN = ("Segoe UI", 10, "bold")
FONT_METRIC = ("Segoe UI", 28, "bold")


@require_role('admin')
class DashboardWindow:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        self.root.title("HCBS — Live Dashboard")
        self.root.geometry("1200x800")
        self.root.configure(bg=BG)

        self.chart_mode = "today"  # 'today' or 'week'
        self.auto_refresh_job = None
        self.cinemas_map = {}  # name -> id

        self._build_ui()
        self._load_cinemas()
        self.refresh_dashboard()

    def _build_ui(self):
        # 1. Top Bar
        top_frame = tk.Frame(self.root, bg=BG2, pady=15, padx=20)
        top_frame.pack(fill="x")

        tk.Label(top_frame, text="📊 Live Dashboard", font=FONT_H1, bg=BG2, fg=TEXT).pack(side="left")

        tk.Button(top_frame, text="Refresh Data", font=FONT_BTN, bg=ACCENT, fg=TEXT, relief="flat",
                  cursor="hand2", padx=15, pady=6, command=self.refresh_dashboard).pack(side="right", padx=10)

        self.cinema_var = tk.StringVar()
        self.cinema_cb = ttk.Combobox(top_frame, textvariable=self.cinema_var,
                                      state="readonly", font=FONT_BODY, width=25)
        self.cinema_cb.pack(side="right", padx=10)
        self.cinema_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_dashboard())
        tk.Label(top_frame, text="Filter by Cinema:", font=FONT_BODY, bg=BG2, fg=TEXT2).pack(side="right")

        # 2. Metric Cards Row
        self.metrics_frame = tk.Frame(self.root, bg=BG, pady=20, padx=20)
        self.metrics_frame.pack(fill="x")

        self.card_bookings = self._create_metric_card("Today's Bookings", "0")
        self.card_revenue = self._create_metric_card("Today's Revenue", "£0.00")
        self.card_occupancy = self._create_metric_card("Overall Occupancy", "0%")
        self.card_shows = self._create_metric_card("Shows Running", "0")

        # 3. Main Content (Chart + Table)
        content_frame = tk.Frame(self.root, bg=BG, padx=20)
        content_frame.pack(fill="both", expand=True)

        # Left: Chart
        chart_frame = tk.Frame(content_frame, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        chart_top = tk.Frame(chart_frame, bg=BG_CARD)
        chart_top.pack(fill="x", padx=15, pady=10)
        tk.Label(chart_top, text="Top 5 Films by Revenue", font=FONT_H2, bg=BG_CARD, fg=TEXT).pack(side="left")

        self.btn_toggle_chart = tk.Button(chart_top, text="View: Today", font=FONT_BTN,
                                          bg=BG2, fg=TEXT, relief="flat", cursor="hand2",
                                          command=self._toggle_chart_mode)
        self.btn_toggle_chart.pack(side="right")

        self.figure = Figure(figsize=(5, 4), dpi=144, facecolor=BG_CARD)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(BG_CARD)
        self.ax.tick_params(colors=TEXT2)
        for spine in self.ax.spines.values():
            spine.set_color(BORDER)

        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Right: Table
        table_frame = tk.Frame(content_frame, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        table_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        tk.Label(table_frame, text="Today's Occupancy", font=FONT_H2,
                 bg=BG_CARD, fg=TEXT).pack(anchor="w", padx=15, pady=10)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dash.Treeview", background=BG_CARD, foreground=TEXT,
                        fieldbackground=BG_CARD, borderwidth=0, font=FONT_BODY, rowheight=28)
        style.configure("Dash.Treeview.Heading", background=BG2, foreground=TEXT, font=FONT_BTN)
        style.map("Dash.Treeview", background=[("selected", ACCENT)], foreground=[("selected", TEXT)])
        style.configure("TCombobox", fieldbackground=BG2, background=BG2, foreground=TEXT, arrowcolor=TEXT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG2), ("disabled", BG2), ("focus", BG2), ("active", BG2)],
                  foreground=[("readonly", TEXT), ("disabled", TEXT), ("focus", TEXT), ("active", TEXT)])
        self.root.option_add('*TCombobox*Listbox.background', BG2, 100)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT, 100)
        self.root.option_add('*TCombobox*Listbox.selectBackground', ACCENT, 100)
        self.root.option_add('*TCombobox*Listbox.selectForeground', TEXT, 100)

        cols = ("cinema", "film", "time", "screen", "booked", "cap", "pct")
        self.tv = ttk.Treeview(table_frame, columns=cols, show="headings", style="Dash.Treeview")
        self.tv.heading("cinema", text="Cinema")
        self.tv.heading("film", text="Film")
        self.tv.heading("time", text="Time")
        self.tv.heading("screen", text="Screen")
        self.tv.heading("booked", text="Booked")
        self.tv.heading("cap", text="Cap")
        self.tv.heading("pct", text="Occ %")

        self.tv.column("cinema", width=100)
        self.tv.column("film", width=120)
        self.tv.column("time", width=60, anchor="center")
        self.tv.column("screen", width=60, anchor="center")
        self.tv.column("booked", width=60, anchor="center")
        self.tv.column("cap", width=60, anchor="center")
        self.tv.column("pct", width=60, anchor="center")

        # Tags for colours
        self.tv.tag_configure("high", foreground=SUCCESS)
        self.tv.tag_configure("med", foreground=WARNING)
        self.tv.tag_configure("low", foreground=ERROR)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=scroll.set)

        self.tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side="right", fill="y", pady=(0, 10))

        # Last updated
        self.status_lbl = tk.Label(self.root, text="Last updated: Never", font=FONT_BODY, bg=BG, fg=TEXT2)
        self.status_lbl.pack(side="bottom", anchor="e", padx=20, pady=10)

    def _create_metric_card(self, title, initial_val):
        frame = tk.Frame(self.metrics_frame, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(side="left", fill="both", expand=True, padx=10)

        tk.Label(frame, text=title, font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(pady=(15, 5))
        val_lbl = tk.Label(frame, text=initial_val, font=FONT_METRIC, bg=BG_CARD, fg=TEXT)
        val_lbl.pack(pady=(0, 15))
        return val_lbl

    def _load_cinemas(self):
        try:
            conn = get_connection()
            cur = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name")
            rows = cur.fetchall()
            self.cinemas_map = {r["cinema_name"]: r["cinema_id"] for r in rows}

            opts = ["All Cinemas"] + list(self.cinemas_map.keys())
            self.cinema_cb['values'] = opts
            self.cinema_cb.current(0)
        except Exception as e:
            print("Failed to load cinemas:", e)

    def _toggle_chart_mode(self):
        if self.chart_mode == "today":
            self.chart_mode = "week"
            self.btn_toggle_chart.config(text="View: This Week")
        else:
            self.chart_mode = "today"
            self.btn_toggle_chart.config(text="View: Today")
        self.refresh_dashboard()

    def refresh_dashboard(self):
        # Cancel pending refresh to avoid duplicates
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)

        # Run DB queries in background to avoid freezing UI
        threading.Thread(target=self._fetch_data_bg, daemon=True).start()

        # Schedule next refresh
        self.auto_refresh_job = self.root.after(60000, self.refresh_dashboard)

    def _fetch_data_bg(self):
        today_str = datetime.date.today().isoformat()
        week_ago_str = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        selected_cinema = self.cinema_var.get()
        cinema_id = self.cinemas_map.get(selected_cinema)

        data = {
            "bookings": 0,
            "revenue": 0.0,
            "occupancy": 0.0,
            "shows": 0,
            "chart_data": [],  # list of (title, revenue)
            "table_data": []  # list of dicts
        }

        try:
            conn = get_connection()

            # Base filters
            cinema_filter = " AND sc.cinema_id = ? " if cinema_id else ""
            params_today = [today_str, cinema_id] if cinema_id else [today_str]

            # 1. Total Bookings & Revenue
            query_metrics = f"""
                SELECT COUNT(b.booking_id) as b_count, IFNULL(SUM(b.total_cost), 0) as b_rev
                FROM bookings b
                JOIN showings sh ON b.showing_id = sh.showing_id
                JOIN screens sc ON sh.screen_id = sc.screen_id
                WHERE sh.show_date = ? AND b.booking_status != 'Cancelled' {cinema_filter}
            """
            cur = conn.execute(query_metrics, params_today)
            row = cur.fetchone()
            if row:
                data["bookings"] = row["b_count"]
                data["revenue"] = row["b_rev"]

            # 2. Occupancy & Shows
            query_shows = f"""
                SELECT COUNT(sh.showing_id) as s_count,
                       IFNULL(SUM(sc.total_capacity - sh.seats_remaining), 0) as booked,
                       IFNULL(SUM(sc.total_capacity), 0) as total
                FROM showings sh
                JOIN screens sc ON sh.screen_id = sc.screen_id
                WHERE sh.show_date = ? {cinema_filter}
            """
            cur = conn.execute(query_shows, params_today)
            row = cur.fetchone()
            if row:
                data["shows"] = row["s_count"]
                if row["total"] > 0:
                    data["occupancy"] = (row["booked"] / row["total"]) * 100

            # 3. Chart Data
            if self.chart_mode == "today":
                c_params = params_today
                date_filter = "sh.show_date = ?"
            else:
                c_params = [week_ago_str, today_str, cinema_id] if cinema_id else [week_ago_str, today_str]
                date_filter = "sh.show_date >= ? AND sh.show_date <= ?"

            query_chart = f"""
                SELECT f.title, SUM(b.total_cost) as rev
                FROM bookings b
                JOIN showings sh ON b.showing_id = sh.showing_id
                JOIN screens sc ON sh.screen_id = sc.screen_id
                JOIN films f ON sh.film_id = f.film_id
                WHERE {date_filter} AND b.booking_status != 'Cancelled' {cinema_filter}
                GROUP BY f.film_id
                ORDER BY rev DESC
                LIMIT 5
            """
            cur = conn.execute(query_chart, c_params)
            for r in cur.fetchall():
                data["chart_data"].append((r["title"], r["rev"]))

            # 4. Table Data
            query_table = f"""
                SELECT c.cinema_name, f.title, sh.show_time, sc.screen_number,
                       (sc.total_capacity - sh.seats_remaining) as booked,
                       sc.total_capacity as capacity
                FROM showings sh
                JOIN screens sc ON sh.screen_id = sc.screen_id
                JOIN cinemas c ON sc.cinema_id = c.cinema_id
                JOIN films f ON sh.film_id = f.film_id
                WHERE sh.show_date = ? {cinema_filter}
                ORDER BY sh.show_time
            """
            cur = conn.execute(query_table, params_today)
            for r in cur.fetchall():
                pct = (r["booked"] / r["capacity"] * 100) if r["capacity"] > 0 else 0
                data["table_data"].append({
                    "cinema": r["cinema_name"],
                    "film": r["title"],
                    "time": r["show_time"],
                    "screen": r["screen_number"],
                    "booked": r["booked"],
                    "cap": r["capacity"],
                    "pct": pct
                })

        except Exception as e:
            print("Dashboard fetch error:", e)

        # Update UI safely
        self.root.after(0, self._update_ui_with_data, data)

    def _update_ui_with_data(self, data):
        # Update metrics
        self.card_bookings.config(text=str(data["bookings"]))
        self.card_revenue.config(text=f"£{data['revenue']:.2f}")
        self.card_occupancy.config(text=f"{data['occupancy']:.1f}%")
        self.card_shows.config(text=str(data["shows"]))

        # Update chart
        self.ax.clear()
        self.ax.set_facecolor(BG_CARD)

        if data["chart_data"]:
            titles = [d[0][:15] + "..." if len(d[0]) > 15 else d[0] for d in data["chart_data"]]
            revs = [d[1] for d in data["chart_data"]]
            bars = self.ax.bar(titles, revs, color=ACCENT)

            # Add value labels
            for bar in bars:
                yval = bar.get_height()
                self.ax.text(bar.get_x() + bar.get_width() / 2, yval,
                             f"£{yval:.0f}", ha='center', va='bottom', color=TEXT, fontsize=8)

            self.ax.set_ylabel("Revenue (£)", color=TEXT2)
            self.ax.tick_params(axis='x', colors=TEXT2, rotation=25)
            self.ax.tick_params(axis='y', colors=TEXT2)
        else:
            self.ax.text(0.5, 0.5, "No revenue data found.", ha='center',
                         va='center', color=TEXT2, transform=self.ax.transAxes)
            self.ax.set_xticks([])
            self.ax.set_yticks([])

        self.figure.tight_layout()
        self.canvas.draw()

        # Update table
        for item in self.tv.get_children():
            self.tv.delete(item)

        for row in data["table_data"]:
            pct = row["pct"]
            tag = "med"
            if pct > 80:
                tag = "high"
            elif pct < 50:
                tag = "low"

            self.tv.insert("", "end", values=(
                row["cinema"],
                row["film"],
                row["time"],
                row["screen"],
                row["booked"],
                row["cap"],
                f"{pct:.1f}%"
            ), tags=(tag,))

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_lbl.config(text=f"Last updated: {now_str}")


if __name__ == "__main__":
    from src.models.user import User
    r = tk.Tk()
    r.withdraw()
    sess = SessionManager.get_instance()
    sess.set_current_user(User(1, 1, "admin_mock", "", "Admin", "", "admin"))
    mw = DashboardWindow(tk.Toplevel(r))
    r.mainloop()
