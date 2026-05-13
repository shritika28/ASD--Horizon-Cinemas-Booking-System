"""
src/models/user.py
==================
User model for the Horizon Cinemas Booking System (HCBS).

Provides the User class which maps to the `users` table in the SQLite database,
as well as a custom AuthenticationError exception for failed login attempts.
"""

import bcrypt
import datetime
import sqlite3
from typing import Optional

from src.database.db_connection import get_connection


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class AuthenticationError(Exception):
    """
    Raised when a user authentication attempt fails.

    This can occur due to:
    - A username that does not exist in the database.
    - An incorrect password being supplied.
    - The account being marked as inactive.
    """

    def __init__(self, message: str = "Authentication failed. Invalid credentials.") -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# User Model
# ---------------------------------------------------------------------------

class User:
    """
    Represents an authenticated HCBS system user.

    Maps to the `users` table in the SQLite database. Supports three roles
    with different levels of access:
    - **Manager**: Full system access, including reports and admin management.
    - **Admin**: Can manage films, showings, and customers.
    - **Staff**: Can create and view bookings only.

    Attributes:
        user_id (int): Unique identifier for the user.
        cinema_id (Optional[int]): The cinema this user is associated with.
        username (str): Unique login username.
        password_hash (str): bcrypt-hashed password string.
        full_name (str): The user's display name.
        email (str): The user's email address.
        role (str): One of 'manager', 'admin', or 'staff'.
        theme_pref (str): UI theme preference, e.g. 'dark' or 'light'.
        is_active (bool): Whether the account is currently active.
        last_login (Optional[str]): ISO-format datetime of last successful login.
    """

    VALID_ROLES = ('manager', 'admin', 'staff')

    def __init__(
        self,
        user_id: int,
        cinema_id: Optional[int],
        username: str,
        password_hash: str,
        full_name: str,
        email: str,
        role: str,
        theme_pref: str = 'dark',
        is_active: bool = True,
        last_login: Optional[str] = None
    ) -> None:
        """
        Initialise a User instance.

        Args:
            user_id (int): Primary key from the users table.
            cinema_id (Optional[int]): FK to the cinemas table; may be None for managers.
            username (str): The user's unique login name.
            password_hash (str): The bcrypt-hashed password stored in the database.
            full_name (str): Human-readable display name.
            email (str): The user's email address.
            role (str): Access role — must be one of 'manager', 'admin', or 'staff'.
            theme_pref (str): GUI theme preference. Defaults to 'dark'.
            is_active (bool): Account active flag. Defaults to True.
            last_login (Optional[str]): ISO-format datetime string of last login.

        Raises:
            ValueError: If the provided role is not a valid HCBS role.
        """
        if role.lower() not in self.VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {', '.join(self.VALID_ROLES)}"
            )

        self.user_id: int = user_id
        self.cinema_id: Optional[int] = cinema_id
        self.username: str = username
        self.password_hash: str = password_hash
        self.full_name: str = full_name
        self.email: str = email
        self.role: str = role.lower()
        self.theme_pref: str = theme_pref
        self.is_active: bool = bool(is_active)
        self.last_login: Optional[str] = last_login

        # Runtime session flag; not persisted
        self._logged_in: bool = False

    # -----------------------------------------------------------------------
    # Static Methods
    # -----------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plaintext password using bcrypt.

        Generates a new salt on every call, so two hashes of the same password
        will always differ. Use this when creating or updating a user's password.

        Args:
            password (str): The plaintext password to hash.

        Returns:
            str: A bcrypt-hashed password string suitable for database storage.

        Example:
            >>> hashed = User.hash_password("supersecret")
            >>> isinstance(hashed, str)
            True
        """
        password_bytes: bytes = password.encode('utf-8')
        salt: bytes = bcrypt.gensalt()
        hashed: bytes = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_text: str, hashed: str) -> bool:
        """
        Verify a plaintext password against a stored bcrypt hash.

        Args:
            plain_text (str): The password entered by the user.
            hashed (str): The bcrypt hash stored in the database.

        Returns:
            bool: True if the password matches the hash, False otherwise.
        """
        try:
            return bcrypt.checkpw(plain_text.encode('utf-8'), hashed.encode('utf-8'))
        except ValueError:
            # Raised if 'hashed' is not a valid bcrypt hash format
            return False

    @staticmethod
    def login(username: str, password: str, db_connection: sqlite3.Connection) -> "User":
        """
        Authenticate a user against the database and return a User object.

        Queries the `users` table for a matching username, verifies the supplied
        password against the stored bcrypt hash, checks the account is active, then
        updates the `last_login` timestamp before returning a populated User instance.

        Args:
            username (str): The username supplied at the login screen.
            password (str): The plaintext password supplied at the login screen.
            db_connection (sqlite3.Connection): An active SQLite database connection.

        Returns:
            User: A fully populated User object representing the authenticated user.

        Raises:
            AuthenticationError: If the username is not found, the password does not
                                 match, or the account has been deactivated.

        Example:
            >>> import sqlite3
            >>> conn = sqlite3.connect("hcbs.db")
            >>> user = User.login("staff1", "password123", conn)
            >>> print(user.role)
            'staff'
        """
        cursor: sqlite3.Cursor = db_connection.cursor()

        cursor.execute(
            """
            SELECT user_id, cinema_id, username, password_hash,
                   full_name, email, role, theme_pref, is_active, last_login
            FROM   users
            WHERE  username = ?
            """,
            (username,)
        )
        row = cursor.fetchone()

        if row is None:
            raise AuthenticationError(f"No account found with username '{username}'.")

        (user_id, cinema_id, db_username, password_hash,
         full_name, email, role, theme_pref, is_active, last_login) = row

        # Verify password
        password_matches: bool = User.verify_password(password, password_hash)
        if not password_matches:
            raise AuthenticationError("Incorrect password. Please try again.")

        # Check active flag
        if not bool(is_active):
            raise AuthenticationError(
                f"Account '{username}' has been deactivated. Contact your manager."
            )

        # Update last_login timestamp
        now: str = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE user_id = ?",
            (now, user_id)
        )
        db_connection.commit()

        user = User(
            user_id=user_id,
            cinema_id=cinema_id,
            username=db_username,
            password_hash=password_hash,
            full_name=full_name if full_name else db_username,
            email=email if email else '',
            role=role,
            theme_pref=theme_pref if theme_pref else 'dark',
            is_active=bool(is_active),
            last_login=now
        )
        user._logged_in = True
        return user

    @staticmethod
    def create_user(username: str, password: str, full_name: str, email: str,
                    role: str, cinema_id: Optional[int] = None) -> None:
        """Create a new user in the database."""
        if role.lower() not in User.VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(User.VALID_ROLES)}")

        conn = get_connection()

        # Check if username exists
        existing = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise ValueError(f"Username '{username}' already exists.")

        hashed = User.hash_password(password)
        conn.execute(
            """
            INSERT INTO users (cinema_id, username, password_hash, full_name, email, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (cinema_id, username, hashed, full_name, email, role.lower())
        )
        conn.commit()

    @staticmethod
    def get_users_by_role(role: str) -> list:
        """Fetch all users of a specific role."""
        conn = get_connection()

        query = """
            SELECT u.user_id, u.username, u.full_name, u.email, u.is_active, c.cinema_name
            FROM users u
            LEFT JOIN cinemas c ON u.cinema_id = c.cinema_id
            WHERE u.role = ?
            ORDER BY u.username
        """
        rows = conn.execute(query, (role.lower(),)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def delete_user(user_id: int) -> bool:
        """Permanently delete a user from the database."""
        try:
            conn = get_connection()
            # Do not allow deleting the last manager or the current user (handled in GUI)
            cursor = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    # -----------------------------------------------------------------------
    # Role Properties
    # -----------------------------------------------------------------------

    @property
    def is_manager(self) -> bool:
        """
        Check if the user has Manager-level access.

        Returns:
            bool: True only if the user's role is 'manager'.
        """
        return self.role == 'manager'

    @property
    def is_admin(self) -> bool:
        """
        Check if the user has Admin-level access or higher.

        Both 'manager' and 'admin' roles have admin-level privileges.

        Returns:
            bool: True if the user's role is 'manager' or 'admin'.
        """
        return self.role in ('manager', 'admin')

    @property
    def is_staff(self) -> bool:
        """
        Check if the user is an active HCBS system user.

        All valid roles ('manager', 'admin', 'staff') are considered staff
        members of the system.

        Returns:
            bool: Always True for any valid User instance.
        """
        return self.role in self.VALID_ROLES

    # -----------------------------------------------------------------------
    # Session Management
    # -----------------------------------------------------------------------

    def logout(self) -> None:
        """
        Clear the user's active session.

        Sets the internal ``_logged_in`` flag to False. In the GUI layer, this
        should be followed by destroying the main application window and
        returning to the login screen.

        Example:
            >>> user.logout()
            >>> user._logged_in
            False
        """
        self._logged_in = False

    # -----------------------------------------------------------------------
    # Dunder Methods
    # -----------------------------------------------------------------------

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation of the User.

        Returns:
            str: A string showing the user_id, username, role, and active status.

        Example:
            >>> repr(user)
            "User(id=1, username='staff1', role='staff', active=True)"
        """
        return (
            f"User(id={self.user_id}, username={self.username!r}, "
            f"role={self.role!r}, active={self.is_active})"
        )

    def __str__(self) -> str:
        """
        Return a human-readable string representation of the User.

        Returns:
            str: The user's full name and role, formatted for display.
        """
        return f"{self.full_name} ({self.role.capitalize()})"
