"""
src/gui/film_listing_window.py
==============================
Film Listing screen for the Horizon Cinemas Booking System (HCBS).

Author      : [Your Name] — Student ID: [Your Student ID]
Module      : Advanced Software Development
Description : Displays films and showings for a selected cinema and date.
              Staff can browse by date and click a showing button to proceed
              to the BookingWindow.
"""

from src.utils.rbac import require_role
from src.gui.login_window import SessionManager
from src.models.film import Film
from src.models.showing import Showing
from src.models.cinema import Cinema
import tkinter as tk
from tkinter import ttk, messagebox
import calendar
import datetime
import os

# Poster loading utility
from src.utils.image_loader import load_poster

# ── Project imports ──────────────────────────────────────────────────────────
import sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Colour / font constants (matches GUI_STYLE_GUIDE.md) ────────────────────
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#111b2e"
ACCENT = "#4f8cff"
ACCENT_HVR = "#3478f6"
SUCCESS = "#22c55e"
SUCCESS_HVR = "#16a34a"
SOLD_OUT = "#26344a"
WARNING = "#f59e0b"
TEXT = "#f8fafc"
TEXT2 = "#a7b4c8"
ERROR = "#ef4444"
BORDER = "#26344a"

FF = "Segoe UI"
FONT_H1 = (FF, 20, "bold")
FONT_H2 = (FF, 14, "bold")
FONT_BODY = (FF, 11)
FONT_SMALL = (FF, 9)
FONT_LABEL = (FF, 11, "bold")
FONT_BTN = (FF, 10, "bold")

THUMB_SIZE = (90, 130)    # poster thumbnail dimensions
CARD_PAD = 14
CARD_GAP = 10


