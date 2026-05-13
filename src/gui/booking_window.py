"""
src/gui/booking_window.py
=========================
Booking Form GUI for the Horizon Cinemas Booking System (HCBS).

Author      : [Your Name] — Student ID: [Your Student ID]
Module      : Advanced Software Development
Description : Allows staff to book tickets. Features dynamic showing
              dropdowns, real-time pricing via PricingEngine, and a
              receipt generator.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import datetime

# ── Project imports ──────────────────────────────────────────────────────────
from src.database.db_connection import get_connection
from src.models.showing import Showing
from src.models.film import Film
from src.models.cinema import Cinema
from src.models.user import User
from src.utils.pricing_engine import PricingEngine
from src.gui.login_window import SessionManager
from src.utils.input_validator import InputValidator

from src.utils.pdf_service import PDFService


def allow_staff_and_admin(cls):
    """Decorator to allow staff, admin, and manager users to access the booking window."""
    original_init = cls.__init__

    def new_init(self, *args, **kwargs):
        session = SessionManager.get_instance()
        user = session.get_current_user()
        if user and user.role not in ['staff', 'admin', 'manager']:
            raise PermissionError(f"Access denied. Required: staff, admin, or manager. Got: {user.role}")
        original_init(self, *args, **kwargs)

    cls.__init__ = new_init
    return cls


def format_receipt_text(booking_data: dict) -> str:
    """Helper function to format the receipt as plain text."""
    cinema_name = booking_data.get('cinema_name', 'N/A')
    ticket_type_fmt = booking_data['ticket_type'].replace('_', ' ').title()
    seat_nums = ', '.join(booking_data['seat_numbers'])
    return f"""========================================
    HORIZON CINEMAS BOOKING SYSTEM
========================================

BOOKING CONFIRMED

BOOKING REFERENCE : {booking_data['booking_ref']}
DATE ISSUED       : {booking_data['booking_date']}

----------------------------------------
CUSTOMER DETAILS
Name              : {booking_data['customer_name']}

FILM DETAILS
Film Name         : {booking_data['film_name']}
Date              : {booking_data['show_date']}
Show Time         : {booking_data['show_time']}
Screen Number     : {booking_data['screen_id']}
Cinema Name       : {cinema_name}

TICKET DETAILS
Number of Tickets : {booking_data['quantity']}
Ticket Type       : {ticket_type_fmt}
Seat Numbers      : {seat_nums}

