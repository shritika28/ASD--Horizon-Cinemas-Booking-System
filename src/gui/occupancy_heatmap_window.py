"""
src/gui/occupancy_heatmap_window.py
===================================
Occupancy Heatmap panel for the Horizon Cinemas Booking System.
"""

from src.database.db_connection import get_connection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import numpy as np

import matplotlib
matplotlib.use("TkAgg")


# Style constants
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#162338"
ACCENT = "#4f8cff"
FG = "#f8fafc"
FG2 = "#a7b4c8"
BORDER = "#26344a"

FF = "Segoe UI"
FONT_H2 = (FF, 13, "bold")
FONT_BODY = (FF, 10)
FONT_BTN = (FF, 10, "bold")


class OccupancyHeatmapPanel:
    def __init__(self, parent):
        self.parent = parent
        self._cinemas = []  # [(id, name)]
        self._screens = {}  # cinema_id -> [(id, screen_number)]

        self._x_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self._y_labels = ["morning", "afternoon", "evening"]

        # We'll store the cell details mapping: (y_idx, x_idx) -> list of showing dicts
        self._cell_data = {}

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        ctrl = tk.Frame(self.parent, bg=BG2, pady=10, padx=16)
        ctrl.pack(fill="x")

        # Cinema Filter
        tk.Label(ctrl, text="Cinema:", bg=BG2, fg=FG2, font=FONT_BODY).pack(side="left", padx=(0, 4))
        self._cinema_var = tk.StringVar()
        self._cinema_cb = ttk.Combobox(ctrl, textvariable=self._cinema_var, state="readonly", font=FONT_BODY, width=20)
        self._cinema_cb.pack(side="left", padx=(0, 16))
        self._cinema_cb.bind("<<ComboboxSelected>>", self._on_cinema_change)

        # Screen Filter
        tk.Label(ctrl, text="Screen:", bg=BG2, fg=FG2, font=FONT_BODY).pack(side="left", padx=(0, 4))
        self._screen_var = tk.StringVar(value="All Screens")
        self._screen_cb = ttk.Combobox(ctrl, textvariable=self._screen_var, state="readonly", font=FONT_BODY, width=12)
        self._screen_cb.pack(side="left", padx=(0, 16))

        # Date Range Filter
        tk.Label(ctrl, text="Date Range:", bg=BG2, fg=FG2, font=FONT_BODY).pack(side="left", padx=(0, 4))
        self._range_var = tk.StringVar(value="Last Month")
        self._range_cb = ttk.Combobox(ctrl, textvariable=self._range_var,
                                      values=["Last Week", "Last Month", "All Time"],
                                      state="readonly", font=FONT_BODY, width=12)
        self._range_cb.pack(side="left", padx=(0, 16))

        tk.Button(ctrl, text="▶ Generate Heatmap", bg=ACCENT, fg=FG, font=FONT_BTN,
                  relief="flat", cursor="hand2", padx=12, pady=4,
                  command=self._generate).pack(side="left", padx=8)

        # Main PanedWindow (Heatmap Left, Details Right)
        self.pane = tk.PanedWindow(self.parent, orient="horizontal", bg=BG, sashwidth=6, sashrelief="flat")
        self.pane.pack(fill="both", expand=True, padx=10, pady=8)

        # Heatmap Frame
        self.heat_frame = tk.Frame(self.pane, bg=BG)
        self.pane.add(self.heat_frame, minsize=500, stretch="always")

        # Details Frame
        self.det_frame = tk.Frame(self.pane, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self.pane.add(self.det_frame, minsize=250)

        # Setup Matplotlib Figure
        self._fig = Figure(figsize=(6, 4), dpi=144, facecolor=BG)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(BG2)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self.heat_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvas.mpl_connect("button_press_event", self._on_click_heatmap)

        self._build_details_ui()
        self._draw_empty_heatmap()

    def _build_details_ui(self):
        tk.Label(self.det_frame, text="Showing Details", font=FONT_H2,
                 bg=BG_CARD, fg=FG).pack(pady=(12, 4), padx=10, anchor="w")
        self.det_lbl = tk.Label(self.det_frame, text="Click a cell to view details.",
                                font=FONT_BODY, bg=BG_CARD, fg=FG2, justify="left", wraplength=230)
        self.det_lbl.pack(pady=4, padx=10, anchor="w")

        # Treeview for showings
        cols = ("date", "film", "occ", "rev", "risk")
        self.det_tv = ttk.Treeview(self.det_frame, columns=cols, show="headings", height=15)
        self.det_tv.heading("date", text="Date")
        self.det_tv.heading("film", text="Film")
        self.det_tv.heading("occ", text="Occ%")
        self.det_tv.heading("rev", text="Rev(£)")
        self.det_tv.heading("risk", text="Risk")

        self.det_tv.column("date", width=75, anchor="center")
        self.det_tv.column("film", width=100, anchor="w")
        self.det_tv.column("occ", width=50, anchor="center")
        self.det_tv.column("rev", width=60, anchor="e")
        self.det_tv.column("risk", width=80, anchor="center")

        self.det_tv.tag_configure("low_risk", foreground="#22c55e")
        self.det_tv.tag_configure("med_risk", foreground="#f59e0b")
        self.det_tv.tag_configure("high_risk", foreground="#ef4444")

        sb = ttk.Scrollbar(self.det_frame, orient="vertical", command=self.det_tv.yview)
        self.det_tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.det_tv.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _load_data(self):
        try:
            conn = get_connection()
            cinemas = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name").fetchall()
            self._cinemas = [(c["cinema_id"], c["cinema_name"]) for c in cinemas]

            screens = conn.execute(
                "SELECT screen_id, cinema_id, screen_number FROM screens ORDER BY cinema_id, screen_number").fetchall()
            for s in screens:
                self._screens.setdefault(s["cinema_id"], []).append((s["screen_id"], f"Screen {s['screen_number']}"))

            opts = ["All Cinemas"] + [name for _, name in self._cinemas]
            self._cinema_cb["values"] = opts
            if opts:
                self._cinema_cb.current(0)
                self._on_cinema_change()
        except Exception as e:
            print(f"Error loading filters: {e}")

    def _on_cinema_change(self, event=None):
        cinema_name = self._cinema_var.get()
        if cinema_name == "All Cinemas":
            self._screen_cb["values"] = ["All Screens"]
        else:
            cid = next((cid for cid, name in self._cinemas if name == cinema_name), None)
            if cid:
                s_opts = ["All Screens"] + [name for _, name in self._screens.get(cid, [])]
                self._screen_cb["values"] = s_opts
        self._screen_cb.current(0)

    def _get_dates(self):
        today = datetime.date.today()
        range_val = self._range_var.get()
        if range_val == "Last Week":
            since = today - datetime.timedelta(days=7)
        elif range_val == "Last Month":
            since = today - datetime.timedelta(days=30)
        else:
            since = datetime.date(2000, 1, 1)
        return since.isoformat(), today.isoformat()

    def _generate(self):
        since, until = self._get_dates()

        cinema_name = self._cinema_var.get()
        screen_val = self._screen_var.get()

        cid = next((cid for cid, name in self._cinemas if name == cinema_name),
                   None) if cinema_name != "All Cinemas" else None
        sid = None
        if cid and screen_val != "All Screens":
            sid = next((sid for sid, name in self._screens.get(cid, []) if name == screen_val), None)

        try:
            conn = get_connection()

            params = [since, until]
            query = """
                SELECT
                    sh.show_date, sh.show_type, sh.seats_remaining, sh.show_time,
                    sc.total_capacity, f.title as film_title, sc.cinema_id,
                    IFNULL(SUM(b.total_cost), 0) as total_revenue
                FROM showings sh
                JOIN screens sc ON sh.screen_id = sc.screen_id
                JOIN films f ON sh.film_id = f.film_id
                LEFT JOIN bookings b ON sh.showing_id = b.showing_id AND b.booking_status != 'Cancelled'
                WHERE sh.show_date BETWEEN ? AND ?
            """
            if cid:
                query += " AND sc.cinema_id = ?"
                params.append(cid)
            if sid:
                query += " AND sh.screen_id = ?"
                params.append(sid)

            query += " GROUP BY sh.showing_id"

            rows = conn.execute(query, params).fetchall()

            # Initialize aggregated data structures
            self._cell_data = {(y, x): [] for y in range(3) for x in range(7)}

            agg_occ = {(y, x): [] for y in range(3) for x in range(7)}

            for r in rows:
                dt = datetime.date.fromisoformat(r["show_date"])
                weekday = dt.weekday()  # 0 = Mon, 6 = Sun

                stype = r["show_type"]
                try:
                    y_idx = self._y_labels.index(stype)
                except ValueError:
                    continue  # Ignore invalid show types

                cap = r["total_capacity"]
                avail = r["seats_remaining"]
                occ_pct = ((cap - avail) / cap * 100) if cap > 0 else 0

                from src.utils.noshow_predictor import predict_noshow
                try:
                    hour = int(r["show_time"].split(":")[0])
                except BaseException:
                    hour = 12

                prob = predict_noshow({
                    "booking_lead_days": 2,
                    "show_time_hour": hour,
                    "day_of_week": weekday,
                    "ticket_type": 0,
                    "num_tickets": 2,
                    "cinema_city": r["cinema_id"],
                    "month": dt.month
                })

                det = {
                    "date": dt.strftime("%Y-%m-%d"),
                    "film": r["film_title"],
                    "occ": occ_pct,
                    "rev": r["total_revenue"],
                    "risk": prob
                }
                self._cell_data[(y_idx, weekday)].append(det)
                agg_occ[(y_idx, weekday)].append(occ_pct)

            # Build 2D matrix
            matrix = np.full((3, 7), np.nan)
            for y in range(3):
                for x in range(7):
                    if agg_occ[(y, x)]:
                        matrix[y, x] = np.mean(agg_occ[(y, x)])

            self._draw_heatmap(matrix)

        except Exception as e:
            messagebox.showerror("Query Error", str(e))

    def _draw_empty_heatmap(self):
        self._ax.clear()
        self._ax.set_facecolor(BG2)
        self._fig.set_facecolor(BG)
        self._ax.text(0.5, 0.5, "Select filters and click Generate",
                      ha="center", va="center", color=FG2, fontsize=10, transform=self._ax.transAxes)
        for sp in self._ax.spines.values():
            sp.set_color(BORDER)
        self._canvas.draw()

    def _draw_heatmap(self, matrix):
        self._ax.clear()
        self._ax.set_facecolor(BG2)
        self._fig.set_facecolor(BG)

        # Create custom colormap: Red (<50), Amber (50-80), Green (>80)
        # We will map 0 to 100
        colors = ["#dc2626", "#dc2626", "#fbbf24", "#fbbf24", "#16a34a", "#16a34a"]
        # Thresholds: 0-50 red, 50-80 amber, 80-100 green
        # Positions in 0..1 scale
        # 0.0 to 0.5 -> red
        # 0.5 to 0.8 -> amber
        # 0.8 to 1.0 -> green
        nodes = [0.0, 0.499, 0.5, 0.799, 0.8, 1.0]
        cmap = LinearSegmentedColormap.from_list("occ_cmap", list(zip(nodes, colors)))

        # Mask NaNs (empty slots)
        masked_matrix = np.ma.masked_invalid(matrix)
        cmap.set_bad(color=BG2)

        cax = self._ax.imshow(masked_matrix, cmap=cmap, vmin=0, vmax=100, aspect='auto')

        # Formatting
        self._ax.set_xticks(np.arange(len(self._x_labels)))
        self._ax.set_yticks(np.arange(len(self._y_labels)))
        self._ax.set_xticklabels(self._x_labels, color=FG2)
        self._ax.set_yticklabels([label.capitalize() for label in self._y_labels], color=FG2)

        for sp in self._ax.spines.values():
            sp.set_color(BORDER)
        self._ax.tick_params(color=BORDER)

        # Annotate cells
        for y in range(3):
            for x in range(7):
                val = matrix[y, x]
                if not np.isnan(val):
                    text_color = "white" if val < 50 or val >= 80 else "black"
                    self._ax.text(x, y, f"{val:.0f}%", ha="center", va="center",
                                  color=text_color, fontsize=10, fontweight="bold")

        # Add colorbar if not already added
        if not hasattr(self, '_cbar') or self._cbar is None:
            self._cbar = self._fig.colorbar(cax, ax=self._ax, fraction=0.046, pad=0.04)
            self._cbar.ax.yaxis.set_tick_params(color=FG2, labelcolor=FG2)
            self._cbar.outline.set_edgecolor(BORDER)
            self._cbar.set_label("Occupancy (%)", color=FG2)
        else:
            self._cbar.update_normal(cax)

        self._ax.set_title("Average Occupancy by Timeslot & Day", color=FG, pad=12)
        self._fig.tight_layout()
        self._canvas.draw()

        # Clear details
        self.det_lbl.config(text="Click a cell to view details.")
        for item in self.det_tv.get_children():
            self.det_tv.delete(item)

    def _on_click_heatmap(self, event):
        if event.inaxes != self._ax:
            return
        if event.xdata is None or event.ydata is None:
            return

        x_idx = int(round(event.xdata))
        y_idx = int(round(event.ydata))

        if x_idx < 0 or x_idx > 6 or y_idx < 0 or y_idx > 2:
            return

        showings = self._cell_data.get((y_idx, x_idx), [])
        day_str = self._x_labels[x_idx]
        slot_str = self._y_labels[y_idx].capitalize()

        self.det_lbl.config(text=f"{day_str} {slot_str}\n{len(showings)} showing(s) found.")

        for item in self.det_tv.get_children():
            self.det_tv.delete(item)

        # Sort showings by date
        showings.sort(key=lambda s: s["date"], reverse=True)

        for s in showings:
            prob = s.get("risk", 0)
            if prob < 0.3:
                risk_str = "Low"
                tag = "low_risk"
            elif prob <= 0.6:
                risk_str = "Medium"
                tag = "med_risk"
            else:
                risk_str = "High"
                tag = "high_risk"

            self.det_tv.insert("", "end", values=(
                s["date"],
                s["film"],
                f"{s['occ']:.0f}%",
                f"£{s['rev']:.2f}",
                risk_str
            ), tags=(tag,))
