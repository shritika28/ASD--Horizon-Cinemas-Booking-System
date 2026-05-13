"""
src/gui/manager_window.py
=========================
Student ID: 1234567 | Name: Alex Smith

Manager-specific GUI components for Horizon Cinemas Booking System.
"""

from src.utils.rbac import require_role
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime

from src.database.db_connection import get_connection
from src.gui.login_window import SessionManager
from src.gui.admin_window import AdminWindow

# Style Guide constants
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#111b2e"   # Card background
ACCENT = "#4f8cff"    # Primary blue
TEXT = "#f8fafc"      # White/Light text
TEXT2 = "#a7b4c8"     # Gray text
SUCCESS = "#22c55e"   # Emerald
ERROR = "#ef4444"     # Rose
WARNING = "#f59e0b"   # Amber
BORDER = "#26344a"    # Dark border

FONT_H1 = ("Segoe UI", 24, "bold")
FONT_H2 = ("Segoe UI", 16, "bold")
FONT_BODY = ("Segoe UI", 11)
FONT_BTN = ("Segoe UI", 11, "bold")


@require_role('manager')
class ManagerWindow:
    def __init__(self, root: tk.Toplevel):
        self.root = root
        self.root.title("Manager Dashboard - HCBS")
        self.root.geometry("1100x700")
        self.root.configure(bg=BG)

        session = SessionManager.get_instance()
        self.user = session.get_current_user()

        self._build_ui()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        # Load initial tab data (Add City) after a short delay
        self.root.after(100, self._refresh_city_list)

    def _create_btn(self, parent, text, bg, command, fg="#FFFFFF", **kwargs):
        """Helper to create a styled button with hover effects."""
        # Defaults
        btn_opts = {
            "relief": "flat",
            "font": ("Segoe UI Semibold", 10),
            "padx": 15,
            "pady": 8,
            "cursor": "hand2",
            "activebackground": bg,
            "activeforeground": fg
        }
        # Override with kwargs
        btn_opts.update(kwargs)

        btn = tk.Button(
            parent, text=text, bg=bg, fg=fg,
            command=command,
            **btn_opts
        )
        # Calculate hover color (slightly darker)
        try:
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            hover_bg = f"#{max(0, r - 20):02x}{max(0, g - 20):02x}{max(0, b - 20):02x}"
        except BaseException:
            hover_bg = bg
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _build_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg=BG2, padx=20, pady=15)
        header_frame.pack(fill="x")

        tk.Label(header_frame, text="👔 Manager Dashboard", font=(
            "Segoe UI Variable Display", 24, "bold"), bg=BG2, fg=ACCENT).pack(side="left")

        btn_frame = tk.Frame(header_frame, bg=BG2)
        btn_frame.pack(side="right")

        self._create_btn(btn_frame, "📊 Live Dashboard", "#0D9488", self._open_dashboard).pack(side="left", padx=10)
        self._create_btn(btn_frame, "Switch to Admin View", ACCENT, self._open_admin).pack(side="left", padx=10)
        self._create_btn(btn_frame, "Logout", "#64748B", self._logout).pack(side="left")

        # Notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("HCBS.TNotebook", background=BG, borderwidth=0)
        style.configure("HCBS.TNotebook.Tab", background=BG, foreground=TEXT2,
                        font=("Segoe UI Semibold", 11), padding=[22, 12])
        style.map("HCBS.TNotebook.Tab", background=[("selected", ACCENT), ("active", BG2)], foreground=[
                  ("selected", "#FFFFFF"), ("active", ACCENT)])
        style.configure("TCombobox", fieldbackground=BG, background=BG, foreground=ACCENT, arrowcolor=ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG)],
                  foreground=[("readonly", ACCENT)])
        self.root.option_add('*TCombobox*Listbox.background', BG, 100)
        self.root.option_add('*TCombobox*Listbox.foreground', ACCENT, 100)
        self.root.option_add('*TCombobox*Listbox.selectBackground', BG2, 100)
        self.root.option_add('*TCombobox*Listbox.selectForeground', ACCENT, 100)
        style.configure("TSpinbox", fieldbackground=BG, background=BG, foreground=ACCENT, arrowcolor=ACCENT)

        self.notebook = ttk.Notebook(self.root, style="HCBS.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)

        # Tabs
        self.tab_city = tk.Frame(self.notebook, bg=BG)
        self.tab_cinema = tk.Frame(self.notebook, bg=BG)
        self.tab_listing = tk.Frame(self.notebook, bg=BG)
        self.tab_overview = tk.Frame(self.notebook, bg=BG)
        self.tab_forecast = tk.Frame(self.notebook, bg=BG)
        self.tab_admin = tk.Frame(self.notebook, bg=BG)
        self.tab_staff = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_city, text="🌆 Add New City")
        self.notebook.add(self.tab_cinema, text="Add New Cinema")
        self.notebook.add(self.tab_listing, text="Add New Listing")
        self.notebook.add(self.tab_overview, text="Cinemas Overview")
        self.notebook.add(self.tab_forecast, text="Revenue Forecast")
        self.notebook.add(self.tab_admin, text="👔 Manage Admins")
        self.notebook.add(self.tab_staff, text="👥 Manage Staff")

        self._build_city_tab()
        self._build_cinema_tab()
        self._build_listing_tab()
        self._build_overview_tab()
        self._build_admin_tab()
        self._build_staff_tab()
        # Forecast tab is lazy-loaded on demand
        self.forecast_built = False
        self.forecast_container = tk.Frame(self.tab_forecast, bg=BG)
        self.forecast_container.pack(fill="both", expand=True)
        tk.Label(self.forecast_container, text="📊 Preparing forecasting engine...",
                 font=FONT_BODY, bg=BG, fg=TEXT2).pack(pady=100)

    def _on_tab_changed(self, event):
        """Handle tab switching to load data only when needed."""
        idx = self.notebook.index("current")
        if idx == 3:  # Overview
            self._load_overview()
        elif idx == 4:  # Forecast
            if not self.forecast_built:
                self._really_build_forecast_tab()
            else:
                self._generate_forecast()
        elif idx == 5:  # Admin
            self._refresh_admins()
        elif idx == 6:  # Staff
            self._refresh_staff()

    # ---- ADMIN VIEW ----
    def _open_admin(self):
        AdminWindow(tk.Toplevel(self.root))

    def _open_dashboard(self):
        from src.gui.dashboard_window import DashboardWindow
        DashboardWindow(tk.Toplevel(self.root))

    def _logout(self):
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            from src.gui.login_window import _logout_and_return
            _logout_and_return(self.root)

    # ---- TAB 0: ADD CITY ----
    def _build_city_tab(self):
        card = tk.Frame(self.tab_city, bg=BG_CARD, padx=30, pady=30,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(pady=30, padx=50, fill="x")

        tk.Label(card, text="Register New City", font=FONT_H2,
                 bg=BG_CARD, fg=TEXT).grid(row=0, column=0, columnspan=2,
                                           sticky="w", pady=(0, 20))

        # City name
        tk.Label(card, text="City Name:", font=FONT_BODY,
                 bg=BG_CARD, fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.city_name_ent = tk.Entry(
            card, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
            width=32, relief="flat",
            highlightbackground=BORDER, highlightthickness=1
        )
        self.city_name_ent.grid(row=1, column=1, sticky="w", pady=10)

        # Default pricing
        tk.Label(card, text="Default Ticket Prices", font=FONT_H2,
                 bg=BG_CARD, fg=TEXT).grid(row=2, column=0, columnspan=2,
                                           sticky="w", pady=(20, 8))

        price_frame = tk.Frame(card, bg=BG_CARD)
        price_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 10))

        tk.Label(price_frame, text="Morning (£):",
                 font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.city_p_morn = tk.Entry(
            price_frame, font=FONT_BODY, bg=BG, fg=TEXT,
            width=8, insertbackground=TEXT, relief="flat",
            highlightbackground=BORDER, highlightthickness=1
        )
        self.city_p_morn.pack(side="left", padx=(5, 20))
        self.city_p_morn.insert(0, "5.00")

        tk.Label(price_frame, text="Afternoon (£):",
                 font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.city_p_aft = tk.Entry(
            price_frame, font=FONT_BODY, bg=BG, fg=TEXT,
            width=8, insertbackground=TEXT, relief="flat",
            highlightbackground=BORDER, highlightthickness=1
        )
        self.city_p_aft.pack(side="left", padx=(5, 20))
        self.city_p_aft.insert(0, "7.00")

        tk.Label(price_frame, text="Evening (£):",
                 font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.city_p_eve = tk.Entry(
            price_frame, font=FONT_BODY, bg=BG, fg=TEXT,
            width=8, insertbackground=TEXT, relief="flat",
            highlightbackground=BORDER, highlightthickness=1
        )
        self.city_p_eve.pack(side="left", padx=(5, 0))
        self.city_p_eve.insert(0, "10.00")

        # Existing cities list
        tk.Label(card, text="Existing Cities:", font=FONT_BODY,
                 bg=BG_CARD, fg=TEXT2).grid(row=4, column=0, sticky="nw", pady=(20, 5))
        self.city_list_var = tk.StringVar()
        self.city_listbox = tk.Listbox(
            card, listvariable=self.city_list_var,
            font=FONT_BODY, bg=BG, fg=TEXT,
            selectbackground=ACCENT, selectforeground=TEXT,
            relief="flat", highlightbackground=BORDER, highlightthickness=1,
            height=6, width=32
        )
        self.city_listbox.grid(row=4, column=1, sticky="w", pady=(20, 5))
        self._refresh_city_list()

        tk.Button(
            card, text="➕ Add City", bg=SUCCESS, fg=TEXT,
            font=FONT_BTN, relief="flat", padx=20, pady=10,
            cursor="hand2", command=self._submit_city
        ).grid(row=5, column=0, columnspan=2, pady=20)

    def _refresh_city_list(self):
        """Refresh the existing-cities listbox and the cinema-tab city dropdown."""
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT city_name FROM cities ORDER BY city_name"
            ).fetchall()
            names = [r["city_name"] for r in rows]
            # Update the listbox on this tab
            if hasattr(self, "city_listbox"):
                self.city_listbox.delete(0, tk.END)
                for n in names:
                    self.city_listbox.insert(tk.END, n)
            # Also keep the cinema-tab combobox in sync
            if hasattr(self, "cinema_city_cb"):
                self.cinema_city_cb["values"] = names
        except Exception as e:
            print(f"Error refreshing city list: {e}")

    def _refresh_all_cinema_data(self):
        """Unified refresh for all tabs that display cinema/city lists."""
        self._load_overview()       # Overview tab
        self._load_listing_data()   # Listing tab
        self._refresh_city_list()    # City/Cinema tabs

        # Forecast tab
        try:
            conn = get_connection()
            cinemas = conn.execute("SELECT cinema_name FROM cinemas ORDER BY cinema_name").fetchall()
            if hasattr(self, "forecast_cinema_cb"):
                self.forecast_cinema_cb["values"] = [c["cinema_name"] for c in cinemas]
        except Exception as e:
            print(f"Error refreshing forecast cinema list: {e}")

    def _submit_city(self):
        from src.utils.input_validator import InputValidator
        city_name = InputValidator.sanitise_text(self.city_name_ent.get(), 100)
        if not city_name:
            messagebox.showerror("Validation Error", "City name is required.")
            return

        try:
            pm = float(self.city_p_morn.get())
            pa = float(self.city_p_aft.get())
            pe = float(self.city_p_eve.get())
        except ValueError:
            messagebox.showerror("Validation Error",
                                 "Prices must be valid numbers.")
            return

        if any(p <= 0 for p in (pm, pa, pe)):
            messagebox.showerror("Validation Error",
                                 "All prices must be greater than zero.")
            return

        try:
            conn = get_connection()
            # Check duplicate
            existing = conn.execute(
                "SELECT city_id FROM cities WHERE LOWER(city_name) = ?",
                (city_name.lower(),)
            ).fetchone()
            if existing:
                messagebox.showerror(
                    "Duplicate",
                    f"City '{city_name}' already exists."
                )
                return

            conn.execute("BEGIN")
            cur = conn.execute(
                "INSERT INTO cities (city_name) VALUES (?)", (city_name,)
            )
            city_id = cur.lastrowid

            today_iso = datetime.date.today().isoformat()
            for stype, price in [
                ("morning", pm), ("afternoon", pa), ("evening", pe)
            ]:
                conn.execute(
                    "INSERT INTO prices (city_id, show_type, lower_hall_price, effective_from) "
                    "VALUES (?, ?, ?, ?)",
                    (city_id, stype, price, today_iso)
                )

            conn.commit()
            messagebox.showinfo(
                "Success",
                f"City '{city_name}' added with prices:\n"
                f"  Morning: £{pm:.2f}  |  Afternoon: £{pa:.2f}  |  Evening: £{pe:.2f}"
            )
            self.city_name_ent.delete(0, tk.END)
            self._refresh_all_cinema_data()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to add city:\n{e}")

    # ---- TAB 1: ADD CINEMA ----
    def _build_cinema_tab(self):
        card = tk.Frame(self.tab_cinema, bg=BG_CARD, padx=30, pady=30, highlightbackground=BORDER, highlightthickness=1)
        card.pack(pady=30, padx=50, fill="x")

        tk.Label(card, text="Register New Cinema Location", font=FONT_H2, bg=BG_CARD,
                 fg=TEXT).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        # City — loaded dynamically from DB
        tk.Label(card, text="City:", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.cinema_city_cb = ttk.Combobox(card, font=FONT_BODY, width=30)
        self.cinema_city_cb.grid(row=1, column=1, sticky="w", pady=10)
        self._refresh_city_list()  # populate from DB

        # Name
        tk.Label(card, text="Cinema Name:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=2, column=0, sticky="w", pady=10)
        self.cinema_name_ent = tk.Entry(card, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                        width=32, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.cinema_name_ent.grid(row=2, column=1, sticky="w", pady=10)

        # Location
        tk.Label(card, text="Location/Address:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=3, column=0, sticky="w", pady=10)
        self.cinema_loc_ent = tk.Entry(card, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=32, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.cinema_loc_ent.grid(row=3, column=1, sticky="w", pady=10)

        # Screens Config
        tk.Label(card, text="Auto-Create Screens:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=4, column=0, sticky="w", pady=10)
        self.cinema_screens_spin = ttk.Spinbox(card, from_=1, to=6, font=FONT_BODY, width=5)
        self.cinema_screens_spin.set(3)
        self.cinema_screens_spin.grid(row=4, column=1, sticky="w", pady=10)

        tk.Label(card, text="Capacity per Screen (50-120):", font=FONT_BODY,
                 bg=BG_CARD, fg=TEXT2).grid(row=5, column=0, sticky="w", pady=10)
        self.cinema_cap_spin = ttk.Spinbox(card, from_=50, to=120, font=FONT_BODY, width=5)
        self.cinema_cap_spin.set(100)
        self.cinema_cap_spin.grid(row=5, column=1, sticky="w", pady=10)

        # Submit
        tk.Button(card, text="Create Cinema", bg=SUCCESS, fg=TEXT, font=FONT_BTN, relief="flat", padx=20,
                  pady=10, cursor="hand2", command=self._submit_cinema).grid(row=6, column=0, columnspan=2, pady=20)

    def _submit_cinema(self):
        from src.utils.input_validator import InputValidator
        city = InputValidator.sanitise_text(self.cinema_city_cb.get(), 100)
        name = InputValidator.sanitise_text(self.cinema_name_ent.get(), 100)
        loc = InputValidator.sanitise_text(self.cinema_loc_ent.get(), 200)
        try:
            screens = int(self.cinema_screens_spin.get())
            capacity = int(self.cinema_cap_spin.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Screens and capacity must be valid numbers.")
            return

        if not city or not name or not loc:
            messagebox.showerror("Validation Error", "All text fields are required.")
            return

        if not (1 <= screens <= 6):
            messagebox.showerror("Validation Error", "Screens must be between 1 and 6.")
            return

        if not (50 <= capacity <= 120):
            messagebox.showerror("Validation Error", "Capacity must be between 50 and 120.")
            return

        try:
            conn = get_connection()
            conn.execute("BEGIN")

            # Lookup or insert city
            cur = conn.execute("SELECT city_id FROM cities WHERE LOWER(city_name) = ?", (city.lower(),))
            city_row = cur.fetchone()
            if city_row:
                city_id = city_row["city_id"]
            else:
                cur = conn.execute("INSERT INTO cities (city_name) VALUES (?)", (city,))
                city_id = cur.lastrowid

            # Insert Cinema
            try:
                cur = conn.execute(
                    "INSERT INTO cinemas (city_id, cinema_name, location) VALUES (?, ?, ?)", (city_id, name, loc))
            except sqlite3.OperationalError:
                cur = conn.execute("INSERT INTO cinemas (city_id, cinema_name) VALUES (?, ?)", (city_id, name))

            cinema_id = cur.lastrowid

            # Insert Screens automatically
            lower = int(capacity * 0.6)
            upper = int(capacity * 0.3)
            vip = capacity - lower - upper

            for i in range(1, screens + 1):
                conn.execute(
                    """
                    INSERT INTO screens (
                        cinema_id, screen_number, total_capacity,
                        lower_hall_seats, upper_gallery_seats, vip_seats
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cinema_id, i, capacity, lower, upper, vip)
                )

            conn.commit()
            messagebox.showinfo("Success", f"Cinema '{name}' in {city} created successfully with {screens} screens!")

            # Clear form & refresh
            self.cinema_name_ent.delete(0, tk.END)
            self.cinema_loc_ent.delete(0, tk.END)
            self._refresh_all_cinema_data()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to add cinema:\n{e}")

    # ---- TAB 2: ADD LISTING ----
    def _build_listing_tab(self):
        card = tk.Frame(self.tab_listing, bg=BG_CARD, padx=30, pady=30,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(pady=30, padx=50, fill="x")

        tk.Label(card, text="Create Film Listing", font=FONT_H2, bg=BG_CARD, fg=TEXT).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 20))

        # Row 1
        tk.Label(card, text="Cinema:", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.list_cinema_cb = ttk.Combobox(card, state="readonly", font=FONT_BODY, width=25)
        self.list_cinema_cb.grid(row=1, column=1, sticky="w", pady=10, padx=(0, 20))
        self.list_cinema_cb.bind("<<ComboboxSelected>>", self._on_list_cinema_change)

        tk.Label(card, text="Film:", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).grid(row=1, column=2, sticky="w", pady=10)
        self.list_film_cb = ttk.Combobox(card, state="readonly", font=FONT_BODY, width=25)
        self.list_film_cb.grid(row=1, column=3, sticky="w", pady=10)

        # Row 2
        tk.Label(card, text="Screen:", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).grid(row=2, column=0, sticky="w", pady=10)
        self.list_screen_cb = ttk.Combobox(card, state="readonly", font=FONT_BODY, width=25)
        self.list_screen_cb.grid(row=2, column=1, sticky="w", pady=10, padx=(0, 20))

        tk.Label(card, text="Date (YYYY-MM-DD):", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=2, column=2, sticky="w", pady=10)
        self.list_date_ent = tk.Entry(card, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                      width=27, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.list_date_ent.grid(row=2, column=3, sticky="w", pady=10)
        self.list_date_ent.insert(0, datetime.date.today().isoformat())

        # Row 3: Times
        tk.Label(card, text="Show Times (Comma separated, max 3):", font=FONT_BODY,
                 bg=BG_CARD, fg=TEXT2).grid(row=3, column=0, columnspan=2, sticky="w", pady=10)
        self.list_times_ent = tk.Entry(card, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=30, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.list_times_ent.grid(row=3, column=2, columnspan=2, sticky="w", pady=10)
        self.list_times_ent.insert(0, "10:00, 14:00, 19:00")

        # Row 4: Pricing Setup
        tk.Label(card, text="Pricing (Lower Hall base):", font=FONT_H2, bg=BG_CARD,
                 fg=TEXT).grid(row=4, column=0, columnspan=4, sticky="w", pady=(20, 10))

        price_frame = tk.Frame(card, bg=BG_CARD)
        price_frame.grid(row=5, column=0, columnspan=4, sticky="w")

        tk.Label(price_frame, text="Morning (£):", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.p_morn_ent = tk.Entry(price_frame, font=FONT_BODY, bg=BG, fg=TEXT, width=8,
                                   insertbackground=TEXT, relief="flat",
                                   highlightbackground=BORDER, highlightthickness=1)
        self.p_morn_ent.pack(side="left", padx=(5, 15))
        self.p_morn_ent.insert(0, "5.00")

        tk.Label(price_frame, text="Afternoon (£):", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.p_aft_ent = tk.Entry(price_frame, font=FONT_BODY, bg=BG, fg=TEXT, width=8,
                                  insertbackground=TEXT, relief="flat",
                                  highlightbackground=BORDER, highlightthickness=1)
        self.p_aft_ent.pack(side="left", padx=(5, 15))
        self.p_aft_ent.insert(0, "7.00")

        tk.Label(price_frame, text="Evening (£):", font=FONT_BODY, bg=BG_CARD, fg=TEXT2).pack(side="left")
        self.p_eve_ent = tk.Entry(price_frame, font=FONT_BODY, bg=BG, fg=TEXT, width=8,
                                  insertbackground=TEXT, relief="flat",
                                  highlightbackground=BORDER, highlightthickness=1)
        self.p_eve_ent.pack(side="left", padx=(5, 15))
        self.p_eve_ent.insert(0, "10.00")

        tk.Button(card, text="Submit Listing", bg=SUCCESS, fg=TEXT, font=FONT_BTN, relief="flat", padx=20,
                  pady=10, cursor="hand2", command=self._submit_listing).grid(row=6, column=0, columnspan=4, pady=20)

        self._load_listing_data()

    def _load_listing_data(self):
        try:
            conn = get_connection()
            cur = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name")
            self._cinemas = cur.fetchall()
            self.list_cinema_cb['values'] = [c["cinema_name"] for c in self._cinemas]

            cur = conn.execute("SELECT film_id, title FROM films ORDER BY title")
            self._films = cur.fetchall()
            self.list_film_cb['values'] = [f["title"] for f in self._films]

        except Exception as e:
            print(f"Error loading listing form data: {e}")

    def _on_list_cinema_change(self, event=None):
        idx = self.list_cinema_cb.current()
        if idx < 0:
            return
        cid = self._cinemas[idx]["cinema_id"]
        try:
            conn = get_connection()
            cur = conn.execute(
                "SELECT screen_id, screen_number FROM screens WHERE cinema_id = ? ORDER BY screen_number", (cid,))
            self._screens = cur.fetchall()
            self.list_screen_cb['values'] = [f"Screen {s['screen_number']}" for s in self._screens]
            if self._screens:
                self.list_screen_cb.current(0)
        except Exception as e:
            print(f"Error loading screens: {e}")

    def _submit_listing(self):
        c_idx = self.list_cinema_cb.current()
        f_idx = self.list_film_cb.current()
        s_idx = self.list_screen_cb.current()

        if c_idx < 0 or f_idx < 0 or s_idx < 0:
            messagebox.showerror("Error", "Please select Cinema, Film, and Screen.")
            return

        cid = self._cinemas[c_idx]["cinema_id"]
        fid = self._films[f_idx]["film_id"]
        sid = self._screens[s_idx]["screen_id"]

        date_str = self.list_date_ent.get().strip()
        from src.utils.input_validator import InputValidator
        if not InputValidator.validate_date(date_str):
            messagebox.showerror("Error", "Invalid Date format. Use YYYY-MM-DD.")
            return

        times_raw = self.list_times_ent.get().split(',')
        times = [t.strip() for t in times_raw if t.strip()]
        if not times or len(times) > 3:
            messagebox.showerror("Error", "Please enter 1 to 3 valid show times.")
            return

        try:
            pm = float(self.p_morn_ent.get())
            pa = float(self.p_aft_ent.get())
            pe = float(self.p_eve_ent.get())
        except ValueError:
            messagebox.showerror("Error", "Prices must be numbers.")
            return

        try:
            conn = get_connection()

            # Validate no overlap
            for t in times:
                cur = conn.execute(
                    "SELECT showing_id FROM showings WHERE screen_id = ? AND show_date = ? AND show_time = ?",
                    (sid, date_str, t)
                )
                if cur.fetchone():
                    messagebox.showerror("Overlap Error", f"Time {t} already has a showing on this screen!")
                    return

            conn.execute("BEGIN")

            cur = conn.execute("SELECT city_id FROM cinemas WHERE cinema_id = ?", (cid,))
            city_id = cur.fetchone()["city_id"]

            today_iso = datetime.date.today().isoformat()
            for stype, price in [("morning", pm), ("afternoon", pa), ("evening", pe)]:
                cur = conn.execute("SELECT price_id FROM prices WHERE city_id = ? AND show_type = ?", (city_id, stype))
                if cur.fetchone():
                    conn.execute(
                        """
                        UPDATE prices
                        SET lower_hall_price = ?, effective_from = ?
                        WHERE city_id = ? AND show_type = ?
                        """,
                        (price, today_iso, city_id, stype)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO prices (city_id, show_type, lower_hall_price, effective_from)
                        VALUES (?, ?, ?, ?)
                        """,
                        (city_id, stype, price, today_iso)
                    )

            cur = conn.execute("SELECT total_capacity FROM screens WHERE screen_id = ?", (sid,))
            cap = cur.fetchone()["total_capacity"]

            # Insert Showings
            for t in times:
                hr = int(t.split(':')[0])
                if hr < 12:
                    show_type = "morning"
                elif hr < 17:
                    show_type = "afternoon"
                else:
                    show_type = "evening"

                conn.execute(
                    """
                    INSERT INTO showings (
                        film_id, screen_id, show_date, show_time,
                        show_type, seats_remaining
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (fid, sid, date_str, t, show_type, cap)
                )

            conn.commit()
            messagebox.showinfo("Success", "Listings and prices successfully saved!")
            self._load_overview()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", str(e))

    # ---- TAB 3: OVERVIEW ----
    def _build_overview_tab(self):
        fr = tk.Frame(self.tab_overview, bg=BG)
        fr.pack(fill="both", expand=True, padx=30, pady=30)

        tk.Label(fr, text="Cinemas Overview", font=FONT_H2, bg=BG, fg="#F2EAD3").pack(anchor="w", pady=(0, 10))

        style = ttk.Style()
        style.configure("HCBS.Treeview", background=BG_CARD, foreground=TEXT,
                        fieldbackground=BG_CARD, borderwidth=0, font=FONT_BODY, rowheight=35)
        style.configure("HCBS.Treeview.Heading", background=BG2, foreground=ACCENT, font=FONT_BTN)

        cols = ("city", "cinema", "screens", "listings")
        self.tv = ttk.Treeview(fr, columns=cols, show="headings", style="HCBS.Treeview")

        self.tv.heading("city", text="City")
        self.tv.heading("cinema", text="Cinema Name")
        self.tv.heading("screens", text="Screen Count")
        self.tv.heading("listings", text="Active Listings")

        self.tv.column("city", width=150)
        self.tv.column("cinema", width=250)
        self.tv.column("screens", width=120, anchor="center")
        self.tv.column("listings", width=120, anchor="center")

        scroll = ttk.Scrollbar(fr, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=scroll.set)

        self.tv.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        btn_fr = tk.Frame(self.tab_overview, bg=BG)
        btn_fr.pack(fill="x", padx=30, pady=(0, 30))
        tk.Button(btn_fr, text="Refresh Data", bg=BG2, fg=TEXT, font=FONT_BTN, relief="flat",
                  padx=15, pady=8, cursor="hand2", command=self._load_overview).pack(side="right")

    def _load_overview(self):
        for item in self.tv.get_children():
            self.tv.delete(item)

        try:
            conn = get_connection()
            query = """
            SELECT c.city_name, cn.cinema_name,
                   COUNT(DISTINCT s.screen_id) as screen_count,
                   COUNT(DISTINCT CASE WHEN sh.is_cancelled = 0 THEN sh.showing_id END) as listing_count
            FROM cities c
            JOIN cinemas cn ON c.city_id = cn.city_id
            LEFT JOIN screens s ON cn.cinema_id = s.cinema_id
            LEFT JOIN showings sh ON s.screen_id = sh.screen_id
            GROUP BY cn.cinema_id
            ORDER BY c.city_name, cn.cinema_name
            """
            cur = conn.execute(query)
            for row in cur.fetchall():
                self.tv.insert("", "end", values=(
                    row["city_name"],
                    row["cinema_name"],
                    row["screen_count"],
                    row["listing_count"]
                ))
        except Exception as e:
            print(f"Overview loading error: {e}")

    def _really_build_forecast_tab(self):
        """Actual construction of the forecast UI (heavy imports and canvas)."""
        if self.forecast_built:
            return

        # Clear the "Preparing..." label
        for child in self.forecast_container.winfo_children():
            child.destroy()

        ctrl_fr = tk.Frame(self.forecast_container, bg=BG2, pady=15, padx=20)
        ctrl_fr.pack(fill="x")

        tk.Label(ctrl_fr, text="Select Cinema:", font=FONT_BODY, bg=BG2, fg=TEXT2).pack(side="left")
        self.forecast_cinema_var = tk.StringVar()
        self.forecast_cinema_cb = ttk.Combobox(
            ctrl_fr, textvariable=self.forecast_cinema_var, state="readonly", font=FONT_BODY, width=30)
        self.forecast_cinema_cb.pack(side="left", padx=10)
        self.forecast_cinema_cb.bind("<<ComboboxSelected>>", self._generate_forecast)

        self.forecast_metric_lbl = tk.Label(ctrl_fr, text="Next Month Forecast: £0.00",
                                            font=FONT_H2, bg=BG2, fg=SUCCESS)
        self.forecast_metric_lbl.pack(side="right", padx=20)

        self.forecast_plot_fr = tk.Frame(self.forecast_container, bg=BG, padx=20, pady=20)
        self.forecast_plot_fr.pack(fill="both", expand=True)

        # Heavy imports deferred here
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            self.forecast_fig = Figure(figsize=(8, 4), dpi=144, facecolor=BG)
            self.forecast_ax = self.forecast_fig.add_subplot(111)
            self.forecast_ax.set_facecolor(BG2)

            self.forecast_canvas = FigureCanvasTkAgg(self.forecast_fig, master=self.forecast_plot_fr)
            self.forecast_canvas.get_tk_widget().pack(fill="both", expand=True)

            conn = get_connection()
            cinemas = conn.execute("SELECT cinema_name FROM cinemas ORDER BY cinema_name").fetchall()
            self.forecast_cinema_cb["values"] = [c["cinema_name"] for c in cinemas]
            if cinemas:
                self.forecast_cinema_cb.current(0)

            self.forecast_built = True
            self._generate_forecast()
        except ImportError:
            tk.Label(self.forecast_container, text="Error: Required libraries (matplotlib/pandas) missing.",
                     fg=ERROR, bg=BG).pack(pady=20)

    def _build_forecast_tab(self):
        # Placeholder for compatibility, but we use _really_build_forecast_tab
        pass

    def _generate_forecast(self, event=None):
        cinema_name = self.forecast_cinema_var.get()
        if not cinema_name:
            return

        conn = get_connection()
        c_row = conn.execute("SELECT cinema_id FROM cinemas WHERE cinema_name = ?", (cinema_name,)).fetchone()
        if not c_row:
            return

        cid = c_row["cinema_id"]

        from src.utils.revenue_forecaster import forecast_revenue
        df, preds = forecast_revenue(cid)

        self.forecast_ax.clear()
        self.forecast_ax.set_facecolor(BG2)
        self.forecast_fig.set_facecolor(BG)

        if not df.empty:
            x_actual = df["label"].tolist()
            y_actual = df["total_revenue"].tolist()

            x_pred = [p[0] for p in preds]
            y_pred = [p[1] for p in preds]

            self.forecast_ax.bar(x_actual, y_actual, color="#4f8cff", label="Actual Revenue")
            self.forecast_ax.bar(x_pred, y_pred, color="#22c55e", hatch="//", label="Predicted Revenue")

            self.forecast_ax.set_title(f"Revenue Forecast for {cinema_name}", color=TEXT)
            self.forecast_ax.tick_params(colors=TEXT2)
            for sp in self.forecast_ax.spines.values():
                sp.set_color(BORDER)

            self.forecast_ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TEXT)

            if preds:
                self.forecast_metric_lbl.config(text=f"Next Month Forecast: £{preds[0][1]:,.2f}")
        else:
            self.forecast_ax.text(0.5, 0.5, "No historical data available for this cinema",
                                  ha='center', va='center', color=TEXT2, transform=self.forecast_ax.transAxes)
            self.forecast_metric_lbl.config(text="Next Month Forecast: £0.00")

        self.forecast_fig.tight_layout()
        self.forecast_canvas.draw()

    # ---- TAB 5: MANAGE ADMINS ----
    def _build_admin_tab(self):
        # Split view: left for form, right for treeview
        main_fr = tk.Frame(self.tab_admin, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=20, pady=20)

        # Left side: Form
        form_fr = tk.Frame(main_fr, bg=BG_CARD, padx=20, pady=20, highlightbackground=BORDER, highlightthickness=1)
        form_fr.pack(side="left", fill="y", padx=(0, 20))

        tk.Label(form_fr, text="Register New Admin", font=FONT_H2, bg=BG_CARD, fg=TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        tk.Label(form_fr, text="Username:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.admin_user_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.admin_user_ent.grid(row=1, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Password:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=2, column=0, sticky="w", pady=10)
        self.admin_pass_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, show="*", relief="flat",
                                       highlightbackground=BORDER, highlightthickness=1)
        self.admin_pass_ent.grid(row=2, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Full Name:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=3, column=0, sticky="w", pady=10)
        self.admin_name_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.admin_name_ent.grid(row=3, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Email:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=4, column=0, sticky="w", pady=10)
        self.admin_email_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                        width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.admin_email_ent.grid(row=4, column=1, sticky="w", pady=10)

        tk.Button(form_fr, text="➕ Create Admin", bg=SUCCESS, fg=TEXT, font=FONT_BTN, relief="flat", padx=15,
                  pady=8, cursor="hand2", command=self._submit_admin).grid(row=5, column=0, columnspan=2, pady=(30, 0))

        # Right side: Treeview
        list_fr = tk.Frame(main_fr, bg=BG)
        list_fr.pack(side="left", fill="both", expand=True)

        tk.Label(list_fr, text="Current Admin Accounts", font=FONT_H2, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 10))

        cols = ("ID", "Username", "Full Name", "Email", "Status")
        self.admin_tv = ttk.Treeview(list_fr, columns=cols, show="headings", style="HCBS.Treeview")
        for c in cols:
            self.admin_tv.heading(c, text=c)
        self.admin_tv.column("ID", width=50, anchor="center")
        self.admin_tv.column("Username", width=120)
        self.admin_tv.column("Full Name", width=150)
        self.admin_tv.column("Email", width=180)
        self.admin_tv.column("Status", width=80, anchor="center")

        sb = ttk.Scrollbar(list_fr, orient="vertical", command=self.admin_tv.yview)
        self.admin_tv.configure(yscrollcommand=sb.set)
        self.admin_tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Button(list_fr, text="🗑 Remove Selected", bg=WARNING, fg="#000", font=("Segoe UI", 9),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=self._remove_admin).pack(pady=(20, 10))

        self._refresh_admins()

    def _refresh_admins(self):
        from src.models.user import User
        for row in self.admin_tv.get_children():
            self.admin_tv.delete(row)
        try:
            admins = User.get_users_by_role('admin')
            for a in admins:
                status = "Active" if a["is_active"] else "Inactive"
                self.admin_tv.insert("", "end", values=(
                    a["user_id"], a["username"], a["full_name"], a["email"], status))
        except Exception as e:
            print(f"Error loading admins: {e}")

    def _submit_admin(self):
        from src.models.user import User
        u = self.admin_user_ent.get().strip()
        p = self.admin_pass_ent.get().strip()
        fn = self.admin_name_ent.get().strip()
        e = self.admin_email_ent.get().strip()

        if not u or not p or not fn:
            messagebox.showerror("Validation Error", "Username, Password, and Full Name are required.")
            return

        if len(p) < 6:
            messagebox.showerror("Validation Error", "Password must be at least 6 characters.")
            return

        try:
            User.create_user(username=u, password=p, full_name=fn, email=e, role='admin')
            messagebox.showinfo("Success", f"Admin '{u}' created successfully.")
            self.admin_user_ent.delete(0, tk.END)
            self.admin_pass_ent.delete(0, tk.END)
            self.admin_name_ent.delete(0, tk.END)
            self.admin_email_ent.delete(0, tk.END)
            self._refresh_admins()
        except ValueError as ve:
            messagebox.showerror("Validation Error", str(ve))
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to create admin: {ex}")

    def _remove_admin(self):
        from src.models.user import User
        sel = self.admin_tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select an admin to remove.")
            return

        uid, uname = self.admin_tv.item(sel[0])["values"][:2]

        if messagebox.askyesno("Confirm Removal",
                               f"Are you sure you want to PERMANENTLY delete admin account '{uname}'?"):
            if User.delete_user(uid):
                messagebox.showinfo("Success", f"Admin '{uname}' removed.")
                self._refresh_admins()
            else:
                messagebox.showerror("Error", "Could not remove admin.")

    # ---- TAB 6: MANAGE STAFF ----
    def _build_staff_tab(self):
        main_fr = tk.Frame(self.tab_staff, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=20, pady=20)

        # Left side: Form
        form_fr = tk.Frame(main_fr, bg=BG_CARD, padx=20, pady=20, highlightbackground=BORDER, highlightthickness=1)
        form_fr.pack(side="left", fill="y", padx=(0, 20))

        tk.Label(form_fr, text="Register New Staff", font=FONT_H2, bg=BG_CARD, fg=TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        tk.Label(form_fr, text="Username:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.staff_user_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_user_ent.grid(row=1, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Password:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=2, column=0, sticky="w", pady=10)
        self.staff_pass_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, show="*", relief="flat",
                                       highlightbackground=BORDER, highlightthickness=1)
        self.staff_pass_ent.grid(row=2, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Full Name:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=3, column=0, sticky="w", pady=10)
        self.staff_name_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_name_ent.grid(row=3, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Email:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=4, column=0, sticky="w", pady=10)
        self.staff_email_ent = tk.Entry(form_fr, font=FONT_BODY, bg=BG, fg=TEXT, insertbackground=TEXT,
                                        width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_email_ent.grid(row=4, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Cinema:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT2).grid(row=5, column=0, sticky="w", pady=10)
        self.staff_cinema_cb = ttk.Combobox(form_fr, state="readonly", font=FONT_BODY, width=23)
        self.staff_cinema_cb.grid(row=5, column=1, sticky="w", pady=10)

        tk.Button(form_fr, text="➕ Create Staff", bg=SUCCESS, fg=TEXT, font=FONT_BTN, relief="flat", padx=15,
                  pady=8, cursor="hand2", command=self._submit_staff).grid(row=6, column=0, columnspan=2, pady=(30, 0))

        # Right side: Treeview
        list_fr = tk.Frame(main_fr, bg=BG)
        list_fr.pack(side="left", fill="both", expand=True)

        tk.Label(list_fr, text="Current Staff Accounts", font=FONT_H2, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 10))

        cols = ("ID", "Username", "Full Name", "Cinema", "Status")
        self.staff_tv = ttk.Treeview(list_fr, columns=cols, show="headings", style="HCBS.Treeview")
        for c in cols:
            self.staff_tv.heading(c, text=c)
        self.staff_tv.column("ID", width=50, anchor="center")
        self.staff_tv.column("Username", width=120)
        self.staff_tv.column("Full Name", width=150)
        self.staff_tv.column("Cinema", width=150)
        self.staff_tv.column("Status", width=80, anchor="center")

        sb = ttk.Scrollbar(list_fr, orient="vertical", command=self.staff_tv.yview)
        self.staff_tv.configure(yscrollcommand=sb.set)
        self.staff_tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Button(list_fr, text="🗑 Remove Selected", bg=WARNING, fg="#000", font=("Segoe UI", 9),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=self._remove_staff).pack(pady=(20, 10))

        self._refresh_staff()

    def _refresh_staff(self):
        from src.models.user import User
        for row in self.staff_tv.get_children():
            self.staff_tv.delete(row)
        try:
            conn = get_connection()
            cinemas = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name").fetchall()
            self._cinemas_data = {c["cinema_name"]: c["cinema_id"] for c in cinemas}
            self.staff_cinema_cb['values'] = list(self._cinemas_data.keys())
            if self.staff_cinema_cb['values']:
                self.staff_cinema_cb.current(0)

            staff = User.get_users_by_role('staff')
            for s in staff:
                status = "Active" if s["is_active"] else "Inactive"
                c_name = s["cinema_name"] or "Unassigned"
                self.staff_tv.insert("", "end", values=(s["user_id"], s["username"], s["full_name"], c_name, status))
        except Exception as e:
            print(f"Error loading staff: {e}")

    def _submit_staff(self):
        from src.models.user import User
        u = self.staff_user_ent.get().strip()
        p = self.staff_pass_ent.get().strip()
        fn = self.staff_name_ent.get().strip()
        e = self.staff_email_ent.get().strip()
        c_name = self.staff_cinema_cb.get()

        if not u or not p or not fn:
            messagebox.showerror("Validation Error", "Username, Password, and Full Name are required.")
            return

        if len(p) < 6:
            messagebox.showerror("Validation Error", "Password must be at least 6 characters.")
            return

        cid = self._cinemas_data.get(c_name)

        try:
            User.create_user(username=u, password=p, full_name=fn, email=e, role='staff', cinema_id=cid)
            messagebox.showinfo("Success", f"Staff '{u}' created successfully.")
            self.staff_user_ent.delete(0, tk.END)
            self.staff_pass_ent.delete(0, tk.END)
            self.staff_name_ent.delete(0, tk.END)
            self.staff_email_ent.delete(0, tk.END)
            self._refresh_staff()
        except ValueError as ve:
            messagebox.showerror("Validation Error", str(ve))
        except Exception as ex:
            messagebox.showerror("Database Error", f"Failed to create staff: {ex}")

    def _remove_staff(self):
        from src.models.user import User
        sel = self.staff_tv.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a staff member to remove.")
            return

        uid, uname = self.staff_tv.item(sel[0])["values"][:2]

        if messagebox.askyesno("Confirm Removal",
                               f"Are you sure you want to PERMANENTLY delete staff account '{uname}'?"):
            if User.delete_user(uid):
                messagebox.showinfo("Success", f"Staff '{uname}' removed.")
                self._refresh_staff()
            else:
                messagebox.showerror("Error", "Could not remove staff.")


if __name__ == "__main__":
    from src.models.user import User
    r = tk.Tk()
    r.withdraw()
    sess = SessionManager.get_instance()
    sess.set_current_user(User(1, 1, "manager_mock", "", "Manager User", "", "manager"))
    mw = ManagerWindow(tk.Toplevel(r))
    r.mainloop()
