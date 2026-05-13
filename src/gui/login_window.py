"""
src/gui/login_window.py
=======================
Login window for the Horizon Cinemas Booking System (HCBS).

Author : [Your Name] — Student ID: [Your Student ID]
Module : Advanced Software Development
Version: 1.0.0

Provides:
  - SessionManager  : Singleton that holds the authenticated User object
                      and database connection for the lifetime of the session.
  - LoginWindow     : Tkinter login screen with username/password fields,
                      bcrypt authentication, and role-based window routing.
"""

import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional
import datetime
import time

# ---------------------------------------------------------------------------
# Resolve the path to hcbs.db relative to this file's location so the app
# works regardless of the working directory it is launched from.
# ---------------------------------------------------------------------------
import os
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, '..', '..'))
DB_PATH = os.path.join(_PROJECT_ROOT, 'hcbs.db')

# ---------------------------------------------------------------------------
# Lazy imports for role windows — avoids circular imports at module load time.
# Each window module must expose a class with the names below.
# ---------------------------------------------------------------------------


def _get_manager_window():
    from src.gui.manager_window import ManagerWindow
    return ManagerWindow


def _get_admin_window():
    from src.gui.admin_window import AdminWindow
    return AdminWindow


def _get_staff_window():
    from src.gui.staff_window import StaffWindow
    return StaffWindow


# ===========================================================================
# Colour & font constants  (matches GUI_STYLE_GUIDE.md)
# ===========================================================================
BG_PRIMARY = "#0b1220"
BG_SECONDARY = "#111b2e"
BG_CARD = "#162338"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#3b78f6"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#a7b4c8"
BORDER = "#26344a"

FONT_FAMILY = "Segoe UI"
FONT_H1 = (FONT_FAMILY, 24, "bold")
FONT_H2 = (FONT_FAMILY, 16, "bold")
FONT_BODY = (FONT_FAMILY, 12)
FONT_SMALL = (FONT_FAMILY, 10)
FONT_LABEL = (FONT_FAMILY, 12, "bold")


# ===========================================================================
# SessionManager — Singleton
# ===========================================================================

