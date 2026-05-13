from src.utils.rbac import require_role
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import datetime
import os
import shutil
import uuid
from src.database.db_connection import get_connection
from src.gui.login_window import SessionManager
from src.models.film import Film
from src.models.showing import Showing

import matplotlib
matplotlib.use("TkAgg")

BG = "#0b1220"
BG2 = "#111b2e"
ACCENT = "#4f8cff"
FG = "#f8fafc"
TEXT2 = "#a7b4c8"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#f59e0b"
BORDER = "#26344a"


@require_role('admin')
class AdminWindow:
    def __init__(self, root: tk.Tk) -> None:
        print("[DEBUG] AdminWindow.__init__ called")
        self.root = root

        session = SessionManager.get_instance()
        self.user = session.get_current_user()

        self.root.title("HCBS — Admin Dashboard")
        self.root.configure(bg=BG)
        self.root.geometry("1100x750")

        self._build_topbar()
        print("[DEBUG] AdminWindow._build_topbar done")
        self._build_notebook()
        print("[DEBUG] AdminWindow._build_notebook done")

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

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=BG2, pady=10, padx=20)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text=f"🎬 Admin Dashboard — {self.user.full_name}", font=(
            "Segoe UI Variable Display", 16, "bold"), bg=BG2, fg=ACCENT).pack(side="left")

        self._create_btn(bar, "Logout", ERROR, self._logout).pack(side="right", padx=5)
        self._create_btn(bar, "Cancel Booking", "#B91C1C", self._open_cancellation).pack(side="right", padx=5)
        self._create_btn(bar, "📊 Live Dashboard", "#0D9488", self._open_dashboard).pack(side="right", padx=5)

    def _build_notebook(self):
        print("[DEBUG] AdminWindow._build_notebook called")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG, foreground=TEXT2,
                        padding=[20, 12], font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT), ("active", BG2)],
                  foreground=[("selected", "#FFFFFF"), ("active", ACCENT)])

        # Customize treeview style
        style.configure("Treeview", background=BG, foreground=ACCENT, fieldbackground=BG, rowheight=35, borderwidth=0)
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])
        style.configure("Treeview.Heading", background=BG2, foreground=ACCENT, font=("Segoe UI", 10, "bold"))

        style.configure("TCombobox", fieldbackground=BG, background=BG, foreground=ACCENT, arrowcolor=ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG)],
                  foreground=[("readonly", ACCENT)])

        self.root.option_add('*TCombobox*Listbox.background', BG, 100)
        self.root.option_add('*TCombobox*Listbox.foreground', ACCENT, 100)
        self.root.option_add('*TCombobox*Listbox.selectBackground', BG2, 100)
        self.root.option_add('*TCombobox*Listbox.selectForeground', ACCENT, 100)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)

        self.tab_films = tk.Frame(self.notebook, bg=BG)
        self.tab_showings = tk.Frame(self.notebook, bg=BG)
        self.tab_bookings = tk.Frame(self.notebook, bg=BG)
        self.tab_reports = tk.Frame(self.notebook, bg=BG)
        self.tab_chart = tk.Frame(self.notebook, bg=BG)
        self.tab_revenue = tk.Frame(self.notebook, bg=BG)
        self.tab_heatmap = tk.Frame(self.notebook, bg=BG)
        self.tab_leaderboard = tk.Frame(self.notebook, bg=BG)
        self.tab_waitlist = tk.Frame(self.notebook, bg=BG)
        self.tab_customers = tk.Frame(self.notebook, bg=BG)
        self.tab_staff = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_films, text="Films")
        self.notebook.add(self.tab_showings, text="Showings")
        self.notebook.add(self.tab_bookings, text="📅 Bookings")
        self.notebook.add(self.tab_reports, text="Reports")
        self.notebook.add(self.tab_chart, text="📊 Revenue Chart")
        self.notebook.add(self.tab_revenue, text="📅 Monthly Revenue")
        self.notebook.add(self.tab_heatmap, text="🔥 Occupancy Heatmap")
        self.notebook.add(self.tab_leaderboard, text="🏆 Staff Leaderboard")
        self.notebook.add(self.tab_waitlist, text="⏳ Waitlist")
        self.notebook.add(self.tab_customers, text="👥 Customers")
        self.notebook.add(self.tab_staff, text="👔 Manage Staff")

        self._build_films_tab()
        self._build_showings_tab()
        self._build_bookings_tab()
        self._build_reports_tab()
        self._build_chart_tab()
        self._build_revenue_tab()
        self._build_heatmap_tab()
        self._build_leaderboard_tab()
        self._build_waitlist_tab()
        self._build_customers_tab()
        self._build_staff_tab()

    # --- FILMS TAB ---
    def _build_films_tab(self):
        print("[DEBUG] AdminWindow._build_films_tab called")
        top = tk.Frame(self.tab_films, bg=BG, pady=10)
        top.pack(fill="x")

        self._create_btn(top, "+ Add Film", SUCCESS, self._open_add_film).pack(side="left", padx=5)
        self._create_btn(top, "✎ Edit Film", ACCENT, self._open_edit_film).pack(side="left", padx=5)
        self._create_btn(top, "✕ Remove Film", ERROR, self._remove_film).pack(side="left", padx=5)
        self._create_btn(top, "↻ Refresh", BG2, self._refresh_films, fg=ACCENT).pack(side="right", padx=5)

        cols = ("ID", "Title", "Genre", "Age Rating", "Duration", "Active")
        self.films_tree = ttk.Treeview(self.tab_films, columns=cols, show="headings", height=15)

        for c in cols:
            self.films_tree.heading(c, text=c)
            self.films_tree.column(c, anchor="center")
        self.films_tree.column("ID", width=50)
        self.films_tree.column("Title", width=250, anchor="w")
        self.films_tree.column("Active", width=80)

        # Scrollbar
        sb = ttk.Scrollbar(self.tab_films, orient="vertical", command=self.films_tree.yview)
        self.films_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.films_tree.pack(fill="both", expand=True, pady=10)

        self._refresh_films()

    def _refresh_films(self):
        for row in self.films_tree.get_children():
            self.films_tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.execute(
                "SELECT film_id, title, genre, age_rating, duration_mins, is_active FROM films ORDER BY title")
            rows = cursor.fetchall()
            print(f"[DEBUG] AdminWindow._refresh_films fetched {len(rows)} rows")
            for row in rows:
                active_str = "Yes" if row["is_active"] else "No"
                self.films_tree.insert("", "end", values=(
                    row["film_id"], row["title"], row["genre"], row["age_rating"],
                    f"{row['duration_mins']}m", active_str
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_add_film(self):
        self._open_film_form("Add Film")

    def _open_edit_film(self):
        sel = self.films_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a film to edit.")
            return
        film_id = self.films_tree.item(sel[0])["values"][0]
        self._open_film_form("Edit Film", film_id)

    def _open_film_form(self, mode, film_id=None):
        win = tk.Toplevel(self.root)
        win.title(mode)
        win.geometry("500x550")
        win.configure(bg=BG)
        win.grab_set()

        fields = [
            ("Title", "entry"),
            ("Genre", "combo", ["Action", "Animation", "Comedy", "Documentary",
             "Drama", "Horror", "Romance", "Sci-Fi", "Thriller"]),
            ("Age Rating", "combo", ["U", "PG", "12", "12A", "15", "18", "R"]),
            ("Duration (mins)", "entry"),
            ("Description", "text"),
            ("Cast Members", "entry"),
            ("Poster Path", "poster"),
        ]

        _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        posters_dir = os.path.join(_project_root, "assets", "posters")

        inputs = {}
        for idx, field in enumerate(fields):
            name, ftype = field[0], field[1]
            tk.Label(win, text=name + ":", bg=BG, fg=TEXT2, font=("Segoe UI", 10)
                     ).grid(row=idx, column=0, pady=10, padx=15, sticky="e")

            if ftype == "poster":
                pf = tk.Frame(win, bg=BG)
                pf.grid(row=idx, column=1, pady=10, padx=10, sticky="w")
                w = tk.Entry(pf, width=34, font=("Segoe UI", 10))
                w.pack(side=tk.LEFT)
                inputs[name] = w

                def browse_poster(fid=film_id):
                    src = filedialog.askopenfilename(
                        parent=win,
                        title="Select poster image",
                        filetypes=[
                            ("Images", "*.png *.jpg *.jpeg *.webp *.gif"),
                            ("All files", "*.*"),
                        ],
                    )
                    if not src:
                        return
                    try:
                        os.makedirs(posters_dir, exist_ok=True)
                        _, ext = os.path.splitext(src)
                        ext = ext.lower() if ext else ".jpg"
                        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                            ext = ".jpg"
                        if fid is not None:
                            dest_name = f"poster_film_{fid}{ext}"
                        else:
                            dest_name = f"poster_{uuid.uuid4().hex[:12]}{ext}"
                        dest_abs = os.path.join(posters_dir, dest_name)
                        shutil.copy2(src, dest_abs)
                        rel = f"assets/posters/{dest_name}"
                        inputs["Poster Path"].delete(0, tk.END)
                        inputs["Poster Path"].insert(0, rel)
                    except OSError as ex:
                        messagebox.showerror("Copy failed", str(ex), parent=win)

                tk.Button(
                    pf,
                    text="Browse…",
                    bg=BG2,
                    fg=FG,
                    command=browse_poster,
                ).pack(side=tk.LEFT, padx=(8, 0))
            elif ftype == "entry":
                w = tk.Entry(win, width=40, font=("Segoe UI", 10))
                w.grid(row=idx, column=1, pady=10, padx=10, sticky="w")
                inputs[name] = w
            elif ftype == "combo":
                w = ttk.Combobox(win, values=field[2], state="readonly", width=37)
                w.grid(row=idx, column=1, pady=10, padx=10, sticky="w")
                if field[2]:
                    w.current(0)
                inputs[name] = w
            elif ftype == "text":
                w = tk.Text(win, width=40, height=4, font=("Segoe UI", 10))
                w.grid(row=idx, column=1, pady=10, padx=10, sticky="w")
                inputs[name] = w

        if film_id:
            try:
                conn = get_connection()
                row = conn.execute("SELECT * FROM films WHERE film_id=?", (film_id,)).fetchone()
                inputs["Title"].insert(0, row["title"])
                inputs["Genre"].set(row["genre"])
                inputs["Age Rating"].set(row["age_rating"])
                inputs["Duration (mins)"].insert(0, str(row["duration_mins"]))
                inputs["Description"].insert("1.0", row["description"] or "")
                inputs["Cast Members"].insert(0, row["cast_members"] or "")
                inputs["Poster Path"].insert(0, row["poster_path"] or "")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                win.destroy()
                return

        def save():
            try:
                from src.utils.input_validator import InputValidator
                t = InputValidator.sanitise_text(inputs["Title"].get(), 100)
                g = inputs["Genre"].get()
                a = inputs["Age Rating"].get()
                d_str = inputs["Duration (mins)"].get().strip()
                d = int(d_str) if d_str.isdigit() else 0
                desc = InputValidator.sanitise_text(inputs["Description"].get("1.0", "end-1c"), 500)
                c = InputValidator.sanitise_text(inputs["Cast Members"].get(), 200)
                p = InputValidator.sanitise_text(inputs["Poster Path"].get(), 200)

                if not t or d <= 0:
                    messagebox.showwarning("Validation Error", "Valid title and duration (>0) are required.")
                    return

                if mode == "Add Film":
                    Film.create(title=t, genre=g, age_rating=a, duration_mins=d,
                                description=desc, cast_members=c, poster_path=p)
                else:
                    Film.update(film_id, title=t, genre=g, age_rating=a, duration_mins=d,
                                description=desc, cast_members=c, poster_path=p)
                win.destroy()
                self._refresh_films()
                messagebox.showinfo("Success", f"Film '{t}' saved.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        self._create_btn(win, "Save Film", SUCCESS, save, fg="#FFFFFF").grid(
            row=len(fields), column=1, pady=20, sticky="e", padx=10)

    def _remove_film(self):
        sel = self.films_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a film to remove.")
            return

        film_id = self.films_tree.item(sel[0])["values"][0]
        title = self.films_tree.item(sel[0])["values"][1]
        active = self.films_tree.item(sel[0])["values"][5]

        if active == "No":
            messagebox.showinfo("Info", "Film is already inactive.")
            return

        if messagebox.askyesno(
                "Confirm Remove",
                f"Are you sure you want to deactivate '{title}'?\n"
                "This will hide it from future listings."):
            try:
                Film.deactivate(film_id)
                self._refresh_films()
                messagebox.showinfo("Success", "Film deactivated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # --- SHOWINGS TAB ---
    def _build_showings_tab(self):
        print("[DEBUG] AdminWindow._build_showings_tab called")
        top = tk.Frame(self.tab_showings, bg=BG, pady=10)
        top.pack(fill="x")

        self._create_btn(top, "+ Add Showing", SUCCESS, self._open_add_showing).pack(side="left", padx=5)
        self._create_btn(top, "✎ Edit Showing", ACCENT, self._open_edit_showing).pack(side="left", padx=5)
        self._create_btn(top, "✕ Cancel Showing", ERROR, self._cancel_showing).pack(side="left", padx=5)
        self._create_btn(top, "↻ Refresh", BG2, self._refresh_showings, fg=ACCENT).pack(side="right", padx=5)

        cols = ("ID", "Film", "Cinema", "Screen", "Date", "Time", "Type", "Seats", "Status")
        self.shows_tree = ttk.Treeview(self.tab_showings, columns=cols, show="headings", height=15)

        for c in cols:
            self.shows_tree.heading(c, text=c)
            self.shows_tree.column(c, width=100, anchor="center")
        self.shows_tree.column("Film", width=220, anchor="w")
        self.shows_tree.column("Cinema", width=150, anchor="w")
        self.shows_tree.column("Screen", width=70)
        self.shows_tree.column("ID", width=50)

        sb = ttk.Scrollbar(self.tab_showings, orient="vertical", command=self.shows_tree.yview)
        self.shows_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.shows_tree.pack(fill="both", expand=True, pady=10)

        self._refresh_showings()

    def _refresh_showings(self):
        for row in self.shows_tree.get_children():
            self.shows_tree.delete(row)
        try:
            conn = get_connection()
            q = '''
                SELECT
                    s.showing_id, f.title, c.cinema_name, s.screen_id,
                    s.show_date, s.show_time, s.show_type,
                    s.seats_remaining, s.is_cancelled
                FROM showings s
                JOIN films f ON s.film_id = f.film_id
                JOIN screens sc ON s.screen_id = sc.screen_id
                JOIN cinemas c ON sc.cinema_id = c.cinema_id
                ORDER BY s.show_date DESC, s.show_time DESC
                LIMIT 200
            '''
            rows = conn.execute(q).fetchall()
            print(f"[DEBUG] AdminWindow._refresh_showings fetched {len(rows)} rows")
            for row in rows:
                status = "Cancelled" if row["is_cancelled"] else "Active"
                self.shows_tree.insert("", "end", values=(
                    row["showing_id"], row["title"], row["cinema_name"],
                    row["screen_id"], row["show_date"], row["show_time"],
                    row["show_type"].capitalize(), row["seats_remaining"], status
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_add_showing(self):
        win = tk.Toplevel(self.root)
        win.title("Add Showing")
        win.geometry("450x450")
        win.configure(bg=BG)
        win.grab_set()

        conn = get_connection()
        films = conn.execute("SELECT film_id, title FROM films WHERE is_active=1 ORDER BY title").fetchall()
        cinemas = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name").fetchall()

        if not films or not cinemas:
            messagebox.showerror("Error", "Need active films and cinemas to create showings.")
            win.destroy()
            return

        tk.Label(win, text="Film:", bg=BG, fg=TEXT2).grid(row=0, column=0, pady=15, padx=15, sticky="e")
        f_cb = ttk.Combobox(win, values=[f"{f['film_id']} - {f['title']}" for f in films], state="readonly", width=35)
        f_cb.grid(row=0, column=1)
        f_cb.current(0)

        tk.Label(win, text="Cinema:", bg=BG, fg=TEXT2).grid(row=1, column=0, pady=15, padx=15, sticky="e")
        c_cb = ttk.Combobox(
            win, values=[f"{c['cinema_id']} - {c['cinema_name']}" for c in cinemas], state="readonly", width=35)
        c_cb.grid(row=1, column=1)
        c_cb.current(0)

        tk.Label(win, text="Screen ID:", bg=BG, fg=TEXT2).grid(row=2, column=0, pady=15, padx=15, sticky="e")
        s_cb = ttk.Combobox(win, state="readonly", width=35)
        s_cb.grid(row=2, column=1)

        def update_screens(*args):
            c_val = c_cb.get()
            if not c_val:
                return
            c_id = int(c_val.split(" - ")[0])
            screens = conn.execute(
                "SELECT screen_id, total_capacity FROM screens WHERE cinema_id=?", (c_id,)).fetchall()
            s_cb['values'] = [f"{s['screen_id']} (Cap: {s['total_capacity']})" for s in screens]
            if screens:
                s_cb.current(0)

        c_cb.bind("<<ComboboxSelected>>", update_screens)
        update_screens()

        tk.Label(win, text="Date (YYYY-MM-DD):", bg=BG, fg=TEXT2).grid(row=3, column=0, pady=15, padx=15, sticky="e")
        d_ent = tk.Entry(win, width=37)
        d_ent.insert(0, datetime.date.today().isoformat())
        d_ent.grid(row=3, column=1)

        tk.Label(win, text="Time:", bg=BG, fg=TEXT2).grid(row=4, column=0, pady=15, padx=15, sticky="e")
        t_cb = ttk.Combobox(win, values=["10:00", "14:30", "19:00"], state="readonly", width=35)
        t_cb.grid(row=4, column=1)
        t_cb.current(0)

        def save():
            try:
                f_id = int(f_cb.get().split(" - ")[0])
                c_id = int(c_cb.get().split(" - ")[0])
                sc_id = int(s_cb.get().split(" ")[0])
                d = d_ent.get().strip()
                t = t_cb.get()

                type_map = {"10:00": "morning", "14:30": "afternoon", "19:00": "evening"}
                stype = type_map.get(t, "evening")

                # Check valid date
                from src.utils.input_validator import InputValidator
                if not InputValidator.validate_date(d):
                    raise ValueError("Invalid date format. Use YYYY-MM-DD.")

                Showing.create(cinema_id=c_id, screen_id=sc_id, film_id=f_id, date=d, show_type=stype)
                win.destroy()
                self._refresh_showings()
                messagebox.showinfo("Success", "Showing created.")
            except ValueError as ve:
                messagebox.showerror("Validation Error", str(ve))
            except Exception as e:
                messagebox.showerror("Error", str(e))

        self._create_btn(win, "Create Showing", SUCCESS, save).grid(row=5, column=1, pady=20, sticky="e")

    def _open_edit_showing(self):
        sel = self.shows_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a showing to edit.")
            return

        sid = self.shows_tree.item(sel[0])["values"][0]

        win = tk.Toplevel(self.root)
        win.title("Edit Showing")
        win.geometry("400x300")
        win.configure(bg=BG)
        win.grab_set()

        try:
            conn = get_connection()
            showing = conn.execute(
                "SELECT screen_id, show_time, show_date FROM showings WHERE showing_id=?", (sid,)).fetchone()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            win.destroy()
            return

        tk.Label(win, text="New Screen ID:", bg=BG, fg=TEXT2).grid(row=0, column=0, pady=15, padx=15, sticky="e")
        s_ent = tk.Entry(win)
        s_ent.insert(0, str(showing["screen_id"]))
        s_ent.grid(row=0, column=1)

        tk.Label(win, text="New Time:", bg=BG, fg=TEXT2).grid(row=1, column=0, pady=15, padx=15, sticky="e")
        t_cb = ttk.Combobox(win, values=["10:00", "14:30", "19:00"], state="readonly", font=("Segoe UI", 10))
        t_cb.set(showing["show_time"])
        t_cb.grid(row=1, column=1)

        def save():
            try:
                new_s = int(s_ent.get().strip())
                new_t = t_cb.get()

                type_map = {"10:00": "morning", "14:30": "afternoon", "19:00": "evening"}
                new_stype = type_map.get(new_t, "evening")

                conn.execute("UPDATE showings SET screen_id=?, show_time=?, show_type=? WHERE showing_id=?",
                             (new_s, new_t, new_stype, sid))
                conn.commit()
                win.destroy()
                self._refresh_showings()
                messagebox.showinfo("Success", "Showing updated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        self._create_btn(win, "Save Changes", SUCCESS, save).grid(row=2, column=1, pady=20, sticky="e")

    def _cancel_showing(self):
        sel = self.shows_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a showing to cancel.")
            return

        sid = self.shows_tree.item(sel[0])["values"][0]
        status = self.shows_tree.item(sel[0])["values"][8]

        if status == "Cancelled":
            messagebox.showinfo("Info", "Showing is already cancelled.")
            return

        if messagebox.askyesno(
                "Confirm Cancel",
                f"Are you sure you want to cancel showing ID {sid}?\n"
                "All active bookings will be cancelled with a 100% refund."):
            try:
                from src.models.cancellation import CancellationManager
                conn = get_connection()
                count = CancellationManager.cancel_showing(sid, conn)
                messagebox.showinfo("Success", f"Showing {sid} cancelled.\n{count} booking(s) affected.")
                self._refresh_showings()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel showing: {e}")

    # --- BOOKINGS TAB ---
    def _build_bookings_tab(self):
        """Display all bookings across the cinema network."""
        top = tk.Frame(self.tab_bookings, bg=BG, pady=10)
        top.pack(fill="x", padx=10)

        tk.Label(top, text="Filter by Status:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left", padx=5)
        self.bookings_status_var = tk.StringVar(value="All")
        status_cb = ttk.Combobox(top, textvariable=self.bookings_status_var,
                                 values=["All", "Active", "Cancelled"], state="readonly", width=15)
        status_cb.pack(side="left", padx=5)
        status_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_bookings())

        self._create_btn(top, "↻ Refresh", BG2, self._refresh_bookings, fg=ACCENT).pack(side="left", padx=5)
        self._create_btn(top, "➕ Create Booking", SUCCESS, self._open_booking).pack(side="left", padx=5)
        self._create_btn(top, "📥 Export CSV", SUCCESS, self._export_bookings_csv).pack(side="right", padx=5)
        self._create_btn(top, "🔍 Details", ACCENT, self._view_booking_details).pack(side="right", padx=5)

        cols = ("ID", "Ref", "Customer", "Film", "Cinema", "Date",
                "Time", "Tickets", "Total (£)", "Status", "Booked By")
        self.bookings_tree = ttk.Treeview(self.tab_bookings, columns=cols, show="headings", height=18)

        for c in cols:
            self.bookings_tree.heading(c, text=c)
            self.bookings_tree.column(c, anchor="center")

        # Set column widths
        self.bookings_tree.column("ID", width=50)
        self.bookings_tree.column("Ref", width=120)
        self.bookings_tree.column("Customer", width=120)
        self.bookings_tree.column("Film", width=150)
        self.bookings_tree.column("Cinema", width=100)
        self.bookings_tree.column("Date", width=90)
        self.bookings_tree.column("Time", width=60)
        self.bookings_tree.column("Tickets", width=60)
        self.bookings_tree.column("Total (£)", width=80)
        self.bookings_tree.column("Status", width=80)
        self.bookings_tree.column("Booked By", width=100)

        # Scrollbar
        sb = ttk.Scrollbar(self.tab_bookings, orient="vertical", command=self.bookings_tree.yview)
        self.bookings_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=10)
        self.bookings_tree.pack(fill="both", expand=True, pady=10, padx=10)

        self._refresh_bookings()

    def _refresh_bookings(self):
        """Populate bookings treeview with all bookings."""
        for row in self.bookings_tree.get_children():
            self.bookings_tree.delete(row)

        try:
            conn = get_connection()
            status_filter = self.bookings_status_var.get()

            # Build query based on status filter
            if status_filter == "All":
                query = """
                    SELECT b.booking_id, b.booking_ref, b.customer_name, f.title, c.cinema_name,
                           sh.show_date, sh.show_time, COUNT(t.ticket_id) as ticket_count,
                           b.total_cost, b.booking_status, u.full_name
                    FROM bookings b
                    JOIN showings sh ON b.showing_id = sh.showing_id
                    JOIN screens sc ON sh.screen_id = sc.screen_id
                    JOIN cinemas c ON sc.cinema_id = c.cinema_id
                    JOIN films f ON sh.film_id = f.film_id
                    JOIN users u ON b.staff_id = u.user_id
                    LEFT JOIN tickets t ON b.booking_id = t.booking_id
                    GROUP BY b.booking_id
                    ORDER BY sh.show_date DESC, sh.show_time DESC
                    LIMIT 500
                """
            else:
                query = """
                    SELECT b.booking_id, b.booking_ref, b.customer_name, f.title, c.cinema_name,
                           sh.show_date, sh.show_time, COUNT(t.ticket_id) as ticket_count,
                           b.total_cost, b.booking_status, u.full_name
                    FROM bookings b
                    JOIN showings sh ON b.showing_id = sh.showing_id
                    JOIN screens sc ON sh.screen_id = sc.screen_id
                    JOIN cinemas c ON sc.cinema_id = c.cinema_id
                    JOIN films f ON sh.film_id = f.film_id
                    JOIN users u ON b.staff_id = u.user_id
                    LEFT JOIN tickets t ON b.booking_id = t.booking_id
                    WHERE b.booking_status = ?
                    GROUP BY b.booking_id
                    ORDER BY sh.show_date DESC, sh.show_time DESC
                    LIMIT 500
                """
                query_params = (status_filter,)

            rows = conn.execute(query, query_params if status_filter != "All" else ()).fetchall()

            for row in rows:
                self.bookings_tree.insert("", "end", values=(
                    row["booking_id"],
                    row["booking_ref"],
                    row["customer_name"][:20] if row["customer_name"] else "N/A",
                    row["title"][:25] if row["title"] else "N/A",
                    row["cinema_name"][:20] if row["cinema_name"] else "N/A",
                    row["show_date"],
                    row["show_time"],
                    row["ticket_count"],
                    f"£{row['total_cost']:.2f}",
                    row["booking_status"],
                    row["full_name"][:15] if row["full_name"] else "N/A"
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load bookings: {e}")

    def _view_booking_details(self):
        """Display details of selected booking."""
        sel = self.bookings_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a booking to view details.")
            return

        booking_id = self.bookings_tree.item(sel[0])["values"][0]

        try:
            conn = get_connection()
            booking = conn.execute("""
                SELECT b.*, sh.show_date, sh.show_time, f.title, c.cinema_name, sc.screen_number
                FROM bookings b
                JOIN showings sh ON b.showing_id = sh.showing_id
                JOIN screens sc ON sh.screen_id = sc.screen_id
                JOIN cinemas c ON sc.cinema_id = c.cinema_id
                JOIN films f ON sh.film_id = f.film_id
                WHERE b.booking_id = ?
            """, (booking_id,)).fetchone()

            if not booking:
                messagebox.showerror("Error", "Booking not found.")
                return

            tickets = conn.execute("""
                SELECT seat_number, ticket_type, unit_price
                FROM tickets
                WHERE booking_id = ?
                ORDER BY seat_number
            """, (booking_id,)).fetchall()

            # Create details window
            win = tk.Toplevel(self.root)
            win.title(f"Booking Details - {booking['booking_ref']}")
            win.geometry("600x500")
            win.configure(bg=BG)

            # Header
            header = tk.Frame(win, bg=BG2, pady=15)
            header.pack(fill="x")
            tk.Label(header, text=f"Booking Ref: {booking['booking_ref']}",
                     font=("Segoe UI", 12, "bold"), bg=BG2, fg=FG).pack(anchor="w", padx=20)

            # Details frame
            details = tk.Frame(win, bg=BG, padx=20, pady=15)
            details.pack(fill="x")

            info_text = f"""
Customer: {booking['customer_name']}
Email: {booking['customer_email'] or 'N/A'}

Film: {booking['title']}
Cinema: {booking['cinema_name']}
Screen: {booking['screen_number']}
Date: {booking['show_date']} at {booking['show_time']}

Total Cost: £{booking['total_cost']:.2f}
Status: {booking['booking_status']}
Booked By Agent: {'Yes' if booking['booked_by_agent'] else 'No'}
            """.strip()

            tk.Label(details, text=info_text, bg=BG, fg=FG, font=("Segoe UI", 10),
                     justify="left", anchor="nw").pack(fill="x")

            # Tickets frame
            tickets_frame = tk.Frame(win, bg=BG2, padx=20, pady=15)
            tickets_frame.pack(fill="x")
            tk.Label(tickets_frame, text="Tickets:", font=("Segoe UI", 11, "bold"),
                     bg=BG2, fg=FG).pack(anchor="w")

            tickets_text = "\n".join([
                f"  • {t['seat_number']:<8} {t['ticket_type']:<15} £{t['unit_price']:.2f}"
                for t in tickets
            ]) or "  No tickets"

            tk.Label(tickets_frame, text=tickets_text, bg=BG2, fg=TEXT2, font=("Courier", 9),
                     justify="left", anchor="nw").pack(fill="x", pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load booking details: {e}")

    def _export_bookings_csv(self):
        """Export all bookings to CSV."""
        try:
            conn = get_connection()
            status_filter = self.bookings_status_var.get()

            if status_filter == "All":
                rows = conn.execute("""
                    SELECT b.booking_id, b.booking_ref, b.customer_name, f.title, c.cinema_name,
                           sh.show_date, sh.show_time, COUNT(t.ticket_id) as ticket_count,
                           b.total_cost, b.booking_status, u.full_name
                    FROM bookings b
                    JOIN showings sh ON b.showing_id = sh.showing_id
                    JOIN screens sc ON sh.screen_id = sc.screen_id
                    JOIN cinemas c ON sc.cinema_id = c.cinema_id
                    JOIN films f ON sh.film_id = f.film_id
                    JOIN users u ON b.staff_id = u.user_id
                    LEFT JOIN tickets t ON b.booking_id = t.booking_id
                    GROUP BY b.booking_id
                    ORDER BY sh.show_date DESC
                """).fetchall()
            else:
                rows = conn.execute("""
                    SELECT b.booking_id, b.booking_ref, b.customer_name, f.title, c.cinema_name,
                           sh.show_date, sh.show_time, COUNT(t.ticket_id) as ticket_count,
                           b.total_cost, b.booking_status, u.full_name
                    FROM bookings b
                    JOIN showings sh ON b.showing_id = sh.showing_id
                    JOIN screens sc ON sh.screen_id = sc.screen_id
                    JOIN cinemas c ON sc.cinema_id = c.cinema_id
                    JOIN films f ON sh.film_id = f.film_id
                    JOIN users u ON b.staff_id = u.user_id
                    LEFT JOIN tickets t ON b.booking_id = t.booking_id
                    WHERE b.booking_status = ?
                    GROUP BY b.booking_id
                    ORDER BY sh.show_date DESC
                """, (status_filter,)).fetchall()

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"bookings_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            if not filepath:
                return

            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ["Booking ID", "Ref", "Customer", "Film", "Cinema", "Date", "Time",
                              "Tickets", "Total (£)", "Status", "Booked By"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in rows:
                    writer.writerow({
                        "Booking ID": row["booking_id"],
                        "Ref": row["booking_ref"],
                        "Customer": row["customer_name"],
                        "Film": row["title"],
                        "Cinema": row["cinema_name"],
                        "Date": row["show_date"],
                        "Time": row["show_time"],
                        "Tickets": row["ticket_count"],
                        "Total (£)": f"£{row['total_cost']:.2f}",
                        "Status": row["booking_status"],
                        "Booked By": row["full_name"]
                    })

            messagebox.showinfo("Success", f"Bookings exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export bookings: {e}")

    # --- CREATE BOOKING TAB ---
    def _build_create_booking_tab(self):
        """Admin interface to create bookings for any cinema."""
        # --- Left Panel: Selection and Entry ---
        left_panel = tk.Frame(self.tab_create_booking, bg=BG, width=400)
        left_panel.pack(side="left", fill="both", padx=15, pady=15)

        # Cinema selection
        tk.Label(left_panel, text="Select Cinema:", bg=BG, fg=FG, font=(
            "Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_cinema_var = tk.StringVar()
        self.cb_cinema_cb = ttk.Combobox(left_panel, textvariable=self.cb_cinema_var,
                                         state="readonly", font=("Segoe UI", 10))
        self.cb_cinema_cb.pack(fill="x", pady=(0, 15))
        self.cb_cinema_cb.bind("<<ComboboxSelected>>", lambda e: self._update_cb_dates())

        # Date selection
        tk.Label(left_panel, text="Select Date:", bg=BG, fg=FG, font=(
            "Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_date_var = tk.StringVar()
        self.cb_date_cb = ttk.Combobox(left_panel, textvariable=self.cb_date_var,
                                       state="readonly", font=("Segoe UI", 10))
        self.cb_date_cb.pack(fill="x", pady=(0, 15))
        self.cb_date_cb.bind("<<ComboboxSelected>>", lambda e: self._update_cb_showings())

        # Showing selection
        tk.Label(left_panel, text="Select Showing:", bg=BG, fg=FG, font=(
            "Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_showing_var = tk.StringVar()
        self.cb_showing_cb = ttk.Combobox(left_panel, textvariable=self.cb_showing_var,
                                          state="readonly", font=("Segoe UI", 10))
        self.cb_showing_cb.pack(fill="x", pady=(0, 15))
        self.cb_showing_cb.bind("<<ComboboxSelected>>", lambda e: self._update_cb_available_seats())

        # Customer info
        tk.Label(left_panel, text="Customer Name:", bg=BG, fg=FG, font=(
            "Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_customer_name = tk.Entry(left_panel, font=("Segoe UI", 10))
        self.cb_customer_name.pack(fill="x", pady=(0, 15))

        tk.Label(left_panel, text="Customer Email:", bg=BG, fg=FG, font=(
            "Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_customer_email = tk.Entry(left_panel, font=("Segoe UI", 10))
        self.cb_customer_email.pack(fill="x", pady=(0, 15))

        # Ticket count
        tk.Label(left_panel, text="Number of Tickets:", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_ticket_count = ttk.Spinbox(left_panel, from_=1, to=20, font=("Segoe UI", 10))
        self.cb_ticket_count.set(1)
        self.cb_ticket_count.pack(fill="x", pady=(0, 15))
        self.cb_ticket_count.bind("<<Change>>", lambda e: self._update_cb_available_seats())

        # Seat selection
        tk.Label(left_panel, text="Select Seats (Available):", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.cb_seats_var = tk.StringVar()
        self.cb_seats_text = tk.Text(left_panel, height=6, font=("Courier", 9), bg=BG2, fg=FG)
        self.cb_seats_text.pack(fill="x", pady=(0, 15))

        tk.Label(left_panel, text="Enter seat numbers (e.g., A1,A2,B1):", bg=BG,
                 fg=TEXT2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        self.cb_selected_seats = tk.Entry(left_panel, font=("Segoe UI", 10))
        self.cb_selected_seats.pack(fill="x", pady=(0, 20))

        # Create booking button
        self._create_btn(left_panel, "✓ Create Booking", SUCCESS, self._create_booking_action).pack(fill="x", pady=10)

        # Load cinemas
        self._load_cb_cinemas()

    def _load_cb_cinemas(self):
        """Load all cinemas into dropdown."""
        try:
            conn = get_connection()
            cinemas = conn.execute("SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name").fetchall()
            cinema_opts = [f"{c['cinema_id']} - {c['cinema_name']}" for c in cinemas]
            self.cb_cinema_cb['values'] = cinema_opts
            if cinema_opts:
                self.cb_cinema_cb.current(0)
                self._update_cb_dates()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load cinemas: {e}")

    def _update_cb_dates(self):
        """Update dates based on selected cinema."""
        cinema_str = self.cb_cinema_var.get()
        if not cinema_str:
            return

        try:
            cinema_id = int(cinema_str.split(" - ")[0])
            conn = get_connection()

            # Get distinct dates for this cinema with showings in the future (and today)
            today = datetime.date.today().isoformat()
            dates = conn.execute("""
                SELECT DISTINCT sh.show_date
                FROM showings sh
                JOIN screens sc ON sh.screen_id = sc.screen_id
                WHERE sc.cinema_id = ? AND sh.show_date >= ?
                ORDER BY sh.show_date
                LIMIT 30
            """, (cinema_id, today)).fetchall()

            date_opts = [d['show_date'] for d in dates]
            self.cb_date_cb['values'] = date_opts
            if date_opts:
                self.cb_date_cb.current(0)
                self._update_cb_showings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load dates: {e}")

    def _update_cb_showings(self):
        """Update showings based on cinema and date."""
        cinema_str = self.cb_cinema_var.get()
        date_str = self.cb_date_var.get()

        if not cinema_str or not date_str:
            return

        try:
            cinema_id = int(cinema_str.split(" - ")[0])
            conn = get_connection()

            showings = conn.execute("""
                SELECT sh.showing_id, f.title, sh.show_time, sh.show_type, sh.seats_remaining
                FROM showings sh
                JOIN screens sc ON sh.screen_id = sc.screen_id
                JOIN films f ON sh.film_id = f.film_id
                WHERE sc.cinema_id = ? AND sh.show_date = ?
                ORDER BY sh.show_time
            """, (cinema_id, date_str)).fetchall()

            showing_opts = [
                f"{s['showing_id']} - {s['title'][:30]} {s['show_time']} "
                f"({s['show_type']}) - {s['seats_remaining']} seats"
                for s in showings
            ]
            self.cb_showing_cb['values'] = showing_opts
            if showing_opts:
                self.cb_showing_cb.current(0)
                self._update_cb_available_seats()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load showings: {e}")

    def _update_cb_available_seats(self):
        """Display available seats for the selected showing."""
        showing_str = self.cb_showing_var.get()
        if not showing_str:
            self.cb_seats_text.delete("1.0", tk.END)
            return

        try:
            showing_id = int(showing_str.split(" - ")[0])

            conn = get_connection()

            # Get booked seats
            booked = conn.execute("""
                SELECT seat_number FROM tickets
                WHERE booking_id IN (
                    SELECT booking_id FROM bookings
                    WHERE showing_id = ? AND booking_status != 'Cancelled'
                )
            """, (showing_id,)).fetchall()

            booked_seats = {b['seat_number'] for b in booked}

            # Get screen capacity
            screen = conn.execute("""
                SELECT s.total_capacity FROM screens s
                JOIN showings sh ON sh.screen_id = s.screen_id
                WHERE sh.showing_id = ?
            """, (showing_id,)).fetchone()

            if not screen:
                self.cb_seats_text.delete("1.0", tk.END)
                return

            capacity = screen['total_capacity']

            # Generate available seats (simple A1, A2, ... format)
            all_seats = []
            for i in range(capacity):
                row = chr(65 + (i // 10))  # A, B, C, ...
                col = (i % 10) + 1
                seat = f"{row}{col}"
                all_seats.append(seat)

            available = [s for s in all_seats if s not in booked_seats]

            # Display available seats (first 40 shown)
            seat_display = "Available: " + ", ".join(available[:40])
            if len(available) > 40:
                seat_display += f"\n... and {len(available) - 40} more"

            self.cb_seats_text.delete("1.0", tk.END)
            self.cb_seats_text.insert("1.0", seat_display)

        except Exception as e:
            self.cb_seats_text.delete("1.0", tk.END)
            self.cb_seats_text.insert("1.0", f"Error: {e}")

    def _create_booking_action(self):
        """Create booking with entered details."""
        cinema_str = self.cb_cinema_var.get()
        showing_str = self.cb_showing_var.get()
        customer_name = self.cb_customer_name.get().strip()
        customer_email = self.cb_customer_email.get().strip()
        seats_str = self.cb_selected_seats.get().strip()

        if not all([cinema_str, showing_str, customer_name, seats_str]):
            messagebox.showwarning("Validation", "Please fill in all required fields and select seats.")
            return

        from src.utils.input_validator import InputValidator
        if customer_email and not InputValidator.validate_email(customer_email):
            messagebox.showwarning("Invalid Input", "Please enter a valid email address.")
            return

        try:
            showing_id = int(showing_str.split(" - ")[0])
            seats = [s.strip().upper() for s in seats_str.split(",")]

            if len(seats) == 0:
                messagebox.showwarning("Validation", "Please enter at least one seat.")
                return

            conn = get_connection()

            # Validate seats exist and are available
            booked = conn.execute("""
                SELECT seat_number FROM tickets
                WHERE booking_id IN (
                    SELECT booking_id FROM bookings
                    WHERE showing_id = ? AND booking_status != 'Cancelled'
                )
            """, (showing_id,)).fetchall()

            booked_seats = {b['seat_number'] for b in booked}

            for seat in seats:
                if seat in booked_seats:
                    messagebox.showerror("Error", f"Seat {seat} is already booked.")
                    return

            # Get showing details for pricing
            showing = conn.execute("""
                SELECT sh.film_id, sh.screen_id, sh.show_date, sh.show_time, sh.show_type, f.title
                FROM showings sh
                JOIN films f ON sh.film_id = f.film_id
                WHERE sh.showing_id = ?
            """, (showing_id,)).fetchone()

            # Get price
            screen = conn.execute("""
                SELECT cinema_id FROM screens WHERE screen_id = ?
            """, (showing['screen_id'],)).fetchone()

            cinema = conn.execute("""
                SELECT city_id FROM cinemas WHERE cinema_id = ?
            """, (screen['cinema_id'],)).fetchone()

            price = conn.execute("""
                SELECT lower_hall_price FROM prices
                WHERE city_id = ? AND show_type = ?
                ORDER BY effective_from DESC LIMIT 1
            """, (cinema['city_id'], showing['show_type'])).fetchone()

            unit_price = price['lower_hall_price'] if price else 5.0
            total_cost = unit_price * len(seats)

            # Validate date and time
            from src.models.booking import BookingManager, BookingError
            try:
                BookingManager.validate_booking_date(showing['show_date'], showing['show_time'])
            except BookingError as e:
                messagebox.showerror("Validation Error", str(e))
                return

            # Create booking reference
            date_part = datetime.date.today().isoformat().replace("-", "")
            time_part = datetime.datetime.now().strftime("%H%M%S")
            booking_ref = f"HCBS-{date_part}-{time_part}"

            # Insert booking
            conn.execute("""
                INSERT INTO bookings
                (
                    showing_id, booking_ref, customer_name, customer_email,
                    total_cost, booking_status, booked_by_agent, staff_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                showing_id, booking_ref, customer_name, customer_email,
                total_cost, "Active", 1, self.user.user_id
            ))

            booking_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']

            # Insert tickets
            for seat in seats:
                conn.execute("""
                    INSERT INTO tickets (booking_id, seat_number, ticket_type, unit_price)
                    VALUES (?, ?, ?, ?)
                """, (booking_id, seat, "lower_hall", unit_price))

            # Update seats_remaining
            conn.execute("""
                UPDATE showings
                SET seats_remaining = seats_remaining - ?
                WHERE showing_id = ?
            """, (len(seats), showing_id))

            conn.commit()

            messagebox.showinfo("Success",
                                f"Booking created!\n\n"
                                f"Booking Ref: {booking_ref}\n"
                                f"Customer: {customer_name}\n"
                                f"Film: {showing['title']}\n"
                                f"Seats: {', '.join(seats)}\n"
                                f"Total: £{total_cost:.2f}")

            # Clear form
            self.cb_customer_name.delete(0, tk.END)
            self.cb_customer_email.delete(0, tk.END)
            self.cb_selected_seats.delete(0, tk.END)
            self.cb_ticket_count.set(1)
            self._refresh_bookings()  # Refresh bookings tab

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create booking: {e}")

    # --- MONTHLY REVENUE TAB ---
    def _build_revenue_tab(self):
        try:
            from src.gui.revenue_report_window import RevenueReportPanel
            self.revenue_panel = RevenueReportPanel(self.tab_revenue)
        except Exception as e:
            tk.Label(self.tab_revenue, text=f"Error loading Revenue Report Panel:\n{e}", fg="red", bg=BG).pack(pady=20)

    # --- HEATMAP TAB ---
    def _build_heatmap_tab(self):
        try:
            from src.gui.occupancy_heatmap_window import OccupancyHeatmapPanel
            self.heatmap_panel = OccupancyHeatmapPanel(self.tab_heatmap)
        except Exception as e:
            tk.Label(self.tab_heatmap,
                     text=f"Error loading Occupancy Heatmap Panel:\n{e}", fg="red", bg=BG).pack(pady=20)

    # --- STAFF LEADERBOARD TAB ---
    def _build_leaderboard_tab(self):
        try:
            from src.gui.staff_leaderboard_window import StaffLeaderboardPanel
            self.leaderboard_panel = StaffLeaderboardPanel(self.tab_leaderboard)
        except Exception as e:
            tk.Label(self.tab_leaderboard,
                     text=f"Error loading Staff Leaderboard Panel:\n{e}", fg="red", bg=BG).pack(pady=20)

    # --- REVENUE CHART TAB ---
    def _build_chart_tab(self):
        """Embedded horizontal bar chart: Top 10 films by revenue."""
        # ── Controls row ──────────────────────────────────────────────────
        ctrl = tk.Frame(self.tab_chart, bg=BG2, pady=12, padx=16)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Time Period:", bg=BG2, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 8))

        self._chart_period = tk.StringVar(value="month")
        for label, val in [("This Week", "week"), ("This Month", "month"), ("All Time", "all")]:
            tk.Radiobutton(
                ctrl, text=label, variable=self._chart_period, value=val,
                bg=BG2, fg=FG, selectcolor=ACCENT, activebackground=BG2,
                activeforeground=FG, font=("Segoe UI", 10),
                command=self._refresh_revenue_chart
            ).pack(side="left", padx=4)

        tk.Label(ctrl, text="Cinema:", bg=BG2, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(20, 6))
        self._chart_cinema_var = tk.StringVar()
        self._chart_cinema_cb = ttk.Combobox(
            ctrl, textvariable=self._chart_cinema_var,
            state="readonly", font=("Segoe UI", 10), width=22
        )
        self._chart_cinema_cb.pack(side="left")
        self._chart_cinema_cb.bind("<<ComboboxSelected>>",
                                   lambda e: self._refresh_revenue_chart())

        tk.Button(
            ctrl, text="📥 Export CSV", bg=SUCCESS, fg=FG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=self._export_chart_csv
        ).pack(side="right", padx=8)

        tk.Button(
            ctrl, text="↻ Refresh", bg=BG, fg=FG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=self._refresh_revenue_chart
        ).pack(side="right", padx=4)

        # ── Matplotlib canvas ─────────────────────────────────────────────
        chart_frame = tk.Frame(self.tab_chart, bg=BG)
        chart_frame.pack(fill="both", expand=True, padx=16, pady=12)

        self._rev_figure = Figure(figsize=(9, 5.5), dpi=144, facecolor=BG)
        self._rev_ax = self._rev_figure.add_subplot(111)
        self._rev_ax.set_facecolor(BG2)

        self._rev_canvas = FigureCanvasTkAgg(self._rev_figure, master=chart_frame)
        self._rev_canvas.get_tk_widget().pack(fill="both", expand=True)

        # ── Status label ──────────────────────────────────────────────────
        self._chart_status = tk.Label(
            self.tab_chart, text="", bg=BG, fg="#a7b4c8", font=("Segoe UI", 9)
        )
        self._chart_status.pack(anchor="e", padx=16, pady=(0, 6))

        # Initialise cinema dropdown then draw first chart
        self._chart_cinemas = {}   # name -> id
        self._chart_data = []      # list of dicts for CSV export
        self._load_chart_cinemas()

    def _load_chart_cinemas(self):
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT cinema_id, cinema_name FROM cinemas ORDER BY cinema_name"
            ).fetchall()
            self._chart_cinemas = {r['cinema_name']: r['cinema_id'] for r in rows}
            opts = ["All Cinemas"] + list(self._chart_cinemas.keys())
            self._chart_cinema_cb['values'] = opts
            self._chart_cinema_cb.current(0)
        except Exception as e:
            print("Chart cinema load error:", e)
        finally:
            self._refresh_revenue_chart()

    def _refresh_revenue_chart(self):
        today = datetime.date.today()
        period = self._chart_period.get()

        if period == "week":
            since = (today - datetime.timedelta(days=7)).isoformat()
            until = today.isoformat()
            period_label = "This Week"
        elif period == "month":
            since = today.replace(day=1).isoformat()
            until = today.isoformat()
            period_label = "This Month"
        else:
            since = "2000-01-01"
            until = today.isoformat()
            period_label = "All Time"

        cinema_name = self._chart_cinema_var.get()
        cinema_id = self._chart_cinemas.get(cinema_name)  # None = all

        try:
            conn = get_connection()

            cinema_filter = " AND sc.cinema_id = ? " if cinema_id else ""
            params = [since, until]
            if cinema_id:
                params.append(cinema_id)

            query = f"""
                SELECT f.title AS film_title,
                       COUNT(b.booking_id) AS booking_count,
                       IFNULL(SUM(b.total_cost), 0) AS total_revenue
                FROM bookings b
                JOIN showings sh  ON b.showing_id  = sh.showing_id
                JOIN screens  sc  ON sh.screen_id  = sc.screen_id
                JOIN films    f   ON sh.film_id     = f.film_id
                WHERE sh.show_date BETWEEN ? AND ?
                  AND b.booking_status != 'Cancelled'
                  {cinema_filter}
                GROUP BY f.film_id
                ORDER BY total_revenue DESC
                LIMIT 10
            """
            rows = conn.execute(query, params).fetchall()
            self._chart_data = [
                {"film_title": r["film_title"],
                 "total_revenue": r["total_revenue"],
                 "booking_count": r["booking_count"]}
                for r in rows
            ]
        except Exception as e:
            messagebox.showerror("Chart Error", f"Failed to load revenue data:\n{e}")
            return

        # ── Draw chart ────────────────────────────────────────────────────
        ax = self._rev_ax
        ax.clear()
        ax.set_facecolor(BG2)
        self._rev_figure.set_facecolor(BG)

        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.tick_params(colors=TEXT2)
        ax.xaxis.label.set_color(TEXT2)
        ax.yaxis.label.set_color(TEXT2)

        if not self._chart_data:
            ax.text(0.5, 0.5, "No revenue data for this period.",
                    ha="center", va="center", color=TEXT2,
                    fontsize=12, transform=ax.transAxes)
        else:
            titles = [d["film_title"] for d in self._chart_data]
            revenues = [d["total_revenue"] for d in self._chart_data]

            # Horizontal bars — longest bar at top
            titles = titles[::-1]
            revenues = revenues[::-1]

            bars = ax.barh(titles, revenues, color=ACCENT, height=0.55)

            # Value labels
            for bar, val in zip(bars, revenues):
                ax.text(
                    bar.get_width() + max(revenues) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"£{val:,.0f}",
                    va="center", ha="left",
                    color=FG, fontsize=9
                )

            ax.set_xlabel("Revenue (£)", color=TEXT2)
            ax.xaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, _: f"£{x:,.0f}")
            )
            ax.tick_params(axis="y", labelsize=9, colors=FG)
            ax.tick_params(axis="x", labelsize=8, colors=TEXT2)

        cinema_label = cinema_name if cinema_name and cinema_name != "All Cinemas" else "All Cinemas"
        ax.set_title(
            f"Top 10 Films by Revenue — {period_label} · {cinema_label}",
            color=FG, fontsize=11, pad=10
        )

        self._rev_figure.tight_layout()
        self._rev_canvas.draw()
        self._chart_status.config(
            text=f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}  |  "
            f"{len(self._chart_data)} film(s) found"
        )

    def _export_chart_csv(self):
        if not self._chart_data:
            messagebox.showwarning("No Data", "Generate the chart first before exporting.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"revenue_chart_{datetime.date.today().isoformat()}.csv"
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["film_title", "total_revenue", "booking_count"]
                )
                writer.writeheader()
                writer.writerows(self._chart_data)
            messagebox.showinfo("Export Successful", f"Saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save CSV:\n{e}")

    # --- REPORTS TAB ---
    def _build_reports_tab(self):
        top = tk.Frame(self.tab_reports, bg=BG, pady=15)
        top.pack(fill="x")

        tk.Label(top, text="Select Report:", bg=BG, fg=TEXT2, font=("Segoe UI", 11)).pack(side="left", padx=10)

        self.report_var = tk.StringVar(value="Bookings per Listing")
        rep_cb = ttk.Combobox(top, textvariable=self.report_var, values=[
            "Bookings per Listing",
            "Monthly Revenue",
            "Top Revenue Film",
            "Staff Leaderboard"
        ], state="readonly", width=30, font=("Segoe UI", 11))
        rep_cb.pack(side="left", padx=5)

        self._create_btn(top, "📊 Generate", ACCENT, self._generate_report).pack(side="left", padx=15)
        self._create_btn(top, "📥 CSV Export", SUCCESS, self._export_csv).pack(side="right", padx=15)

        self.rep_tree = ttk.Treeview(self.tab_reports, show="headings", height=20)

        sb = ttk.Scrollbar(self.tab_reports, orient="vertical", command=self.rep_tree.yview)
        self.rep_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.rep_tree.pack(fill="both", expand=True, pady=10)

    def _generate_report(self):
        rtype = self.report_var.get()
        conn = get_connection()
        for row in self.rep_tree.get_children():
            self.rep_tree.delete(row)

        try:
            from src.models.reports import ReportManager
            cinema_id = self.user.cinema_id or 1  # Fallback to 1 if admin has no cinema assigned

            # Using current month/year for those that require it
            now = datetime.datetime.now()
            y, m = now.year, now.month

            data = []

            if rtype == "Bookings per Listing":
                cols = ("Film Title", "Date", "Time", "Active Bookings", "Total Revenue (£)")
                self.rep_tree["columns"] = cols
                for c in cols:
                    self.rep_tree.heading(c, text=c)
                    self.rep_tree.column(c, width=150, anchor="center")

                raw_data = ReportManager.bookings_per_listing(cinema_id, conn)
                for r in raw_data:
                    self.rep_tree.insert("", "end", values=(
                        r["film_title"], r["show_date"], r["show_time"],
                        r["total_bookings"], f"£{r['total_revenue']:.2f}"
                    ))
                data = raw_data

            elif rtype == "Monthly Revenue":
                cols = ("Total Bookings", "Total Revenue (£)", "Avg Occupancy (%)",
                        "Morning Revenue (£)", "Afternoon Revenue (£)", "Evening Revenue (£)")
                self.rep_tree["columns"] = cols
                for c in cols:
                    self.rep_tree.heading(c, text=c)
                    self.rep_tree.column(c, width=150, anchor="center")

                stats = ReportManager.monthly_revenue(cinema_id, y, m, conn)
                self.rep_tree.insert("", "end", values=(
                    stats["total_bookings"],
                    f"£{stats['total_revenue']:.2f}",
                    f"{stats['average_occupancy_percent']:.1f}%",
                    f"£{stats['revenue_by_show_type'].get('morning', 0):.2f}",
                    f"£{stats['revenue_by_show_type'].get('afternoon', 0):.2f}",
                    f"£{stats['revenue_by_show_type'].get('evening', 0):.2f}"
                ))
                data = [stats]

            elif rtype == "Top Revenue Film":
                cols = ("Film Title", "Active Bookings", "Total Revenue (£)")
                self.rep_tree["columns"] = cols
                for c in cols:
                    self.rep_tree.heading(c, text=c)
                    self.rep_tree.column(c, width=150, anchor="center")

                raw_data = ReportManager.top_revenue_films(cinema_id, 10, conn)
                for r in raw_data:
                    self.rep_tree.insert("", "end", values=(
                        r["film_title"], r["total_bookings"], f"£{r['total_revenue']:.2f}"))
                data = raw_data

            elif rtype == "Staff Leaderboard":
                cols = ("Rank", "Staff Name", "Active Bookings", "Total Revenue (£)")
                self.rep_tree["columns"] = cols
                for c in cols:
                    self.rep_tree.heading(c, text=c)
                    self.rep_tree.column(c, width=150, anchor="center")

                raw_data = ReportManager.staff_booking_leaderboard(cinema_id, y, m, conn)
                for r in raw_data:
                    self.rep_tree.insert("", "end", values=(
                        r["rank"], r["staff_full_name"], r["total_bookings"], f"£{r['total_revenue']:.2f}"))
                data = raw_data

            self.current_report_data = data

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def _export_csv(self):
        if not hasattr(self, 'current_report_data') or not self.current_report_data:
            messagebox.showwarning("Warning", "No data to export. Generate a report first.")
            return

        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[(
            "CSV files", "*.csv")], initialfile=f"report_{datetime.datetime.now().strftime('%Y%m%d')}.csv")
        if not f:
            return

        try:
            from src.models.reports import ReportManager
            filepath = ReportManager.export_to_csv(self.current_report_data, os.path.basename(f))
            # Move the generated file to the user's chosen location if they picked somewhere else,
            # since ReportManager forces it into 'exports/' folder.
            import shutil
            if os.path.abspath(f) != os.path.abspath(filepath):
                shutil.copy2(filepath, f)
            messagebox.showinfo("Success", f"Export successful!\nSaved to {f}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")

    def _open_cancellation(self):
        try:
            from src.gui.cancellation_window import CancellationWindow
            CancellationWindow(tk.Toplevel(self.root))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open cancellation window: {e}")

    def _open_dashboard(self):
        try:
            from src.gui.dashboard_window import DashboardWindow
            DashboardWindow(tk.Toplevel(self.root))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open dashboard: {e}")

    def _logout(self):
        from src.gui.login_window import _logout_and_return
        _logout_and_return(self.root)

    def _open_booking(self):
        """Open the full staff booking window (skips payment for admins)."""
        try:
            from src.gui.booking_window import BookingWindow
            BookingWindow(tk.Toplevel(self.root))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open booking window: {e}")

    def _build_waitlist_tab(self):
        top = tk.Frame(self.tab_waitlist, bg=BG, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Showing ID:", bg=BG, fg=FG).pack(side="left", padx=5)
        self.waitlist_showing_ent = tk.Entry(top, font=("Segoe UI", 11), width=10)
        self.waitlist_showing_ent.pack(side="left", padx=5)

        tk.Button(top, text="🔍 Load", bg=ACCENT, fg=FG, command=self._refresh_waitlist).pack(side="left", padx=5)
        tk.Button(top, text="✅ Promote", bg=SUCCESS, fg=FG, command=self._promote_waitlist).pack(side="right", padx=5)
        tk.Button(top, text="✕ Remove", bg=WARNING, fg="#000", command=self._remove_waitlist).pack(side="right", padx=5)

        cols = ("ID", "Customer", "Email", "Phone", "Tickets", "Status", "Joined")
        self.waitlist_tree = ttk.Treeview(self.tab_waitlist, columns=cols, show="headings", height=15)

        for c in cols:
            self.waitlist_tree.heading(c, text=c)
            self.waitlist_tree.column(c, anchor="center")
        self.waitlist_tree.column("Customer", width=150, anchor="w")
        self.waitlist_tree.column("Email", width=150, anchor="w")
        self.waitlist_tree.column("Joined", width=150)

        sb = ttk.Scrollbar(self.tab_waitlist, orient="vertical", command=self.waitlist_tree.yview)
        self.waitlist_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.waitlist_tree.pack(fill="both", expand=True, pady=10)

    def _refresh_waitlist(self):
        for row in self.waitlist_tree.get_children():
            self.waitlist_tree.delete(row)

        sh_id = self.waitlist_showing_ent.get().strip()
        if not sh_id.isdigit():
            return

        try:
            conn = get_connection()
            cursor = conn.execute("SELECT * FROM waitlist WHERE showing_id = ? ORDER BY joined_at ASC", (sh_id,))
            for r in cursor.fetchall():
                self.waitlist_tree.insert("", "end", values=(
                    r["waitlist_id"], r["customer_name"], r["customer_email"],
                    r["customer_phone"], r["num_tickets"], r["status"], r["joined_at"]
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _promote_waitlist(self):
        sel = self.waitlist_tree.selection()
        if not sel:
            return
        w_id = self.waitlist_tree.item(sel[0])["values"][0]
        import datetime
        try:
            conn = get_connection()
            conn.execute("UPDATE waitlist SET status = 'offered', offered_at = ? WHERE waitlist_id = ?",
                         (datetime.datetime.now().isoformat(), w_id))
            conn.commit()
            self._refresh_waitlist()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _remove_waitlist(self):
        sel = self.waitlist_tree.selection()
        if not sel:
            return
        w_id = self.waitlist_tree.item(sel[0])["values"][0]
        try:
            conn = get_connection()
            conn.execute("DELETE FROM waitlist WHERE waitlist_id = ?", (w_id,))
            conn.commit()
            self._refresh_waitlist()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # --- CUSTOMERS TAB ---
    def _build_customers_tab(self):
        """Display unique customers aggregated from bookings,
        with email, phone (from waitlist where available), loyalty points,
        booking count and total spend."""
        # ── Controls bar ──────────────────────────────────────────────────
        top = tk.Frame(self.tab_customers, bg=BG, pady=10)
        top.pack(fill="x", padx=10)

        tk.Label(top, text="Search:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(5, 3))
        self._cust_search_var = tk.StringVar()
        search_entry = tk.Entry(
            top, textvariable=self._cust_search_var,
            font=("Segoe UI", 10), bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", bd=4, width=28
        )
        search_entry.pack(side="left", padx=4)
        search_entry.bind("<KeyRelease>", lambda e: self._refresh_customers())

        self._create_btn(top, "↻ Refresh", BG2, self._refresh_customers, fg=ACCENT).pack(side="left", padx=8)

        self._create_btn(top, "📥 Export CSV", SUCCESS, self._export_customers_csv).pack(side="right", padx=5)

        # ── Summary label ─────────────────────────────────────────────────
        self._cust_summary = tk.Label(
            self.tab_customers, text="", bg=BG, fg=TEXT2, font=("Segoe UI", 9)
        )
        self._cust_summary.pack(anchor="e", padx=16)

        # ── Treeview ──────────────────────────────────────────────────────
        cols = ("Customer Name", "Email", "Phone",
                "Loyalty Points", "Bookings", "Total Spent (£)")
        self.customers_tree = ttk.Treeview(
            self.tab_customers, columns=cols, show="headings", height=20
        )

        col_widths = {
            "Customer Name": 180,
            "Email": 210,
            "Phone": 130,
            "Loyalty Points": 110,
            "Bookings": 80,
            "Total Spent (£)": 110,
        }
        for c in cols:
            self.customers_tree.heading(
                c, text=c,
                command=lambda _c=c: self._sort_customers(_c)
            )
            self.customers_tree.column(
                c, width=col_widths.get(c, 120), anchor="center"
            )
        self.customers_tree.column("Customer Name", anchor="w")
        self.customers_tree.column("Email", anchor="w")

        sb = ttk.Scrollbar(
            self.tab_customers, orient="vertical",
            command=self.customers_tree.yview
        )
        self.customers_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 10))
        self.customers_tree.pack(fill="both", expand=True, pady=10, padx=10)

        # Sort state
        self._cust_sort_col = None
        self._cust_sort_asc = True
        self._cust_data = []   # cache for CSV export

        self._refresh_customers()

    def _fetch_customers(self, search=""):
        """Query the DB and return a list of dicts for each unique customer."""
        conn = get_connection()

        # Unique customers from bookings joined with loyalty points
        rows = conn.execute("""
            SELECT
                b.customer_name,
                b.customer_email,
                COALESCE(lp.points, 0)          AS loyalty_points,
                COUNT(b.booking_id)             AS booking_count,
                COALESCE(SUM(b.total_cost), 0)  AS total_spent
            FROM bookings b
            LEFT JOIN loyalty_points lp
                   ON LOWER(lp.customer_name) = LOWER(b.customer_name)
            WHERE b.booking_status != 'Cancelled'
            GROUP BY LOWER(b.customer_name)
            ORDER BY b.customer_name ASC
        """).fetchall()

        # Phone lookup from waitlist contact_info (numeric-looking entries only)
        phone_map = {}
        for wl in conn.execute(
            "SELECT customer_name, contact_info FROM waitlist"
        ).fetchall():
            info = wl["contact_info"] or ""
            if any(ch.isdigit() for ch in info) and "@" not in info:
                phone_map.setdefault(wl["customer_name"].lower(), info)

        result = []
        search_lower = search.lower()
        for row in rows:
            name = row["customer_name"] or ""
            email = row["customer_email"] or "N/A"
            phone = phone_map.get(name.lower(), "N/A")
            pts = row["loyalty_points"]
            bks = row["booking_count"]
            spent = row["total_spent"]

            if search_lower and \
               search_lower not in name.lower() and \
               search_lower not in email.lower():
                continue

            result.append({
                "name": name,
                "email": email,
                "phone": phone,
                "loyalty_points": pts,
                "bookings": bks,
                "total_spent": spent,
            })

        return result

    def _refresh_customers(self):
        """Clear and repopulate the customers treeview."""
        for row in self.customers_tree.get_children():
            self.customers_tree.delete(row)

        search = self._cust_search_var.get().strip()
        try:
            self._cust_data = self._fetch_customers(search)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {e}")
            return

        if self._cust_sort_col:
            self._apply_customer_sort()

        for d in self._cust_data:
            self.customers_tree.insert("", "end", values=(
                d["name"],
                d["email"],
                d["phone"],
                d["loyalty_points"],
                d["bookings"],
                f"£{d['total_spent']:.2f}",
            ))

        self._cust_summary.config(
            text=f"{len(self._cust_data)} customer(s) found"
        )

    def _sort_customers(self, col):
        """Toggle sort direction on the clicked column heading."""
        if self._cust_sort_col == col:
            self._cust_sort_asc = not self._cust_sort_asc
        else:
            self._cust_sort_col = col
            self._cust_sort_asc = True
        self._refresh_customers()

    def _apply_customer_sort(self):
        """Sort self._cust_data in-place based on the active sort column."""
        key_map = {
            "Customer Name": lambda d: d["name"].lower(),
            "Email": lambda d: d["email"].lower(),
            "Phone": lambda d: d["phone"],
            "Loyalty Points": lambda d: d["loyalty_points"],
            "Bookings": lambda d: d["bookings"],
            "Total Spent (£)": lambda d: d["total_spent"],
        }
        key_fn = key_map.get(self._cust_sort_col)
        if key_fn:
            self._cust_data.sort(key=key_fn, reverse=not self._cust_sort_asc)

    def _export_customers_csv(self):
        """Export the currently displayed customer rows to a CSV file."""
        if not self._cust_data:
            messagebox.showwarning("No Data", "No customers to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"customers_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not filepath:
            return

        try:
            fieldnames = ["Customer Name", "Email", "Phone",
                          "Loyalty Points", "Bookings", "Total Spent (£)"]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for d in self._cust_data:
                    writer.writerow({
                        "Customer Name": d["name"],
                        "Email": d["email"],
                        "Phone": d["phone"],
                        "Loyalty Points": d["loyalty_points"],
                        "Bookings": d["bookings"],
                        "Total Spent (£)": f"£{d['total_spent']:.2f}",
                    })
            messagebox.showinfo("Export Successful", f"Saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save CSV:\n{e}")

    # --- MANAGE STAFF TAB ---
    def _build_staff_tab(self):
        # Split view: left for form, right for treeview
        main_fr = tk.Frame(self.tab_staff, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=20, pady=20)

        # Left side: Form
        form_fr = tk.Frame(main_fr, bg=BG2, padx=20, pady=20, highlightbackground=BORDER, highlightthickness=1)
        form_fr.pack(side="left", fill="y", padx=(0, 20))

        tk.Label(form_fr, text="Register New Staff", font=("Segoe UI", 16, "bold"), bg=BG2,
                 fg=FG).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        tk.Label(form_fr, text="Username:", font=("Segoe UI", 11), bg=BG2,
                 fg=TEXT2).grid(row=1, column=0, sticky="w", pady=10)
        self.staff_user_ent = tk.Entry(form_fr, font=("Segoe UI", 11), bg=BG, fg=FG, insertbackground=FG,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_user_ent.grid(row=1, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Password:", font=("Segoe UI", 11), bg=BG2,
                 fg=TEXT2).grid(row=2, column=0, sticky="w", pady=10)
        self.staff_pass_ent = tk.Entry(form_fr, font=("Segoe UI", 11), bg=BG, fg=FG, insertbackground=FG,
                                       width=25, show="*", relief="flat",
                                       highlightbackground=BORDER, highlightthickness=1)
        self.staff_pass_ent.grid(row=2, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Full Name:", font=("Segoe UI", 11), bg=BG2,
                 fg=TEXT2).grid(row=3, column=0, sticky="w", pady=10)
        self.staff_name_ent = tk.Entry(form_fr, font=("Segoe UI", 11), bg=BG, fg=FG, insertbackground=FG,
                                       width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_name_ent.grid(row=3, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Email:", font=("Segoe UI", 11), bg=BG2,
                 fg=TEXT2).grid(row=4, column=0, sticky="w", pady=10)
        self.staff_email_ent = tk.Entry(form_fr, font=("Segoe UI", 11), bg=BG, fg=FG, insertbackground=FG,
                                        width=25, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        self.staff_email_ent.grid(row=4, column=1, sticky="w", pady=10)

        tk.Label(form_fr, text="Cinema:", font=("Segoe UI", 11), bg=BG2,
                 fg=TEXT2).grid(row=5, column=0, sticky="w", pady=10)
        self.staff_cinema_cb = ttk.Combobox(form_fr, state="readonly", width=23)
        self.staff_cinema_cb.grid(row=5, column=1, sticky="w", pady=10)

        self._create_btn(form_fr, "➕ Create Staff", SUCCESS, self._submit_staff).grid(
            row=6, column=0, columnspan=2, pady=(30, 0))

        # Right side: Treeview
        list_fr = tk.Frame(main_fr, bg=BG)
        list_fr.pack(side="left", fill="both", expand=True)

        tk.Label(list_fr, text="Current Staff Accounts", font=(
            "Segoe UI", 16, "bold"), bg=BG, fg=FG).pack(anchor="w", pady=(0, 10))

        cols = ("ID", "Username", "Full Name", "Cinema", "Status")
        self.staff_tv = ttk.Treeview(list_fr, columns=cols, show="headings", style="Treeview")
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

        self._create_btn(list_fr, "🗑 Remove Selected", WARNING, self._remove_staff,
                         padx=10, pady=4, font=("Segoe UI", 9)).pack(pady=(20, 10))

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