@require_role('staff')
class FilmListingWindow:
    """
    Film Listing screen — shown after login for all roles.

    Allows the user to select a cinema and date, then browse all showings
    for that day. Each film card shows poster, metadata, and coloured
    showing-time buttons. Clicking a button routes to BookingWindow.

    Parameters
    ----------
    parent : tk.Widget
        Root window (standalone) or a frame inside :class:`StaffShellWindow`.

    embedded : bool
        When True, skip the duplicate top bar (shell provides one) and use compact rows.

    shell
        Optional :class:`StaffShellWindow` for tab navigation (e.g. jump to booking).
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        embedded: bool = False,
        shell: object | None = None,
    ) -> None:
        self.content = parent
        self._tk = parent.winfo_toplevel()
        self.shell = shell
        self._embedded = embedded
        self.session = SessionManager.get_instance()
        self.user = self.session.get_current_user()

        self._current_date = datetime.date.today()
        self._cinemas: list[Cinema] = []
        self.poster_images: list = []   # keep references so GC doesn't collect them
        self._selected_cinema_id: int | None = None

        # Filter state — populated by _refresh_films(), filtered by _apply_filters()
        self._all_films: list[tuple] = []   # list of (Film, list[Showing])
        self._displayed_films: list[tuple] = []

        # StringVar traces for real-time filtering
        self._search_var = tk.StringVar()
        self._genre_var = tk.StringVar(value="All")
        self._rating_var = tk.StringVar(value="All")

        if embedded:
            self._r = {"ctrl": 0, "search": 1, "film": 2, "status": 3}
        else:
            self._r = {"top": 0, "ctrl": 1, "search": 2, "film": 3, "status": 4}

        if not embedded:
            self._configure_root()
        else:
            self.content.columnconfigure(0, weight=1)
            self.content.rowconfigure(self._r["film"], weight=1)

        self._build_ui()
        self._load_cinemas()

    # ── Window setup ─────────────────────────────────────────────────────────

    def _configure_root(self) -> None:
        self.content.title("HCBS — Now Showing")
        self.content.minsize(1024, 768)
        self.content.configure(bg=BG)
        self.content.resizable(True, True)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(self._r["film"], weight=1)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        if not self._embedded:
            self._build_topbar()
        self._build_controls()
        self._build_search_bar()
        self._build_film_area()
        self._build_statusbar()

    def _build_topbar(self) -> None:
        """Top navigation bar with title and logout."""
        bar = tk.Frame(self.content, bg=BG2, pady=10)
        bar.grid(row=self._r["top"], column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        tk.Label(bar, text="🎬", font=(FF, 20), bg=BG2, fg=ACCENT
                 ).grid(row=0, column=0, padx=(16, 8))
        tk.Label(bar, text="Horizon Cinemas Booking System",
                 font=FONT_H2, bg=BG2, fg=TEXT
                 ).grid(row=0, column=1, sticky="w")

        col = 3
        # Admin Dashboard
        if self.user and self.user.role in ('admin', 'manager'):
            admin_btn = tk.Button(
                bar, text="Admin Dashboard", font=FONT_BTN,
                bg=ACCENT, fg=TEXT, activebackground=ACCENT_HVR,
                relief="flat", cursor="hand2", padx=14, pady=4,
                command=self._open_admin
            )
            admin_btn.grid(row=0, column=col, padx=(0, 16))
            col += 1

            dash_btn = tk.Button(
                bar, text="📊 Dashboard", font=FONT_BTN,
                bg="#8E9775", fg=TEXT, activebackground="#A7AF92",
                relief="flat", cursor="hand2", padx=14, pady=4,
                command=self._open_dashboard
            )
            dash_btn.grid(row=0, column=col, padx=(0, 16))
            col += 1

        # Manager Dashboard
        if self.user and self.user.role == 'manager':
            mgr_btn = tk.Button(
                bar, text="Manager Dashboard", font=FONT_BTN,
                bg="#8E9775", fg=TEXT, activebackground="#A7AF92",
                relief="flat", cursor="hand2", padx=14, pady=4,
                command=self._open_manager
            )
            mgr_btn.grid(row=0, column=col, padx=(0, 16))
            col += 1

        # Cancel Booking
        if not self._embedded:
            cancel_btn = tk.Button(
                bar, text="Cancel Booking", font=FONT_BTN,
                bg=ERROR, fg=TEXT, activebackground="#C16A0B",
                relief="flat", cursor="hand2", padx=14, pady=4,
                command=self._open_cancellation
            )
            cancel_btn.grid(row=0, column=col, padx=(0, 16))
            col += 1

        # Help Chatbot
        help_btn = tk.Button(
            bar, text="❓ Help", font=FONT_BTN,
            bg=WARNING, fg=TEXT, activebackground=ACCENT_HVR,
            relief="flat", cursor="hand2", padx=14, pady=4,
            command=self._open_chatbot
        )
        help_btn.grid(row=0, column=col, padx=(0, 16))
        col += 1

        # Logout
        logout_btn = tk.Button(
            bar, text="Logout", font=FONT_BTN,
            bg="#4A4A4A", fg="#FFFFFF", activebackground="#333333",
            relief="flat", cursor="hand2", padx=14, pady=4,
            command=self._logout
        )
        logout_btn.grid(row=0, column=col, padx=(0, 16))

    def _open_admin(self) -> None:
        from src.gui.admin_window import AdminWindow
        AdminWindow(tk.Toplevel(self._tk))

    def _open_manager(self) -> None:
        from src.gui.manager_window import ManagerWindow
        ManagerWindow(tk.Toplevel(self._tk))

    def _open_dashboard(self) -> None:
        from src.gui.dashboard_window import DashboardWindow
        DashboardWindow(tk.Toplevel(self._tk))

    def _open_cancellation(self) -> None:
        if self.shell is not None:
            self.shell.select_cancel_tab()
            return
        from src.gui.cancellation_window import CancellationWindow
        CancellationWindow(tk.Toplevel(self._tk))

    def _open_chatbot(self) -> None:
        if not hasattr(self, "chatbot_window") or not self.chatbot_window.winfo_exists():
            from src.gui.chatbot_widget import ChatbotWidget
            self.chatbot_window = ChatbotWidget(self._tk)
        else:
            self.chatbot_window.show_widget()

    def _build_controls(self) -> None:
        """Date navigator + cinema selector row."""
        ctrl = tk.Frame(self.content, bg=BG, pady=12)
        ctrl.grid(row=self._r["ctrl"], column=0, sticky="ew", padx=20)
        ctrl.columnconfigure(4, weight=1)

        # ── Previous / Next day ───────────────────────────────────────────────
        prev_btn = tk.Button(
            ctrl, text="◀  Prev Day", font=FONT_BTN,
            bg=BG2, fg=TEXT, activebackground=ACCENT, relief="flat",
            cursor="hand2", padx=12, pady=6,
            command=self._prev_day
        )
        prev_btn.grid(row=0, column=0, padx=(0, 8))

        self._date_lbl = tk.Label(
            ctrl, text=self._fmt_date(), font=FONT_H2,
            bg=BG, fg=TEXT, width=24, anchor="center"
        )
        self._date_lbl.grid(row=0, column=1)

        next_btn = tk.Button(
            ctrl, text="Next Day  ▶", font=FONT_BTN,
            bg=BG2, fg=TEXT, activebackground=ACCENT, relief="flat",
            cursor="hand2", padx=12, pady=6,
            command=self._next_day
        )
        next_btn.grid(row=0, column=2, padx=(8, 8))

        pick_btn = tk.Button(
            ctrl, text="📅  Pick date…", font=FONT_BTN,
            bg=ACCENT, fg=TEXT, activebackground=ACCENT_HVR, relief="flat",
            cursor="hand2", padx=12, pady=6,
            command=self._open_date_calendar,
        )
        pick_btn.grid(row=0, column=3, padx=(0, 24))

        # ── Cinema selector ───────────────────────────────────────────────────
        tk.Label(ctrl, text="Cinema:", font=FONT_LABEL,
                 bg=BG, fg=TEXT2).grid(row=0, column=4, sticky="e")

        self._cinema_var = tk.StringVar()

        if self.user and self.user.is_admin:
            style = ttk.Style()
            style.theme_use('clam')
            style.configure("HCBS.TCombobox",
                            fieldbackground=BG2, background=BG2,
                            foreground=TEXT, selectbackground=ACCENT,
                            arrowcolor=TEXT)
            style.map("HCBS.TCombobox",
                      fieldbackground=[('readonly', BG2), ('disabled', BG2), ('focus', BG2), ('active', BG2)],
                      foreground=[('readonly', TEXT), ('disabled', TEXT), ('focus', TEXT), ('active', TEXT)])
            app_root = self._tl._root()
            app_root.option_add('*TCombobox*Listbox.background', BG2, 100)
            app_root.option_add('*TCombobox*Listbox.foreground', TEXT, 100)
            app_root.option_add('*TCombobox*Listbox.selectBackground', ACCENT, 100)
            app_root.option_add('*TCombobox*Listbox.selectForeground', TEXT, 100)
            self._cinema_cb = ttk.Combobox(
                ctrl, textvariable=self._cinema_var,
                state="readonly", font=FONT_BODY, width=34,
                style="HCBS.TCombobox"
            )
            self._cinema_cb.grid(row=0, column=5, padx=(8, 0))
            self._cinema_cb.bind("<<ComboboxSelected>>", self._on_cinema_change)
        else:
            # Staff: Show static label
            tk.Label(ctrl, textvariable=self._cinema_var, font=FONT_LABEL,
                     bg=BG, fg=TEXT).grid(row=0, column=5, padx=(8, 0), sticky="w")

    def _build_search_bar(self) -> None:
        """
        Search + filter bar — inserted between date controls and film canvas.

        Controls
        --------
        - Search Entry  : real-time title / actor keyword filter (StringVar trace).
        - Genre combo   : filters by exact genre match (or 'All').
        - Age Rating    : filters by exact BBFC rating (or 'All').
        - Clear button  : resets all three controls and re-renders all films.
        """
        GENRES = ["All", "Action", "Animation", "Comedy", "Documentary",
                  "Drama", "Horror", "Romance", "Sci-Fi", "Thriller"]
        RATINGS = ["All", "U", "PG", "12", "12A", "15", "18"]

        bar = tk.Frame(self.content, bg=BG2, pady=10)
        bar.grid(row=self._r["search"], column=0, sticky="ew", padx=0)
        bar.columnconfigure(1, weight=1)   # search field expands

        # ── Search label + entry ──────────────────────────────────────────────
        tk.Label(bar, text="🔍  Search by title or actor:",
                 font=FONT_LABEL, bg=BG2, fg=TEXT2
                 ).grid(row=0, column=0, padx=(16, 6))

        search_entry = tk.Entry(
            bar, textvariable=self._search_var,
            font=FONT_BODY, bg=BG, fg=TEXT,
            insertbackground=TEXT, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
            highlightcolor=ACCENT
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 16), ipady=6)
        search_entry.bind("<FocusIn>",
                          lambda e: search_entry.config(highlightbackground=ACCENT))
        search_entry.bind("<FocusOut>",
                          lambda e: search_entry.config(highlightbackground=BORDER))

        # ── Genre combo ───────────────────────────────────────────────────────
        tk.Label(bar, text="Genre:", font=FONT_LABEL,
                 bg=BG2, fg=TEXT2).grid(row=0, column=2, padx=(0, 6))

        self._genre_cb = ttk.Combobox(
            bar, textvariable=self._genre_var,
            values=GENRES, state="readonly",
            font=FONT_BODY, width=14, style="HCBS.TCombobox"
        )
        self._genre_cb.grid(row=0, column=3, padx=(0, 16))

        # ── Age rating combo ──────────────────────────────────────────────────
        tk.Label(bar, text="Rating:", font=FONT_LABEL,
                 bg=BG2, fg=TEXT2).grid(row=0, column=4, padx=(0, 6))

        self._rating_cb = ttk.Combobox(
            bar, textvariable=self._rating_var,
            values=RATINGS, state="readonly",
            font=FONT_BODY, width=8, style="HCBS.TCombobox"
        )
        self._rating_cb.grid(row=0, column=5, padx=(0, 16))

        # ── Clear Filters button ──────────────────────────────────────────────
        clear_btn = tk.Button(
            bar, text="✕  Clear Filters", font=FONT_BTN,
            bg=SOLD_OUT, fg=TEXT, activebackground=BG,
            relief="flat", cursor="hand2", padx=12, pady=6,
            command=self._clear_filters
        )
        clear_btn.grid(row=0, column=6, padx=(0, 16))
        clear_btn.bind("<Enter>", lambda e: clear_btn.config(bg=BG))
        clear_btn.bind("<Leave>", lambda e: clear_btn.config(bg=SOLD_OUT))

        # ── Attach traces (fire on every change) ─────────────────────────────
        self._search_var.trace_add("write", lambda *_: self._apply_filters())
        self._genre_var .trace_add("write", lambda *_: self._apply_filters())
        self._rating_var.trace_add("write", lambda *_: self._apply_filters())

    def _build_film_area(self) -> None:
        """Scrollable canvas that holds all film cards."""
        wrapper = tk.Frame(self.content, bg=BG)
        wrapper.grid(
            row=self._r["film"],
            column=0,
            sticky="nsew",
            padx=20,
            pady=(8, 0),
        )
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrapper, bg=BG, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(wrapper, orient="vertical",
                                 command=self._canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        # Inner frame where all cards live
        self._inner = tk.Frame(self._canvas, bg=BG)
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )
        self._inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse-wheel scrolling
        self._canvas.bind_all("<MouseWheel>",
                              lambda e: self._canvas.yview_scroll(
                                  -1 * (e.delta // 120), "units"))

    def _build_statusbar(self) -> None:
        """Bottom status bar."""
        bar = tk.Frame(self.content, bg=BG2, pady=6)
        bar.grid(row=self._r["status"], column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self._status_lbl = tk.Label(
            bar, text="Select a cinema to view today's films.",
            font=FONT_SMALL, bg=BG2, fg=TEXT2, anchor="w"
        )
        self._status_lbl.grid(row=0, column=0, padx=16, sticky="w")

        tk.Label(bar, text="🟢 Available  🔘 Sold Out",
                 font=FONT_SMALL, bg=BG2, fg=TEXT2
                 ).grid(row=0, column=1, padx=16)

    # ── Canvas resize helpers ─────────────────────────────────────────────────

    def _on_inner_resize(self, _e=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event) -> None:
        self._canvas.itemconfig(self._inner_id, width=event.width)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_cinemas(self) -> None:
        """Populate the cinema selection and load initial film data."""
        try:
            print("[DEBUG] FilmListingWindow._load_cinemas called")
            self._cinemas = Cinema.get_all()
            print(f"[DEBUG] Loaded {len(self._cinemas)} cinemas")
            names = [c.cinema_name for c in self._cinemas]

            # Handle home cinema for staff
            home_cinema = None
            if self.user and self.user.cinema_id:
                home_cinema = next((c for c in self._cinemas if c.cinema_id == self.user.cinema_id), None)

            if home_cinema:
                self._cinema_var.set(home_cinema.cinema_name)
                self._selected_cinema_id = home_cinema.cinema_id
                print(f"[DEBUG] Selected home cinema: {self._selected_cinema_id} ({home_cinema.cinema_name})")
            elif names:
                self._cinema_var.set(names[0])
                self._selected_cinema_id = self._cinemas[0].cinema_id
                print(f"[DEBUG] Selected first cinema: {self._selected_cinema_id} ({names[0]})")

            # Populate combobox if it exists (for admin/manager)
            if hasattr(self, '_cinema_cb'):
                self._cinema_cb['values'] = names

            # Load initial films
            if self._selected_cinema_id:
                self._refresh_films()

        except Exception as exc:
            print(f"[DEBUG] FilmListingWindow._load_cinemas ERROR: {exc}")
            messagebox.showerror("Database Error", str(exc), parent=self._tk)

    def _refresh_films(self) -> None:
        """
        Query the database for showings, build self._all_films, then apply filters.

        This is the only method that hits the database. All subsequent filtering
        is done client-side via _apply_filters() without a DB round-trip.
        """
        print(f"[DEBUG] FilmListingWindow._refresh_films called, cinema_id={self._selected_cinema_id}")
        self._all_films.clear()

        if self._selected_cinema_id is None:
            print("[DEBUG] _selected_cinema_id is None, returning")
            return

        date_str = self._current_date.isoformat()
        print(f"[DEBUG] Calling Showing.get_by_cinema_date({self._selected_cinema_id}, {date_str})")
        try:
            showings = Showing.get_by_cinema_date(
                self._selected_cinema_id, date_str
            )
            print(f"[DEBUG] Got {len(showings)} showings")
        except Exception as exc:
            print(f"[DEBUG] ERROR in get_by_cinema_date: {exc}")
            messagebox.showerror("Error", str(exc), parent=self._tk)
            return

        # Group showings by film_id, fetch Film objects
        film_showings: dict[int, list[Showing]] = {}
        for sh in showings:
            film_showings.setdefault(sh.film_id, []).append(sh)

        print(f"[DEBUG] Grouped into {len(film_showings)} films")
        for film_id, film_shows in film_showings.items():
            try:
                film = Film.get_by_id(film_id)
                self._all_films.append((film, film_shows))
            except Exception:
                continue

        print(f"[DEBUG] _all_films now has {len(self._all_films)} entries")
        # Reset filter widgets to 'All' without triggering another refresh
        # (we only reset on date/cinema change, not on filter change)
        self._apply_filters()

    def _apply_filters(self) -> None:
        """
        Filter self._all_films client-side and re-render the visible cards.

        Reads the current values of search_var, genre_var, and rating_var.
        No database calls are made here — operates purely on the cached list.
        """
        query = self._search_var.get().strip().lower()
        genre = self._genre_var.get()
        rating = self._rating_var.get()

        self._displayed_films = []
        for film, film_shows in self._all_films:
            # ── Title / actor search ──────────────────────────────────────────
            if query:
                haystack = (
                    film.title.lower() + " " +
                    film.cast_members.lower() + " " +
                    film.description.lower()
                )
                if query not in haystack:
                    continue
            # ── Genre filter ──────────────────────────────────────────────────
            if genre != "All" and film.genre != genre:
                continue
            # ── Age rating filter ─────────────────────────────────────────────
            if rating != "All" and film.age_rating != rating:
                continue

            self._displayed_films.append((film, film_shows))

        self._render_cards()

    def _render_cards(self) -> None:
        """
        Rebuild the scrollable card list from self._displayed_films.

        Called by _apply_filters() every time a filter control changes.
        """
        # Wipe existing cards
        for widget in self._inner.winfo_children():
            widget.destroy()
        self.poster_images.clear()

        if not self._all_films and self._selected_cinema_id is not None:
            tk.Label(
                self._inner,
                text=f"No showings scheduled for {self._fmt_date()}.",
                font=FONT_H2, bg=BG, fg=TEXT2, pady=60
            ).pack()
            self._set_status(f"0 showings on {self._fmt_date()}.")
            return

        if not self._displayed_films:
            # Films exist but filters excluded them all
            msg_frame = tk.Frame(self._inner, bg=BG)
            msg_frame.pack(fill="x", pady=60)
            tk.Label(
                msg_frame, text="🔍  No films match your search.",
                font=FONT_H2, bg=BG, fg=TEXT2
            ).pack()
            tk.Label(
                msg_frame,
                text="Try adjusting the search term, genre, or age rating filter.",
                font=FONT_SMALL, bg=BG, fg=TEXT2
            ).pack(pady=(4, 0))
            self._set_status(
                f"0 of {len(self._all_films)} film(s) match current filters."
            )
            return

        for i, (film, film_shows) in enumerate(self._displayed_films):
            self._build_film_card(self._inner, film, film_shows, i)

        total_shows = sum(len(s) for _, s in self._displayed_films)
        filtered = len(self._displayed_films) != len(self._all_films)
        filter_note = (f" (filtered from {len(self._all_films)})"
                       if filtered else "")
        self._set_status(
            f"{len(self._displayed_films)} film(s){filter_note}  ·  "
            f"{total_shows} showing(s) on {self._fmt_date()}  ·  "
            f"{self._get_cinema_name()}"
        )

    def _build_film_card(self, parent, film: Film,
                         showings: list[Showing], index: int) -> None:
        """Render one film card with poster, metadata, and showing buttons."""
        bg = BG_CARD if index % 2 == 0 else BG2

        card = tk.Frame(parent, bg=bg, pady=CARD_PAD, padx=CARD_PAD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=0, pady=(0, CARD_GAP))
        card.columnconfigure(1, weight=1)

        # ── Poster thumbnail ──────────────────────────────────────────────────
        poster_frame = tk.Frame(card, bg=bg, width=THUMB_SIZE[0] + 4,
                                height=THUMB_SIZE[1] + 4)
        poster_frame.grid(row=0, column=0, rowspan=3, padx=(0, 16),
                          sticky="n", pady=4)
        poster_frame.grid_propagate(False)

        poster_lbl = tk.Label(poster_frame, bg=BG)
        poster_lbl.place(x=0, y=0, width=THUMB_SIZE[0], height=THUMB_SIZE[1])

        photo = load_poster(film.poster_path, size=THUMB_SIZE)
        self.poster_images.append(photo)
        poster_lbl.config(image=photo)

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = tk.Frame(card, bg=bg)
        title_row.grid(row=0, column=1, sticky="ew")
        title_row.columnconfigure(0, weight=1)

        tk.Label(title_row, text=film.title,
                 font=FONT_H2, bg=bg, fg=TEXT, anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        # IMDb badge
        if film.imdb_rating:
            tk.Label(title_row,
                     text=f"⭐ {film.imdb_rating:.1f}",
                     font=FONT_SMALL, bg=WARNING, fg="#0b1220",
                     padx=6, pady=2
                     ).grid(row=0, column=1, padx=(8, 0))

        # Age rating badge
        tk.Label(title_row, text=f" {film.age_rating} ",
                 font=(FF, 9, "bold"), bg=ACCENT, fg=TEXT,
                 padx=4, pady=2
                 ).grid(row=0, column=2, padx=(6, 0))

        # ── Meta row ──────────────────────────────────────────────────────────
        meta = (
            f"🎭 {film.genre}   "
            f"⏱ {film.duration_formatted}   "
            + (f"🎬 {film.cast_members[:60]}{'…' if len(film.cast_members) > 60 else ''}"
               if film.cast_members else "")
        )
        tk.Label(card, text=meta, font=FONT_SMALL, bg=bg,
                 fg=TEXT2, anchor="w", wraplength=700, justify="left"
                 ).grid(row=1, column=1, sticky="ew", pady=(2, 4))

        # ── Description ───────────────────────────────────────────────────────
        if film.description:
            tk.Label(card, text=film.description[:200] + ("…" if len(film.description) > 200 else ""),
                     font=FONT_SMALL, bg=bg, fg=TEXT2,
                     anchor="w", wraplength=700, justify="left"
                     ).grid(row=2, column=1, sticky="ew", pady=(0, 8))

        # ── Showing buttons ───────────────────────────────────────────────────
        btn_row = tk.Frame(card, bg=bg)
        btn_row.grid(row=3, column=1, sticky="w", pady=(4, 0))

        tk.Label(btn_row, text="Showings:", font=FONT_LABEL,
                 bg=bg, fg=TEXT2).pack(side="left", padx=(0, 10))

        for sh in sorted(showings, key=lambda s: s.show_time):
            sold_out = sh.is_sold_out or sh.seats_remaining <= 0
            btn_bg = SOLD_OUT if sold_out else SUCCESS
            btn_fg = TEXT2 if sold_out else TEXT
            btn_text = f"{sh.show_time}\n{'SOLD OUT' if sold_out else f'{sh.seats_remaining} seats'}"
            state = "disabled" if sold_out else "normal"

            btn = tk.Button(
                btn_row,
                text=btn_text,
                font=FONT_BTN,
                bg=btn_bg, fg=btn_fg,
                activebackground=SUCCESS_HVR if not sold_out else SOLD_OUT,
                activeforeground=TEXT,
                relief="flat", cursor="hand2" if not sold_out else "",
                padx=14, pady=8, state=state,
                command=lambda s=sh: self._open_booking(s)
            )
            btn.pack(side="left", padx=(0, 8))
            if not sold_out:
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=SUCCESS_HVR))
                btn.bind("<Leave>", lambda e, b=btn, c=btn_bg: b.config(bg=c))

        # ── Similar Films Section ─────────────────────────────────────────────
        from src.utils.film_recommender import recommend_films
        recs = recommend_films(film.film_id, self._selected_cinema_id)
        if recs:
            rec_container = tk.Frame(card, bg=bg, pady=10)
            rec_container.grid(row=4, column=1, sticky="w", pady=(10, 0))

            tk.Label(rec_container, text="✨ You might also like...",
                     font=FONT_LABEL, bg=bg, fg=ACCENT).pack(anchor="w", pady=(0, 5))

            rec_list = tk.Frame(rec_container, bg=bg)
            rec_list.pack(fill="x")

            for r in recs:
                r_frame = tk.Frame(rec_list, bg=BG_CARD if index % 2 != 0 else BG2,
                                   highlightbackground=BORDER, highlightthickness=1, padx=10, pady=5)
                r_frame.pack(side="left", padx=(0, 10))

                title_lbl = tk.Label(r_frame, text=r["title"][:25] + ("..." if len(r["title"])
                                     > 25 else ""), font=(FF, 10, "bold"), bg=r_frame["bg"], fg=TEXT)
                title_lbl.pack(anchor="w")

                meta_lbl = tk.Label(r_frame, text=f"{r['genre']} | {r['age_rating']}",
                                    font=FONT_SMALL, bg=r_frame["bg"], fg=TEXT2)
                meta_lbl.pack(anchor="w")

                info_lbl = tk.Label(
                    r_frame, text=f"Next: {r['next_show_date']} {r['next_show_time']}",
                    font=FONT_SMALL, bg=r_frame["bg"], fg=TEXT2)
                info_lbl.pack(anchor="w", pady=(2, 5))

                btn = tk.Button(
                    r_frame, text="Book Now", font=FONT_BTN, bg=SUCCESS, fg=TEXT,
                    activebackground=SUCCESS_HVR, relief="flat", cursor="hand2", padx=10, pady=2,
                    command=lambda sh_id=r["next_showing_id"]: self._open_booking_by_id(sh_id)
                )
                btn.pack(anchor="w")

    # ── Event handlers ────────────────────────────────────────────────────────

    def _clear_filters(self) -> None:
        """
        Reset all three filter controls to their default 'All' / empty state
        and re-render all films. Traces will fire automatically after set().
        """
        self._search_var.set("")
        self._genre_var .set("All")
        self._rating_var.set("All")
        # Traces have already called _apply_filters; scroll back to top
        self._canvas.yview_moveto(0)

    def _on_cinema_change(self, _event=None) -> None:
        idx = self._cinema_cb.current()
        if 0 <= idx < len(self._cinemas):
            self._selected_cinema_id = self._cinemas[idx].cinema_id
            self._refresh_films()

    def _set_listing_date(self, d: datetime.date) -> None:
        """Update the visible date and reload showings for that day."""
        self._current_date = d
        self._date_lbl.config(text=self._fmt_date())
        self._refresh_films()

    def _open_date_calendar(self) -> None:
        """Popup month grid to jump to any day (no extra packages)."""
        win = tk.Toplevel(self._tk)
        win.title("Pick a date")
        win.configure(bg=BG)
        win.transient(self._tk)
        win.grab_set()
        view = {"y": self._current_date.year, "m": self._current_date.month}

        header = tk.Label(win, text="", font=FONT_H2, bg=BG, fg=TEXT)
        header.pack(pady=(12, 4))

        nav = tk.Frame(win, bg=BG)
        nav.pack()
        tk.Button(
            nav, text="◀  Month", font=FONT_BTN, bg=BG2, fg=TEXT,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=lambda: self._cal_shift_month(view, -1, grid_fr, header, win),
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            nav, text="Today", font=FONT_BTN, bg=BG2, fg=TEXT,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=lambda: self._cal_go_today(view, grid_fr, header),
        ).pack(side=tk.LEFT, padx=12)
        tk.Button(
            nav, text="Month  ▶", font=FONT_BTN, bg=BG2, fg=TEXT,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=lambda: self._cal_shift_month(view, 1, grid_fr, header, win),
        ).pack(side=tk.LEFT, padx=4)

        grid_fr = tk.Frame(win, bg=BG)
        grid_fr.pack(padx=14, pady=12)

        def rebuild() -> None:
            for w in grid_fr.winfo_children():
                w.destroy()
            y, m = view["y"], view["m"]
            header.config(text=f"{calendar.month_name[m]} {y}")
            weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for c, wd in enumerate(weekdays):
                tk.Label(
                    grid_fr, text=wd, font=FONT_SMALL, bg=BG, fg=TEXT2, width=5
                ).grid(row=0, column=c, padx=1, pady=(0, 4))
            today = datetime.date.today()
            for r, week in enumerate(calendar.monthcalendar(y, m), start=1):
                for c, day in enumerate(week):
                    if day == 0:
                        tk.Label(grid_fr, text="", bg=BG, width=5).grid(
                            row=r, column=c, padx=1, pady=1
                        )
                        continue

                    def pick(
                        _win=win,
                        yy=y,
                        mm=m,
                        dd=day,
                    ) -> None:
                        try:
                            chosen = datetime.date(yy, mm, dd)
                        except ValueError:
                            return
                        self._set_listing_date(chosen)
                        _win.destroy()

                    btn = tk.Button(
                        grid_fr,
                        text=str(day),
                        font=FONT_BODY,
                        width=4,
                        relief="flat",
                        cursor="hand2",
                        command=pick,
                    )
                    is_today = (y, m, day) == (today.year, today.month, today.day)
                    is_sel = (y, m, day) == (
                        self._current_date.year,
                        self._current_date.month,
                        self._current_date.day,
                    )
                    if is_sel:
                        btn.config(bg=SUCCESS, fg=TEXT, activebackground=SUCCESS_HVR)
                    elif is_today:
                        btn.config(bg=ACCENT, fg=TEXT, activebackground=ACCENT_HVR)
                    else:
                        btn.config(bg=BG2, fg=TEXT, activebackground=ACCENT)
                    btn.grid(row=r, column=c, padx=1, pady=1)

        win._rebuild_cal = rebuild  # type: ignore[attr-defined]
        rebuild()

        tk.Button(
            win, text="Close", font=FONT_BTN, bg=BG2, fg=TEXT,
            relief="flat", padx=16, pady=6, cursor="hand2", command=win.destroy,
        ).pack(pady=(4, 14))

    def _cal_shift_month(
        self,
        view: dict,
        delta: int,
        grid_fr: tk.Frame,
        header: tk.Label,
        win: tk.Toplevel,
    ) -> None:
        m = view["m"] + delta
        y = view["y"]
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        view["y"], view["m"] = y, m
        win._rebuild_cal()  # type: ignore[attr-defined]

    def _cal_go_today(self, view: dict, grid_fr: tk.Frame, header: tk.Label) -> None:
        t = datetime.date.today()
        view["y"], view["m"] = t.year, t.month
        grid_fr.winfo_toplevel()._rebuild_cal()  # type: ignore[attr-defined]

    def _prev_day(self) -> None:
        self._set_listing_date(self._current_date - datetime.timedelta(days=1))

    def _next_day(self) -> None:
        self._set_listing_date(self._current_date + datetime.timedelta(days=1))

    def _open_booking(self, showing: Showing) -> None:
        """Open the BookingWindow for the selected showing."""
        try:
            if self.shell is not None:
                self.shell.open_booking_with_showing(showing.showing_id)
                return
            from src.gui.booking_window import BookingWindow
            top = tk.Toplevel(self._tk)
            BookingWindow(top, showing_id=showing.showing_id)
        except ImportError:
            # BookingWindow not yet implemented — show placeholder
            messagebox.showinfo(
                "Proceed to Booking",
                f"Showing ID: {showing.showing_id}\n"
                f"Date: {showing.show_date}  Time: {showing.show_time}\n"
                f"Seats Available: {showing.seats_remaining}\n\n"
                f"BookingWindow coming soon.",
                parent=self._tk
            )

    def _open_booking_by_id(self, showing_id: int) -> None:
        try:
            if self.shell is not None:
                self.shell.open_booking_with_showing(showing_id)
                return
            from src.gui.booking_window import BookingWindow
            top = tk.Toplevel(self._tk)
            BookingWindow(top, showing_id=showing_id)
        except ImportError:
            messagebox.showinfo("Error", "BookingWindow not yet implemented.")

    def _logout(self) -> None:
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?", parent=self._tk):
            from src.gui.login_window import _logout_and_return
            _logout_and_return(self._tk)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fmt_date(self) -> str:
        return self._current_date.strftime("%A, %d %B %Y")

    def _get_cinema_name(self) -> str:
        if hasattr(self, '_cinema_cb'):
            idx = self._cinema_cb.current()
            if 0 <= idx < len(self._cinemas):
                return self._cinemas[idx].cinema_name
        return self._cinema_var.get()

    def _set_status(self, msg: str) -> None:
        self._status_lbl.config(text=msg)


# ── Standalone launch (for isolated testing) ─────────────────────────────────

if __name__ == "__main__":
    # Inject a dummy session so the window can be tested without logging in
    from src.models.user import User
    session = SessionManager.get_instance()
    dummy = User(1, None, "test", "", "Test User", "", "staff")
    session.set_current_user(dummy)

    root = tk.Tk()
    FilmListingWindow(root)
    root.mainloop()