----------------------------------------
TOTAL COST        : £{booking_data['total_cost']:.2f}
========================================""".strip()


# ── Style Constants ──────────────────────────────────────────────────────────
BG = "#0b1220"
BG2 = "#111b2e"
BG_CARD = "#111b2e"
ACCENT = "#4f8cff"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"
TEXT = "#f8fafc"
TEXT2 = "#a7b4c8"
BORDER = "#26344a"

FF = "Segoe UI"
FONT_H1 = (FF, 22, "bold")
FONT_H2 = (FF, 18, "bold")
FONT_BODY = (FF, 12)
FONT_LABEL = (FF, 12, "bold")
FONT_BTN = (FF, 12, "bold")
FONT_MONO = ("Consolas", 11)


@allow_staff_and_admin
class BookingWindow:
    def __init__(
        self,
        root: tk.Widget,
        showing_id: int | None = None,
        *,
        embedded: bool = False,
        shell: object | None = None,
    ) -> None:
        self.root = root
        self._tl = root.winfo_toplevel()
        self._embedded = embedded
        self.shell = shell
        self.session = SessionManager.get_instance()
        self.user = self.session.get_current_user()

        if not embedded:
            self.root.title("HCBS — New Booking")
            self.root.minsize(1050, 720)
        self.root.configure(bg=BG)

        # State variables
        self._showing_id_param = showing_id
        self._all_films = []
        self._available_showings = []
        self._selected_showing: Showing = None
        self.confirmed_price = None
        self._debounce_timer = None

        self._configure_styles()
        self._configure_styles()
        self._build_ui()
        self._initialise_data()

    def _create_btn(self, parent, text, bg, command, fg="#FFFFFF", **kwargs):
        """Helper to create a styled button with hover effects."""
        btn = tk.Button(
            parent, text=text, bg=bg, fg=fg,
            relief="flat", font=("Segoe UI Semibold", 11),
            padx=20, pady=10, cursor="hand2",
            activebackground=bg, activeforeground=fg,
            command=command, **kwargs
        )
        try:
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            hover_bg = f"#{max(0, r-20):02x}{max(0, g-20):02x}{max(0, b-20):02x}"
        except (TypeError, ValueError):
            hover_bg = bg
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def load_showing_prefill(self, showing_id: int) -> None:
        """Used from the staff shell: open New booking with a showing pre-selected."""
        self._showing_id_param = showing_id
        self._initialise_data()

    def _main_menu_click(self) -> None:
        if self.shell is not None:
            self.shell.select_now_tab()
        else:
            self._tl.destroy()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "HCBS.TCombobox",
            fieldbackground=BG2,
            background=BG2,
            foreground=TEXT,
            selectbackground=ACCENT,
            arrowcolor=TEXT,
            font=FONT_BODY,
            padding=5,
        )
        style.map(
            "HCBS.TCombobox",
            foreground=[('readonly', TEXT), ('active', TEXT), ('focus', TEXT)],
        )

        # Fix dropdown list visibility (Tkinter Combobox bug where dropdown inherits foreground but not background)
        app_root = self._tl._root()
        app_root.option_add('*TCombobox*Listbox.background', BG2)
        app_root.option_add('*TCombobox*Listbox.foreground', TEXT)
        app_root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
        app_root.option_add('*TCombobox*Listbox.selectForeground', TEXT)
        style.configure("HCBS.TRadiobutton", background=BG_CARD, foreground=TEXT,
                        font=FONT_BODY)
        style.map("HCBS.TRadiobutton",
                  background=[('active', BG_CARD)],
                  indicatorcolor=[('selected', ACCENT)])

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Main container grid
        self.root.columnconfigure(0, weight=6)  # Form area
        self.root.columnconfigure(1, weight=4)  # Receipt area
        self.root.rowconfigure(0, weight=1)

        self._build_form_panel()
        self._build_receipt_panel()

    def _build_form_panel(self) -> None:
        form_frame = tk.Frame(self.root, bg=BG, padx=30, pady=30)
        form_frame.grid(row=0, column=0, sticky="nsew")

        tk.Label(
            form_frame, text="🎟️  New Ticket Booking", font=FONT_H1, bg=BG, fg=TEXT
        ).pack(anchor="w", pady=(0, 20))

        # 1. Selection Card
        sel_card = tk.Frame(form_frame, bg=BG_CARD, padx=20, pady=20, highlightbackground=BORDER, highlightthickness=1)
        sel_card.pack(fill="x", pady=(0, 20))

        self.cinema_var = tk.StringVar()
        if self.user and self.user.is_admin:
            tk.Label(sel_card, text="Select Cinema:", font=FONT_LABEL, bg=BG_CARD,
                     fg=TEXT2).grid(row=0, column=0, sticky="w", pady=5)
            self.cinema_cb = ttk.Combobox(sel_card, textvariable=self.cinema_var,
                                          state="readonly", width=40, style="HCBS.TCombobox")
            self.cinema_cb.grid(row=0, column=1, padx=10, pady=5)
            self.cinema_cb.bind("<<ComboboxSelected>>", self._on_cinema_change)
            row_offset = 1
        else:
            # Staff: Show static label
            tk.Label(sel_card, text="Cinema:", font=FONT_LABEL, bg=BG_CARD,
                     fg=TEXT2).grid(row=0, column=0, sticky="w", pady=5)
            tk.Label(sel_card, textvariable=self.cinema_var, font=FONT_LABEL, bg=BG_CARD,
                     fg=TEXT).grid(row=0, column=1, sticky="w", padx=10, pady=5)
            row_offset = 1

        # Date
        tk.Label(sel_card, text="Date:", font=FONT_LABEL, bg=BG_CARD,
                 fg=TEXT2).grid(row=row_offset, column=0, sticky="w", pady=5)
        self.date_var = tk.StringVar()
        self.date_cb = ttk.Combobox(sel_card, textvariable=self.date_var, state="readonly",
                                    width=25, style="HCBS.TCombobox", font=FONT_BODY)
        self.date_cb.grid(row=row_offset, column=1, padx=10, pady=5)
        self.date_cb.bind("<<ComboboxSelected>>", self._on_date_or_film_change)

        # Film
        tk.Label(sel_card, text="Film:", font=FONT_LABEL, bg=BG_CARD, fg=TEXT2).grid(
            row=row_offset+1, column=0, sticky="w", pady=5)
        self.film_var = tk.StringVar()
        self.film_cb = ttk.Combobox(sel_card, textvariable=self.film_var, state="readonly",
                                    width=40, style="HCBS.TCombobox", font=FONT_BODY)
        self.film_cb.grid(row=row_offset+1, column=1, padx=10, pady=5)
        self.film_cb.bind("<<ComboboxSelected>>", self._on_date_or_film_change)

        # Showing (each option includes screen number — there is no separate screen control)
        tk.Label(sel_card, text="Screen & Time:", font=FONT_LABEL, bg=BG_CARD,
                 fg=ACCENT).grid(row=row_offset+2, column=0, sticky="w", pady=5)
        self.showing_var = tk.StringVar()
        # Wider so "Screen N — time (Type) — seats" is readable (tk width is in characters).
        self.showing_cb = ttk.Combobox(sel_card, textvariable=self.showing_var,
                                       state="readonly", width=52, style="HCBS.TCombobox", font=FONT_BODY)
        self.showing_cb.grid(row=row_offset+2, column=1, padx=10, pady=5, sticky="ew")
        sel_card.columnconfigure(1, weight=1)
        self.showing_cb.bind("<<ComboboxSelected>>", self._on_showing_change)

        # 2. Ticket Details Card
        tkt_card = tk.Frame(form_frame, bg=BG_CARD, padx=20, pady=20, highlightbackground=BORDER, highlightthickness=1)
        tkt_card.pack(fill="x", pady=(0, 20))

        tk.Label(tkt_card, text="Ticket Type:", font=FONT_LABEL, bg=BG_CARD,
                 fg=TEXT2).grid(row=0, column=0, sticky="w", pady=5)

        self.ticket_type_var = tk.StringVar(value="lower_hall")
        ttk.Radiobutton(
            tkt_card, text="Lower Hall", variable=self.ticket_type_var, value="lower_hall",
            style="HCBS.TRadiobutton", command=self._schedule_realtime_update
        ).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(
            tkt_card, text="Upper Gallery", variable=self.ticket_type_var, value="upper_gallery",
            style="HCBS.TRadiobutton", command=self._schedule_realtime_update
        ).grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(
            tkt_card, text="VIP", variable=self.ticket_type_var, value="vip",
            style="HCBS.TRadiobutton", command=self._schedule_realtime_update
        ).grid(row=0, column=3, sticky="w")

        tk.Label(tkt_card, text="Quantity:", font=FONT_LABEL, bg=BG_CARD,
                 fg=TEXT2).grid(row=1, column=0, sticky="w", pady=(15, 5))
        self.qty_var = tk.IntVar(value=1)
        self.qty_spin = ttk.Spinbox(tkt_card, from_=1, to=50, textvariable=self.qty_var,
                                    width=5, font=FONT_BODY, command=self._on_qty_change)
        self.qty_spin.grid(row=1, column=1, sticky="w", pady=(15, 5))

        # Bind key release to trigger realtime update
        self.qty_spin.bind("<KeyRelease>", self._on_qty_change)
        self.qty_spin.bind("<ButtonRelease-1>", self._on_qty_change)

        # Group booking banner (hidden by default)
        self.group_banner = tk.Label(tkt_card, text="🎟 GROUP BOOKING MODE — Auto-select enabled",
                                     font=FONT_LABEL, bg="#f97316", fg=TEXT, pady=4)
        self.group_banner.grid(row=1, column=2, columnspan=2, sticky="w", padx=(15, 0), pady=(15, 5))
        self.group_banner.grid_remove()  # hidden until qty >= 10

        # Real-time availability Result Label
        chk_frame = tk.Frame(tkt_card, bg=BG_CARD)
        chk_frame.grid(row=2, column=0, columnspan=4, sticky="w", pady=(20, 0))

        self.check_btn = self._create_btn(chk_frame, "🔍 Check Availability & Price",
                                          BG2, self.check_availability_and_price, fg=ACCENT)
        self.check_btn.pack(side="left")

        self.avail_lbl = tk.Label(
            chk_frame,
            text="",
            font=FONT_LABEL,
            bg=BG_CARD,
            fg=WARNING,
            wraplength=460,
            justify="left",
            anchor="w"
        )
        self.avail_lbl.pack(side="left", padx=20, fill="x", expand=True)

        # 3. Customer Details Card
        self.cust_card = tk.Frame(form_frame, bg=BG_CARD, padx=20, pady=20,
                                  highlightbackground=BORDER, highlightthickness=1)
        self.cust_card.pack(fill="x", pady=(0, 20))

        tk.Label(self.cust_card, text="Customer Name:", font=FONT_BODY,
                 bg=BG_CARD, fg=TEXT).grid(row=0, column=0, sticky="w", pady=5)
        self.cust_name_ent = tk.Entry(self.cust_card, font=FONT_BODY, bg=BG, fg=TEXT,
                                      insertbackground=TEXT, relief="flat",
                                      highlightbackground=BORDER, highlightthickness=1)
        self.cust_name_ent.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        tk.Label(self.cust_card, text="Phone:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT).grid(row=1, column=0, sticky="w", pady=5)
        self.cust_phone_ent = tk.Entry(self.cust_card, font=FONT_BODY, bg=BG, fg=TEXT,
                                       insertbackground=TEXT, relief="flat",
                                       highlightbackground=BORDER, highlightthickness=1)
        self.cust_phone_ent.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        tk.Label(self.cust_card, text="Email:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT).grid(row=2, column=0, sticky="w", pady=5)
        self.cust_email_ent = tk.Entry(self.cust_card, font=FONT_BODY, bg=BG, fg=TEXT,
                                       insertbackground=TEXT, relief="flat",
                                       highlightbackground=BORDER, highlightthickness=1)
        self.cust_email_ent.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        self.cust_email_ent.bind("<FocusOut>", self._check_duplicate_booking)

        self.cust_card.columnconfigure(1, weight=1)

        # Duplicate Banner
        self.dup_banner = tk.Frame(form_frame, bg="#ca8a04", padx=10, pady=10)
        self.dup_lbl = tk.Label(self.dup_banner, text="", bg=WARNING, fg="#0b1220", font=FONT_BODY, wraplength=400)
        self.dup_lbl.pack(side="left", fill="x", expand=True)

        self.dup_yes_btn = self._create_btn(self.dup_banner, "Yes", ACCENT,
                                            self._dismiss_duplicate_banner, fg="#FFFFFF")
        self.dup_yes_btn.pack(side="right", padx=5)

        self.dup_no_btn = self._create_btn(self.dup_banner, "No", ERROR, self._reset_form, fg="#FFFFFF")
        self.dup_no_btn.pack(side="right", padx=5)

        # 4. Action Buttons
        act_frame = tk.Frame(form_frame, bg=BG)
        act_frame.pack(fill="x", pady=(10, 0))

        self.book_btn = self._create_btn(act_frame, "✅ Select Seats & Book", SUCCESS,
                                         self._process_booking, fg="#FFFFFF")
        self.book_btn.config(state="disabled")
        self.book_btn.pack(side="right")

        self._create_btn(act_frame, "Main Menu", BG2, self._main_menu_click, fg=ACCENT).pack(side="left")

        self._create_btn(act_frame, "🏅 Check Loyalty", "#92400E", self._show_loyalty_popup,
                         fg="#FFFFFF").pack(side="left", padx=(12, 0))

    def _build_receipt_panel(self) -> None:
        rec_frame = tk.Frame(self.root, bg=BG2, padx=30, pady=30, highlightbackground=BORDER, highlightthickness=1)
        rec_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(rec_frame, text="🧾 Booking Receipt", font=FONT_H2, bg=BG2, fg=TEXT).pack(anchor="w", pady=(0, 20))

        self.receipt_text = tk.Text(rec_frame, font=FONT_MONO, bg=BG, fg=TEXT2, relief="flat",
                                    padx=15, pady=15, state="disabled")
        self.receipt_text.pack(fill="both", expand=True)

        # Tags for display_receipt formatting
        self.receipt_text.tag_config("header", foreground=SUCCESS, font=FONT_H2, justify="center")
        self.receipt_text.tag_config("bold_large", foreground=TEXT, font=FONT_H1)
        self.receipt_text.tag_config("bold_green", foreground=SUCCESS, font=FONT_H2)
        self.receipt_text.tag_config("normal", foreground=TEXT, font=FONT_BODY)
        self.receipt_text.tag_config("label", foreground=TEXT2, font=FONT_BODY)

        # Action Buttons below receipt
        self.rec_act_frame = tk.Frame(rec_frame, bg=BG2)

        self.pdf_btn = self._create_btn(self.rec_act_frame, "🖨️ Print / Save PDF",
                                        ACCENT, self._generate_pdf, fg="#FFFFFF")
        self.pdf_btn.pack(side="left")

        self.new_booking_btn = self._create_btn(self.rec_act_frame, "🔄 New Booking", BG2, self._reset_form, fg=ACCENT)
        self.new_booking_btn.pack(side="right")

        # Hide buttons initially
        self.rec_act_frame.pack_forget()

    # ── Initialisation & Data Flow ───────────────────────────────────────────

    def _initialise_data(self) -> None:
        """Load dates, films, and handle optional showing_id parameter."""
        # 0. Populate Cinemas
        try:
            self._all_cinemas = Cinema.get_all()
            if self.user and self.user.is_admin and hasattr(self, 'cinema_cb'):
                self.cinema_cb['values'] = [c.cinema_name for c in self._all_cinemas]

            # Default to user's home cinema
            if self.user and self.user.cinema_id:
                home_c = next((c for c in self._all_cinemas if c.cinema_id == self.user.cinema_id), None)
                if home_c:
                    self.cinema_var.set(home_c.cinema_name)

            if not self.cinema_var.get() and self._all_cinemas and hasattr(self, 'cinema_cb'):
                self.cinema_cb.current(0)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to load cinemas:\n{e}")

        # 1. Populate Dates (Today + 7 days)
        today = datetime.date.today()
        dates = [(today + datetime.timedelta(days=i)).isoformat() for i in range(8)]
        self.date_cb['values'] = dates

        # 2. Populate Films
        try:
            self._all_films = Film.get_all_active()
            self.film_cb['values'] = [f.title for f in self._all_films]
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to load films:\n{e}")

        # 3. Handle showing_id parameter if provided
        if self._showing_id_param:
            try:
                sh = Showing.get_by_id(self._showing_id_param)

                # Set Cinema — always set cinema_var regardless of widget presence
                conn = get_connection()
                row = conn.execute("SELECT cinema_id FROM screens WHERE screen_id = ?", (sh.screen_id,)).fetchone()
                if row:
                    cin = next((c for c in self._all_cinemas if c.cinema_id == row['cinema_id']), None)
                    if cin:
                        self.cinema_var.set(cin.cinema_name)
                        if hasattr(self, 'cinema_cb'):
                            self.cinema_cb.set(cin.cinema_name)

                # Set Date
                if sh.show_date in dates:
                    self.date_var.set(sh.show_date)
                else:
                    self.date_cb['values'] = tuple(list(self.date_cb['values']) + [sh.show_date])
                    self.date_var.set(sh.show_date)

                # Set Film
                f_title = next((f.title for f in self._all_films if f.film_id == sh.film_id), "")
                if not f_title:
                    try:
                        # Film might be inactive but showing is scheduled
                        f = Film.get_by_id(sh.film_id)
                        self._all_films.append(f)
                        self.film_cb['values'] = tuple(list(self.film_cb['values']) + [f.title])
                        f_title = f.title
                    except Exception:
                        pass
                self.film_var.set(f_title)

                # Load Showings and Select (match by showing_id so screen + seats stay correct)
                self._on_date_or_film_change()
                for i, s in enumerate(self._available_showings):
                    if s.showing_id == sh.showing_id:
                        self.showing_cb.current(i)
                        self._on_showing_change()
                        break

                # Lock Cinema, Date & Film to prevent confusion
                if hasattr(self, 'cinema_cb'):
                    self.cinema_cb.config(state="disabled")
                self.date_cb.config(state="disabled")
                self.film_cb.config(state="disabled")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load showing {self._showing_id_param}:\n{e}")
        else:
            self.date_cb.current(0)
            if self._all_films:
                self.film_cb.current(0)
            self._on_date_or_film_change()

    # ── Event Handlers ───────────────────────────────────────────────────────

    def _on_cinema_change(self, event=None) -> None:
        self.showing_var.set('')
        self.showing_cb['values'] = []
        self._on_date_or_film_change()

    def _on_date_or_film_change(self, event=None) -> None:
        """Fetch showings for the selected date and film."""
        self._reset_check()

        date_str = self.date_var.get()
        film_title = self.film_var.get()
        if not date_str or not film_title:
            return

        film = next((f for f in self._all_films if f.title == film_title), None)
        if not film:
            return

        try:
            conn = get_connection()
            # Filter by cinema
            if self.cinema_var.get() and hasattr(self, '_all_cinemas'):
                sel_cin_name = self.cinema_var.get()
                cin = next((c for c in self._all_cinemas if c.cinema_name == sel_cin_name), None)
                cinema_id_filter = cin.cinema_id if cin else (self.user.cinema_id if self.user else 1)
            else:
                cinema_id_filter = self.user.cinema_id if self.user else 1

            cursor = conn.execute(
                """
                SELECT s.*, sc.cinema_id, sc.screen_number
                FROM showings s
                JOIN screens sc ON s.screen_id = sc.screen_id
                WHERE s.film_id = ? AND s.show_date = ? AND sc.cinema_id = ?
                ORDER BY sc.screen_number, s.show_time
                """,
                (film.film_id, date_str, cinema_id_filter),
            )
            rows = cursor.fetchall()
            self._available_showings = []
            displays = []
            for row in rows:
                s = Showing._from_row(row)
                self._available_showings.append(s)
                sn = row["screen_number"] if "screen_number" in row.keys() else s.screen_id
                displays.append(
                    f"Screen {sn} — {s.show_time} ({s.show_type.title()}) — {s.seats_remaining} seats"
                )

            if not self._available_showings:
                self.showing_cb['values'] = ["No showings available"]
                self.showing_var.set("No showings available")
                self._selected_showing = None
            else:
                self.showing_cb['values'] = displays
                self.showing_cb.current(0)
                self._on_showing_change()

        except Exception as e:
            messagebox.showerror("Error", f"Could not load showings: {e}")

    def _on_showing_change(self, event=None) -> None:
        """Map combobox selection index to the Showing object (avoids duplicate label bugs)."""
        self._reset_check()
        display_val = self.showing_var.get()
        if not display_val or display_val == "No showings available":
            self._selected_showing = None
            return

        idx = self.showing_cb.current()
        if 0 <= idx < len(self._available_showings):
            self._selected_showing = self._available_showings[idx]
        else:
            self._selected_showing = None
        self._schedule_realtime_update()

    def _on_qty_change(self, event=None):
        """Called whenever qty spinbox changes — shows/hides group banner and triggers update."""
        try:
            qty = self.qty_var.get()
            if qty >= 10:
                self.group_banner.grid()
            else:
                self.group_banner.grid_remove()
        except tk.TclError:
            pass
        self._schedule_realtime_update()

    def _schedule_realtime_update(self, event=None) -> None:
        """Debounce wrapper for the real-time availability and price update."""
        if getattr(self, '_debounce_timer', None) is not None:
            try:
                self.root.after_cancel(self._debounce_timer)
            except Exception:
                pass
        self._debounce_timer = self.root.after(300, self._perform_realtime_update)

    def _perform_realtime_update(self) -> None:
        """Calculate price, verify seat availability dynamically in real-time."""
        self.book_btn.config(text="✅ Select Seats & Book", state="disabled", bg=SUCCESS)
        self.confirmed_price = None
        self.is_waitlist_mode = False

    def _reset_check(self) -> None:
        """Disable Book button and clear price text if params change."""
        self.avail_lbl.config(text="Select a showing and quantity to see live availability.", fg=TEXT2)
        self.book_btn.config(text="✅ Select Seats & Book", state="disabled", bg=SUCCESS)
        self.confirmed_price = None
        self.is_waitlist_mode = False

    def _check_duplicate_booking(self, event=None):
        pass  # Placeholder for duplicate booking check

    def _dismiss_duplicate_banner(self):
        self.dup_banner.pack_forget()

    def check_availability_and_price(self) -> None:
        """Calculate price, verify seat availability, and validate show date."""
        self._reset_check()

        # 1. Validate inputs
        if not self._selected_showing:
            self.avail_lbl.config(text="Select a showing and quantity to see live availability.", fg=TEXT2)
            return

        t_type = self.ticket_type_var.get()
        if not t_type:
            return

        try:
            qty = self.qty_var.get()
            if qty < 1 or qty > 50:
                raise ValueError
        except (tk.TclError, ValueError):
            self.avail_lbl.config(text="❌ Error: Quantity must be between 1 and 50.", fg=ERROR)
            return

        sh = self._selected_showing

        # 2. Check booking date validation
        from src.models.booking import BookingManager, BookingError
        try:
            BookingManager.validate_booking_date(sh.show_date, sh.show_time)
        except BookingError as e:
            self.avail_lbl.config(text=f"❌ Error: {str(e)}", fg=ERROR)
            return

        # 3. Check live seat availability
        try:
            available_seats = Showing.get_live_availability(sh.showing_id, t_type)
        except Exception as e:
            self.avail_lbl.config(text=f"❌ DB Error: {str(e)}", fg=ERROR)
            return

        if available_seats <= 0:
            self.avail_lbl.config(text="❌ Sold Out — Join Waitlist", fg=ERROR)
            self.book_btn.config(text="📝 Join Waitlist", state="normal", bg="#d97706")
            self.is_waitlist_mode = True
            return
        elif available_seats < qty:
            self.avail_lbl.config(text=f"❌ Not enough seats — only {available_seats} remaining.", fg=ERROR)
            self.book_btn.config(text="📝 Join Waitlist", state="normal", bg="#d97706")
            self.is_waitlist_mode = True
            return

        # 4. Calculate total cost using PricingEngine
        try:
            conn = get_connection()

            # Check zone-specific availability
            # Get zone capacity
            cursor = conn.execute("""
                SELECT lower_hall_seats, upper_gallery_seats, vip_seats
                FROM screens WHERE screen_id = ?
            """, (sh.screen_id,))
            screen_row = cursor.fetchone()
            zone_cap = screen_row[f"{t_type}_seats"] if screen_row else 0

            # Get booked count in zone
            cursor = conn.execute("""
                SELECT COUNT(*) as c FROM tickets t
                JOIN bookings b ON t.booking_id = b.booking_id
                WHERE b.showing_id = ? AND t.ticket_type = ? AND b.booking_status = 'Active'
            """, (sh.showing_id, t_type))
            booked_in_zone = cursor.fetchone()["c"]

            avail_in_zone = zone_cap - booked_in_zone

            if avail_in_zone < qty:
                self.avail_lbl.config(
                    text=f"❌ Only {avail_in_zone} seats left in {t_type.replace('_', ' ').title()}.", fg=ERROR)
                return

            # Look up city_id from the cinema (PricingEngine uses city_id not cinema_id)
            city_row = conn.execute(
                "SELECT city_id FROM cinemas WHERE cinema_id = ?", (sh.cinema_id,)
            ).fetchone()
            city_id = city_row["city_id"] if city_row else sh.cinema_id

            self.confirmed_price = PricingEngine.calculate_price(
                city_id=city_id,
                show_type=sh.show_type,
                ticket_type=t_type,
                quantity=qty,
                db_connection=conn
            )

            # 5. Display success result with color coding
            total_str = f"£{self.confirmed_price['total_price']:.2f}"
            color = SUCCESS if available_seats > 10 else WARNING
            msg = f"✅ {available_seats} seats available — Total: {total_str}"

            self.avail_lbl.config(text=msg, fg=color)
            self.is_waitlist_mode = False
            self.book_btn.config(text="✅ Select Seats & Book", state="normal", bg=SUCCESS)

        except Exception as e:
            self.is_waitlist_mode = False
            self.avail_lbl.config(text=f"❌ Pricing Error: {str(e)}", fg=ERROR)

    # ── Booking Processing ───────────────────────────────────────────────────

    def _process_booking(self) -> None:
        try:
            if getattr(self, 'is_waitlist_mode', False):
                self._process_waitlist_join()
                return

            name = InputValidator.sanitise_text(self.cust_name_ent.get(), 100)
            email = InputValidator.sanitise_text(self.cust_email_ent.get(), 100)
            phone = InputValidator.sanitise_text(self.cust_phone_ent.get(), 20)

            if not name:
                self.avail_lbl.config(text="❌ Error: Customer Name is required.", fg=ERROR)
                return

            if email and not InputValidator.validate_email(email):
                self.avail_lbl.config(text="❌ Error: Please enter a valid email address.", fg=ERROR)
                return

            if not self._selected_showing or not self.confirmed_price:
                self.avail_lbl.config(text="❌ Error: Please check availability and price first.", fg=ERROR)
                return

            qty = self.confirmed_price["quantity"]
            sh = self._selected_showing

            from src.gui.seat_map_window import SeatMapWindow

            def on_seats_selected(selected_seats):
                booking_data = {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "selected_seats": selected_seats,
                }

                if self.user and self.user.role in ('admin', 'manager'):
                    self._finalize_booking(
                        booking_data["name"],
                        booking_data["email"],
                        booking_data["phone"],
                        booking_data["selected_seats"],
                    )
                else:
                    from src.gui.payment_window import PaymentWindow

                    PaymentWindow(
                        self.root,
                        total_amount=self.confirmed_price["total_price"],
                        booking_data=booking_data,
                        on_payment_success=self._on_payment_success,
                    )

            SeatMapWindow(
                self.root,
                sh.showing_id,
                qty,
                self.confirmed_price["ticket_type"],
                on_seats_selected,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start booking process: {e}")

    def _on_payment_success(self, booking_data: dict) -> None:
        self._finalize_booking(
            booking_data["name"],
            booking_data["email"],
            booking_data["phone"],
            booking_data["selected_seats"]
        )

    def _finalize_booking(self, name: str, email: str, phone: str, selected_seats: list) -> None:
        qty = self.confirmed_price["quantity"]
        sh = self._selected_showing
        now = datetime.datetime.now()

        try:
            conn = get_connection()
            from src.models.booking import BookingManager

            result = BookingManager.create_booking(
                showing_id=sh.showing_id,
                staff_user_id=self.user.user_id if self.user else 1,
                ticket_type=self.confirmed_price["ticket_type"],
                quantity=qty,
                customer_name=name,
                customer_email=email,
                customer_phone=phone,
                unit_price=self.confirmed_price["unit_price"],
                db_connection=conn,
                booked_by_agent=False,
                selected_seats=selected_seats
            )

            ref = result["booking_ref"]
            seat_numbers = result["seat_numbers"]

            # Refresh local showing data
            sh.seats_remaining -= qty

            try:
                cinema = Cinema.get_by_id(sh.cinema_id)
                cinema_name = cinema.cinema_name
            except Exception:
                cinema_name = "Horizon Cinemas"

            self.current_booking_data = {
                "booking_ref": ref,
                "customer_name": name,
                "film_name": self.film_var.get(),
                "show_date": sh.show_date,
                "show_time": f"{sh.show_time} ({sh.show_type.title()})",
                "screen_id": sh.screen_id,
                "cinema_name": cinema_name,
                "quantity": qty,
                "seat_numbers": seat_numbers,
                "ticket_type": self.confirmed_price["ticket_type"],
                "total_cost": self.confirmed_price["total_price"],
                "booking_date": now.strftime('%d %b %Y %H:%M')
            }

            self.display_receipt(self.current_booking_data)
            self.book_btn.config(state="disabled")

            # Award loyalty points
            try:
                from src.utils.loyalty_manager import award_points
                email = self.cust_email_ent.get().strip()
                if email:
                    loyalty = award_points(name, email, ref, self.confirmed_price["total_price"])
                    self.current_booking_data["loyalty"] = loyalty
                    self.display_receipt(self.current_booking_data)  # re-render with badge
            except Exception as e:
                print(f"Loyalty award error: {e}")

            messagebox.showinfo("Success", f"Booking Confirmed!\nReference: {ref}")

        except Exception as e:
            messagebox.showerror("Booking Failed", str(e))

    def _process_waitlist_join(self) -> None:
        name = InputValidator.sanitise_text(self.cust_name_ent.get(), 100)
        email = InputValidator.sanitise_text(self.cust_email_ent.get(), 100)
        phone = InputValidator.sanitise_text(self.cust_phone_ent.get(), 20)

        if not name or not email or not phone:
            messagebox.showwarning("Missing Info", "Name, Email, and Phone are required to join the waitlist.")
            return

        if not InputValidator.validate_email(email):
            messagebox.showwarning("Invalid Input", "Please enter a valid email address for waitlist.")
            return

        try:
            qty = self.qty_var.get()
            sh = self._selected_showing

            from src.utils.waitlist_manager import join_waitlist
            join_waitlist(sh.showing_id, name, email, phone, qty)

            messagebox.showinfo("Waitlist Joined",
                                f"You have been successfully added to the waitlist for {qty} seat(s).")
            self._reset_check()
            self.cust_name_ent.delete(0, tk.END)
            self.cust_email_ent.delete(0, tk.END)
            self.cust_phone_ent.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to join waitlist:\n{e}")

    def display_receipt(self, booking_data: dict) -> None:
        """Render the receipt into the text widget with rich formatting."""
        self.receipt_text.config(state="normal")
        self.receipt_text.delete(1.0, tk.END)

        self.receipt_text.insert(tk.END, "BOOKING CONFIRMED\n\n", "header")

        self.receipt_text.insert(tk.END, "Booking Reference:\n", "label")
        self.receipt_text.insert(tk.END, f"{booking_data['booking_ref']}\n\n", "bold_large")

        fields = [
            ("Film Name", booking_data['film_name']),
            ("Show Date", booking_data['show_date']),
            ("Show Time", booking_data['show_time']),
            ("Screen Number", str(booking_data['screen_id'])),
            ("Cinema Name", booking_data.get('cinema_name', 'N/A')),
            ("Number of Tickets", str(booking_data['quantity'])),
            ("Seat Numbers", ', '.join(booking_data['seat_numbers'])),
            ("Ticket Type", booking_data['ticket_type'].replace('_', ' ').title()),
            ("Booking Date", booking_data['booking_date'])
        ]

        for label, val in fields:
            self.receipt_text.insert(tk.END, f"{label:<20}: ", "label")
            self.receipt_text.insert(tk.END, f"{val}\n", "normal")

        self.receipt_text.insert(tk.END, "\nTotal Cost:\n", "label")
        self.receipt_text.insert(tk.END, f"£{booking_data['total_cost']:.2f}\n", "bold_green")

        # --- Group booking summary ---
        qty = booking_data.get("quantity", 1)
        if qty >= 10:
            per_seat = booking_data['total_cost'] / qty
            self.receipt_text.insert(tk.END, f"\n🎟 Group Booking — {qty} seats\n", "header")
            self.receipt_text.insert(tk.END, f"Per-seat cost: £{per_seat:.2f}\n", "label")

        # --- Loyalty badge ---
        if "loyalty" in booking_data:
            loy = booking_data["loyalty"]
            tier = loy["tier"].title()
            pts = loy["total_points"]
            earned = loy["points_earned"]
            tier_colours = {"Bronze": "#d97706", "Silver": "#cbd5e1", "Gold": "#f59e0b"}
            badge_colour = tier_colours.get(tier, TEXT2)
            self.receipt_text.tag_config(f"tier_{tier}", foreground=badge_colour, font=("Segoe UI", 11, "bold"))
            self.receipt_text.insert(tk.END, f"\n{tier} Member — {pts} pts  (+{earned} earned today)\n", f"tier_{tier}")

        # --- Embed QR Code ---
        try:
            from src.utils.qr_generator import generate_qr_image
            self.qr_img = generate_qr_image(booking_data['booking_ref'], size=150)
            self.receipt_text.insert(tk.END, "\n")
            self.receipt_text.image_create(tk.END, image=self.qr_img)
            self.receipt_text.insert(tk.END, "\n")
        except Exception as e:
            print(f"Failed to load QR: {e}")

        self.receipt_text.config(state="disabled")
        self.rec_act_frame.pack(fill="x", pady=(20, 0))

    def _generate_pdf(self) -> None:
        if hasattr(self, 'current_booking_data'):
            try:
                path = PDFService.generate_ticket(self.current_booking_data)
                if messagebox.askyesno(
                    "Success",
                    f"Ticket PDF generated successfully!\nPath: {path}\n\nWould you like to open it now?"
                ):
                    import os
                    os.startfile(path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate PDF:\n{e}")

    def _reset_form(self) -> None:
        """Clear customer fields and reset checks after booking."""
        self.cust_name_ent.delete(0, tk.END)
        self.cust_phone_ent.delete(0, tk.END)
        self.cust_email_ent.delete(0, tk.END)
        self.qty_var.set(1)
        self._reset_check()

        self.receipt_text.config(state="normal")
        self.receipt_text.delete(1.0, tk.END)
        self.receipt_text.config(state="disabled")
        self.rec_act_frame.pack_forget()

    def _show_loyalty_popup(self) -> None:
        """Show a loyalty account lookup popup keyed to the entered email."""
        email = self.cust_email_ent.get().strip()
        if not email:
            from tkinter import messagebox
            messagebox.showwarning("No Email", "Enter a customer email first.", parent=self._tl)
            return

        from src.utils.loyalty_manager import get_account, TIER_COLOURS
        acct = get_account(email)

        pop = tk.Toplevel(self._tl)
        pop.title("Loyalty Account")
        pop.geometry("420x380")
        pop.configure(bg=BG)
        pop.grab_set()

        if not acct:
            tk.Label(pop, text="No loyalty account found for this email.",
                     bg=BG, fg=TEXT2, font=FONT_BODY).pack(pady=40)
            return

        tier = acct["tier"]
        badge_colour = TIER_COLOURS.get(tier, TEXT2)

        tk.Label(pop, text="🏅 Loyalty Account", font=FONT_H2, bg=BG, fg=TEXT).pack(pady=(20, 5))
        tk.Label(pop, text=acct["customer_name"], font=FONT_BODY, bg=BG, fg=TEXT2).pack()
        tk.Label(pop, text=f"{tier.upper()} MEMBER", font=("Segoe UI", 14, "bold"), bg=BG, fg=badge_colour).pack(pady=6)
        tk.Label(pop, text=f"🔖 {acct['total_points']} pts", font=("Segoe UI", 20, "bold"), bg=BG, fg=TEXT).pack(pady=4)

        sep = tk.Frame(pop, bg=BORDER, height=1)
        sep.pack(fill="x", padx=20, pady=8)

        tk.Label(pop, text="Recent Transactions:", font=FONT_LABEL, bg=BG, fg=TEXT2).pack(anchor="w", padx=20)

        from tkinter import ttk
        cols = ("Date", "Booking", "Earned", "Deducted")
        tv = ttk.Treeview(pop, columns=cols, show="headings", height=5)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=90, anchor="center")

        for tx in acct.get("transactions", []):
            tv.insert("", "end", values=(
                tx["created_at"][:10],
                tx.get("booking_id", "—"),
                f"+{tx['points_earned']}" if tx["points_earned"] > 0 else str(tx["points_earned"]),
                tx["points_redeemed"]
            ))
        tv.pack(fill="x", padx=20, pady=8)
        tk.Button(pop, text="Close", bg=BG2, fg=TEXT, relief="flat", padx=20, pady=6, command=pop.destroy).pack(pady=6)

# ── Standalone launch (for isolated testing) ─────────────────────────────────


if __name__ == "__main__":
    session = SessionManager.get_instance()
    dummy = User(1, None, "test", "", "Test Staff", "", "staff")
    session.set_current_user(dummy)

    root = tk.Tk()
    # Mock launch - pass showing_id=1 to test pre-fill, or None
    BookingWindow(tk.Toplevel(root), showing_id=None)
    root.withdraw()
    root.mainloop()