class SessionManager:
    """
    Application-wide singleton that stores the currently authenticated user
    and the shared database connection.

    Usage
    -----
    Anywhere in the app::

        from src.gui.login_window import SessionManager
        session = SessionManager.get_instance()
        user    = session.get_current_user()

    Notes
    -----
    - Only one instance is ever created (classic singleton via ``_instance``).
    - The database connection is opened once at startup and kept alive.
    """

    _instance: Optional["SessionManager"] = None

    def __new__(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_user = None
            cls._instance._db_connection = None
            cls._instance._last_activity = None
            cls._instance._active_root = None
            cls._instance._timeout_thread = threading.Thread(target=cls._instance._check_timeout_loop, daemon=True)
            cls._instance._timeout_thread.start()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SessionManager":
        """Return (or create) the singleton SessionManager."""
        return cls()

    # ------------------------------------------------------------------
    # Database connection
    # ------------------------------------------------------------------

    def get_db_connection(self) -> sqlite3.Connection:
        """
        Return the shared SQLite connection, opening it if not yet open.

        Returns:
            sqlite3.Connection: The active database connection.
        """
        if self._db_connection is None:
            self._db_connection = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._db_connection.row_factory = sqlite3.Row
        return self._db_connection

    def close_db_connection(self) -> None:
        """Close the SQLite connection gracefully."""
        if self._db_connection:
            self._db_connection.close()
            self._db_connection = None

    # ------------------------------------------------------------------
    # User session
    # ------------------------------------------------------------------

    def set_current_user(self, user) -> None:
        """
        Store the authenticated User object in the session.

        Args:
            user: A ``User`` instance returned by ``User.login()``.
        """
        self._current_user = user

    def get_current_user(self):
        """
        Retrieve the currently authenticated User.

        Returns:
            User | None: The logged-in user, or None if no session is active.
        """
        return self._current_user

    def clear_session(self) -> None:
        """
        Clear the current user session.

        Calls ``user.logout()`` to update the User object's internal flag,
        then removes the reference so ``get_current_user()`` returns None.
        """
        if self._current_user:
            self._current_user.logout()
        self._current_user = None
        self._last_activity = None

    def update_activity(self, event=None) -> None:
        """Update the last activity timestamp on user interaction."""
        self._last_activity = datetime.datetime.now()

    def register_root(self, root: tk.Tk) -> None:
        """Register the active Tkinter root window and bind interaction events."""
        self._active_root = root
        self.update_activity()

        # Bind events to update activity
        root.bind_all("<Any-KeyPress>", self.update_activity)
        root.bind_all("<Any-Button>", self.update_activity)
        root.bind_all("<Motion>", self.update_activity)

    def _check_timeout_loop(self) -> None:
        """Background daemon thread checking for 15 minutes of inactivity."""
        while True:
            time.sleep(30)
            if self._current_user and self._last_activity:
                inactive_duration = datetime.datetime.now() - self._last_activity
                if inactive_duration > datetime.timedelta(minutes=15):
                    if self._active_root:
                        # Schedule on main thread to prevent cross-thread UI updates
                        self._active_root.after(0, self._trigger_auto_logout)

    def _trigger_auto_logout(self) -> None:
        """Executed on the main thread to perform auto-logout."""
        if not self._current_user:
            return

        messagebox.showinfo(
            "Session Expired",
            "Your session has expired due to inactivity. Please log in again.",
            parent=self._active_root
        )
        _logout_and_return(self._active_root)


# ===========================================================================
# Helper widgets
# ===========================================================================

class _PlaceholderEntry(tk.Entry):
    """
    A tk.Entry subclass that shows placeholder (hint) text in a muted colour
    and clears it when the field receives focus.
    """

    def __init__(self, master, placeholder: str, show_char: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self._placeholder = placeholder
        self._show_char = show_char
        self._is_empty = True

        self._set_placeholder()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _set_placeholder(self):
        self.config(fg=TEXT_SECONDARY, show="")
        self.insert(0, self._placeholder)

    def _on_focus_in(self, _event=None):
        if self._is_empty:
            self.delete(0, tk.END)
            self.config(fg=TEXT_PRIMARY,
                        show=self._show_char if self._show_char else "")
            self._is_empty = False

    def _on_focus_out(self, _event=None):
        if not self.get():
            self._is_empty = True
            self._set_placeholder()

    def get_value(self) -> str:
        """Return the actual value, ignoring the placeholder text."""
        return "" if self._is_empty else self.get()


# ===========================================================================
# LoginWindow
# ===========================================================================

class LoginWindow:
    """
    The HCBS Login screen.

    Displays the branding header, username and password fields, and a Login
    button. On successful authentication the window is destroyed and the
    appropriate role-based window is launched.

    Parameters
    ----------
    root : tk.Tk
        The Tkinter root window passed in from ``main.py``.
    """

    MIN_W = 1024
    MIN_H = 768

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = SessionManager.get_instance()

        self._configure_root()
        self._build_ui()

    # ------------------------------------------------------------------
    # Window configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        """Set global root window properties."""
        self.root.title("HCBS — Horizon Cinemas Booking System")
        self.root.minsize(self.MIN_W, self.MIN_H)
        self.root.configure(bg=BG_PRIMARY)
        self.root.resizable(True, True)
        try:
            self.root.option_add('*Button.cursor', 'hand2')
        except Exception:
            pass

        # Centre on screen
        self.root.update_idletasks()
        w, h = self.MIN_W, self.MIN_H
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build all UI widgets."""
        # ── Root grid ──────────────────────────────────────────────────
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ── Outer wrapper (centres card vertically & horizontally) ─────
        outer = tk.Frame(self.root, bg=BG_PRIMARY)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        # ── Card ───────────────────────────────────────────────────────
        card = tk.Frame(
            outer,
            bg=BG_CARD,
            padx=48,
            pady=48,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.grid(row=0, column=0, ipadx=0, ipady=0)
        card.columnconfigure(0, weight=1)

        # ── Logo / Icon area ───────────────────────────────────────────
        icon_lbl = tk.Label(
            card,
            text="🎬",
            font=(FONT_FAMILY, 38),
            bg=BG_CARD,
            fg=ACCENT
        )
        icon_lbl.grid(row=0, column=0, pady=(0, 8))

        # ── Title ──────────────────────────────────────────────────────
        title_lbl = tk.Label(
            card,
            text="Horizon Cinemas Booking System",
            font=FONT_H1,
            bg=BG_CARD,
            fg=TEXT_PRIMARY
        )
        title_lbl.grid(row=1, column=0, pady=(0, 4))

        # ── Subtitle ───────────────────────────────────────────────────
        sub_lbl = tk.Label(
            card,
            text="Staff Login",
            font=FONT_H2,
            bg=BG_CARD,
            fg=TEXT_SECONDARY
        )
        sub_lbl.grid(row=2, column=0, pady=(0, 28))

        # ── Divider ────────────────────────────────────────────────────
        tk.Frame(card, bg=BORDER, height=1, width=360).grid(
            row=3, column=0, pady=(0, 28), sticky="ew"
        )

        # ── Form frame ─────────────────────────────────────────────────
        form = tk.Frame(card, bg=BG_CARD)
        form.grid(row=4, column=0, sticky="ew")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=0)

        # Username label
        tk.Label(
            form,
            text="Username",
            font=FONT_LABEL,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        # Username entry
        self.username_var = tk.StringVar()
        self.username_entry = self._make_entry(form, textvariable=self.username_var)
        self.username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 16), ipady=8)
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus_set())

        # Password label
        tk.Label(
            form,
            text="Password",
            font=FONT_LABEL,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            anchor="w"
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))

        # Password entry
        self.password_var = tk.StringVar()
        self.password_entry = self._make_entry(
            form, textvariable=self.password_var, show="*"
        )
        self.password_entry.grid(row=3, column=0, sticky="ew", pady=(0, 8), ipady=8)
        self.password_visible = False
        self.password_toggle_btn = tk.Button(
            form,
            text="👁",
            font=(FONT_FAMILY, 12),
            bg=BG_SECONDARY,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            cursor="hand2",
            width=3,
            command=self._toggle_password_visibility
        )
        self.password_toggle_btn.grid(row=3, column=1, sticky="e", padx=(10, 0), pady=(0, 8), ipady=6)
        self.password_entry.bind("<Return>", lambda e: self._on_login_click())

        # ── Error label (hidden until needed) ─────────────────────────
        self.error_lbl = tk.Label(
            form,
            text="",
            font=FONT_SMALL,
            bg=BG_CARD,
            fg=ERROR,
            anchor="w",
            wraplength=360
        )
        self.error_lbl.grid(row=4, column=0, sticky="w", pady=(0, 12))

        # ── Login button ───────────────────────────────────────────────
        self.login_btn = tk.Button(
            form,
            text="Login",
            font=FONT_LABEL,
            bg=ACCENT,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            cursor="hand2",
            width=32,
            pady=10,
            command=self._on_login_click
        )
        self.login_btn.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        self.login_btn.bind("<Enter>", lambda e: self.login_btn.config(bg=ACCENT_HOVER))
        self.login_btn.bind("<Leave>", lambda e: self.login_btn.config(bg=ACCENT))

        # ── Loading indicator (hidden until login is in progress) ──────
        self.loading_lbl = tk.Label(
            form,
            text="⏳  Authenticating, please wait…",
            font=FONT_SMALL,
            bg=BG_CARD,
            fg=TEXT_SECONDARY
        )
        # Not gridded yet — shown dynamically

        # ── Footer ─────────────────────────────────────────────────────
        tk.Label(
            card,
            text="© 2026 Horizon Cinemas · Authorised personnel only",
            font=FONT_SMALL,
            bg=BG_CARD,
            fg=TEXT_SECONDARY
        ).grid(row=5, column=0, pady=(28, 0))

        # Give focus to username field
        self.username_entry.focus_set()

    def _make_entry(self, parent, **kwargs) -> tk.Entry:
        """
        Create a consistently styled tk.Entry widget.

        Args:
            parent: The parent widget.
            **kwargs: Extra keyword arguments forwarded to tk.Entry.

        Returns:
            tk.Entry: The configured entry widget.
        """
        entry = tk.Entry(
            parent,
            font=FONT_BODY,
            bg=BG_SECONDARY,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
            highlightcolor=ACCENT,
            **kwargs
        )
        entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground=ACCENT))
        entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground=BORDER))
        return entry

    # ------------------------------------------------------------------
    # Login logic
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        """Display the error label with a given message."""
        self.error_lbl.config(text=f"⚠  {message}")

    def _clear_error(self) -> None:
        """Clear any previously displayed error message."""
        self.error_lbl.config(text="")

    def _toggle_password_visibility(self) -> None:
        """Toggle whether the password field is masked."""
        self.password_visible = not self.password_visible
        self.password_entry.config(show="" if self.password_visible else "*")
        self.password_toggle_btn.config(text="🙈" if self.password_visible else "👁")
        self.password_entry.focus_set()

    def _set_loading(self, loading: bool) -> None:
        """
        Toggle the loading state of the login form.

        Disables the button and shows the loading label while authentication
        is in progress to prevent duplicate submissions.

        Args:
            loading (bool): True to show loading state; False to restore.
        """
        if loading:
            self.login_btn.config(state="disabled", text="Logging in…", bg=BORDER)
            self.loading_lbl.grid(row=6, column=0, sticky="w", pady=(8, 0))
        else:
            self.login_btn.config(state="normal", text="Login", bg=ACCENT)
            self.loading_lbl.grid_remove()

    def _on_login_click(self) -> None:
        """
        Handle the Login button click or Enter key press.

        Validates that both fields are populated, then spawns a background
        thread to perform bcrypt verification (which is CPU-intensive) so
        the Tkinter main thread remains responsive during authentication.
        """
        self._clear_error()

        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username:
            self._show_error("Please enter your username.")
            self.username_entry.focus_set()
            return
        if not password:
            self._show_error("Please enter your password.")
            self.password_entry.focus_set()
            return

        self._set_loading(True)

        # Run authentication in a background thread so the UI doesn't freeze
        thread = threading.Thread(
            target=self._authenticate,
            args=(username, password),
            daemon=True
        )
        thread.start()

    def _authenticate(self, username: str, password: str) -> None:
        """
        Perform authentication in a background thread.

        On completion, schedules the result handler back on the main thread
        via ``root.after(0, ...)`` — required for Tkinter thread safety.

        Args:
            username (str): Username entered by the user.
            password (str): Plaintext password entered by the user.
        """
        try:
            from src.models.user import User
            conn = self.session.get_db_connection()
            user = User.login(username, password, conn)
            # Schedule success handler on main thread
            self.root.after(0, self._on_login_success, user)
        except Exception as exc:
            # Schedule failure handler on main thread
            self.root.after(0, self._on_login_failure, str(exc))

    def _on_login_success(self, user) -> None:
        """
        Called on the main thread after successful authentication.

        Stores the user in the session and routes to the correct role window.

        Args:
            user: The authenticated ``User`` object.
        """
        self._set_loading(False)
        self.session.set_current_user(user)

        # Destroy the login window and launch the role-appropriate dashboard
        self.root.destroy()

        new_root = tk.Tk()
        self.session.register_root(new_root)
        if user.is_manager:
            _get_manager_window()(new_root)
        elif user.is_admin:
            _get_admin_window()(new_root)
        else:
            _get_staff_window()(new_root)
        new_root.mainloop()

    def _on_login_failure(self, message: str) -> None:
        """
        Called on the main thread after a failed authentication attempt.

        Restores the form to its interactive state and displays the error.

        Args:
            message (str): The error message from the AuthenticationError.
        """
        self._set_loading(False)
        # Always show a generic message to the user (avoids leaking info)
        self._show_error("Invalid username or password.")
        self.password_var.set("")
        self.password_entry.focus_set()


# ===========================================================================
# Standalone entry point (for testing this window in isolation)
# ===========================================================================

def _logout_and_return(window_root: tk.Tk) -> None:
    """
    Utility called by role windows to log out and return to the Login screen.

    Import and call this from ManagerWindow, AdminWindow, and StaffWindow
    inside their own logout buttons::

        from src.gui.login_window import _logout_and_return
        logout_btn = tk.Button(..., command=lambda: _logout_and_return(self.root))

    Args:
        window_root (tk.Tk): The Tk root of the currently open role window.
    """
    session = SessionManager.get_instance()
    session.clear_session()
    window_root.destroy()

    new_root = tk.Tk()
    LoginWindow(new_root)
    new_root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()
