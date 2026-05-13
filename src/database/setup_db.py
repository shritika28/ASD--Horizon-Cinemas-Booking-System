import sqlite3
import bcrypt
import datetime
import random

DB_PATH = 'hcbs.db'


def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_tables(cursor):
    cursor.executescript("""
    DROP TABLE IF EXISTS tickets;
    DROP TABLE IF EXISTS waitlist;
    DROP TABLE IF EXISTS bookings;
    DROP TABLE IF EXISTS agent_logs;
    DROP TABLE IF EXISTS loyalty_points;
    DROP TABLE IF EXISTS prices;
    DROP TABLE IF EXISTS showings;
    DROP TABLE IF EXISTS films;
    DROP TABLE IF EXISTS screens;
    DROP TABLE IF EXISTS cinemas;
    DROP TABLE IF EXISTS cities;
    DROP TABLE IF EXISTS users;

    CREATE TABLE cities (
        city_id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_name TEXT NOT NULL
    );

    CREATE TABLE cinemas (
        cinema_id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER,
        cinema_name TEXT NOT NULL,
        FOREIGN KEY(city_id) REFERENCES cities(city_id)
    );

    CREATE TABLE screens (
        screen_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cinema_id INTEGER,
        screen_number INTEGER NOT NULL,
        total_capacity INTEGER NOT NULL,
        lower_hall_seats INTEGER NOT NULL,
        upper_gallery_seats INTEGER NOT NULL,
        vip_seats INTEGER NOT NULL,
        FOREIGN KEY(cinema_id) REFERENCES cinemas(cinema_id)
    );

    CREATE TABLE films (
        film_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        genre TEXT NOT NULL,
        age_rating TEXT NOT NULL,
        duration_mins INTEGER NOT NULL,
        imdb_rating REAL,
        cast_members TEXT DEFAULT '',
        poster_path TEXT DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE showings (
        showing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        film_id INTEGER,
        screen_id INTEGER,
        show_date TEXT NOT NULL,
        show_time TEXT NOT NULL,
        show_type TEXT NOT NULL,
        seats_remaining INTEGER NOT NULL,
        is_cancelled INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(film_id) REFERENCES films(film_id),
        FOREIGN KEY(screen_id) REFERENCES screens(screen_id)
    );

    CREATE TABLE prices (
        price_id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER,
        show_type TEXT NOT NULL,
        lower_hall_price REAL NOT NULL,
        effective_from TEXT NOT NULL,
        FOREIGN KEY(city_id) REFERENCES cities(city_id)
    );

    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cinema_id INTEGER,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        theme_pref TEXT NOT NULL DEFAULT 'dark',
        is_active INTEGER NOT NULL DEFAULT 1,
        last_login TEXT,
        FOREIGN KEY(cinema_id) REFERENCES cinemas(cinema_id)
    );

    CREATE TABLE bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        showing_id INTEGER,
        booking_ref TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT DEFAULT '',
        total_cost REAL NOT NULL,
        booking_status TEXT NOT NULL,
        booked_by_agent BOOLEAN NOT NULL,
        cancellation_fee REAL DEFAULT 0.00,
        cancelled_at TEXT,
        staff_id INTEGER DEFAULT 1,
        booking_time TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(showing_id) REFERENCES showings(showing_id),
        FOREIGN KEY(staff_id) REFERENCES users(user_id)
    );

    CREATE TABLE tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER,
        seat_number TEXT NOT NULL,
        ticket_type TEXT NOT NULL,
        unit_price REAL NOT NULL,
        pdf_path TEXT,
        FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
    );

    CREATE TABLE waitlist (
        waitlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
        showing_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        num_tickets INTEGER NOT NULL,
        joined_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting', -- 'waiting', 'offered', 'confirmed', 'expired'
        offered_at TEXT,
        FOREIGN KEY (showing_id) REFERENCES showings(showing_id)
    );

    CREATE TABLE loyalty_points (
        loyalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT UNIQUE NOT NULL,
        points INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE agent_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        tool_input TEXT NOT NULL,
        tool_output TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)


def seed_data(conn_or_cursor):
    # If passed a connection, get a cursor. Connection.execute returns a cursor,
    # but Connection itself doesn't have fetchall/fetchone.
    if hasattr(conn_or_cursor, 'cursor') and not hasattr(conn_or_cursor, 'fetchall'):
        cursor = conn_or_cursor.cursor()
    else:
        cursor = conn_or_cursor

    # 1. Cities
    cities = ['Birmingham', 'Bristol', 'Cardiff', 'London']
    for city in cities:
        cursor.execute("INSERT INTO cities (city_name) VALUES (?)", (city,))

    # 2. Cinemas
    cinemas_data = [
        (1, 'Horizon Birmingham Central'), (1, 'Horizon Birmingham South'),
        (2, 'Horizon Bristol East'), (2, 'Horizon Bristol West'),
        (3, 'Horizon Cardiff Bay'), (3, 'Horizon Cardiff North'),
        (4, 'Horizon London West End'), (4, 'Horizon London Stratford')
    ]
    cursor.executemany("INSERT INTO cinemas (city_id, cinema_name) VALUES (?, ?)", cinemas_data)

    # 3. Screens
    screens_data = []
    for cinema_id in range(1, 9):
        for screen_num in range(1, 4):  # 3 screens per cinema
            total = random.randint(50, 120)
            vip = random.randint(5, 10)
            lower = int(total * 0.3)
            upper = total - vip - lower
            screens_data.append((cinema_id, screen_num, total, lower, upper, vip))
    cursor.executemany("""
        INSERT INTO screens (cinema_id, screen_number, total_capacity, lower_hall_seats, upper_gallery_seats, vip_seats)
        VALUES (?, ?, ?, ?, ?, ?)
    """, screens_data)

    # 4. Films (poster_path is relative to project root; add files under assets/posters/)
    films_data = [
        ('The Matrix Awakens', 'The simulation continues.', 'Sci-Fi', '15', 140, 7.9,
         'Keanu Reeves, Carrie-Anne Moss', 'assets/posters/matrix_awakens.jpg'),
        ('Inception: Restart', 'Dreams within dreams return.', 'Sci-Fi', '12A', 152, 8.1,
         'Leonardo DiCaprio, Elliot Page', 'assets/posters/inception_restart.jpg'),
        ('Toy Story 5', 'The toys are back for another adventure.', 'Animation', 'U', 98, 7.5,
         'Tom Hanks, Tim Allen', 'assets/posters/toy_story_5.jpg'),
        ('Avengers: Next Gen', 'Earth mightiest heroes assemble again.', 'Action', '12A', 165, 8.0,
         'Samuel L. Jackson', 'assets/posters/avengers_next_gen.jpg'),
        ('The Silent Echo', 'Some sounds should stay unheard.', 'Horror', '18', 110, 6.8,
         'Florence Pugh', 'assets/posters/silent_echo.jpg'),
        ('Love in Paris', 'A romantic escape along the Seine.', 'Romance', 'PG', 105, 7.2,
         'Emma Stone', 'assets/posters/love_paris.jpg'),
        ('Desert Storm', 'One mission. No turning back.', 'Action', '15', 130, 7.0,
         'Idris Elba', 'assets/posters/desert_storm.jpg'),
        ('Ocean Planet', 'Blue worlds beneath the waves.', 'Documentary', 'U', 85, 8.4,
         'David Attenborough', 'assets/posters/ocean_planet.jpg'),
    ]
    cursor.executemany("""
        INSERT INTO films (title, description, genre, age_rating, duration_mins,
            imdb_rating, cast_members, poster_path, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, films_data)

    # 5. Prices
    today = datetime.date.today().isoformat()
    prices_data = [
        # Birmingham
        (1, 'morning', 5.0, today), (1, 'afternoon', 6.0, today), (1, 'evening', 7.0, today),
        # Bristol
        (2, 'morning', 6.0, today), (2, 'afternoon', 7.0, today), (2, 'evening', 8.0, today),
        # Cardiff
        (3, 'morning', 5.0, today), (3, 'afternoon', 6.0, today), (3, 'evening', 7.0, today),
        # London
        (4, 'morning', 10.0, today), (4, 'afternoon', 11.0, today), (4, 'evening', 12.0, today)
    ]
    cursor.executemany("""
        INSERT INTO prices (city_id, show_type, lower_hall_price, effective_from)
        VALUES (?, ?, ?, ?)
    """, prices_data)

    # 6. Users (cinema_id, username, password_hash, full_name, email, role, theme_pref, is_active)
    users_data = [
        (None, 'manager1', hash_password('password123'), 'Alice Manager', 'alice@hcbs.com', 'manager', 'dark', 1),
        (1, 'admin1', hash_password('password123'), 'Bob Admin', 'bob@hcbs.com', 'admin', 'dark', 1),
        (5, 'admin2', hash_password('password123'), 'Carol Admin', 'carol@hcbs.com', 'admin', 'light', 1),
        (2, 'staff1', hash_password('password123'), 'Dave Staff', 'dave@hcbs.com', 'staff', 'dark', 1),
        (3, 'staff2', hash_password('password123'), 'Eve Staff', 'eve@hcbs.com', 'staff', 'dark', 1),
        (7, 'staff3', hash_password('password123'), 'Frank Staff', 'frank@hcbs.com', 'staff', 'light', 1),
    ]
    cursor.executemany("""
        INSERT INTO users (cinema_id, username, password_hash, full_name, email, role, theme_pref, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, users_data)

    # 7. Create showings for the next 7 days (including Today)
    print("Seeding showings for the next 7 days...")
    show_types_times = [('morning', '10:00'), ('afternoon', '14:30'), ('evening', '19:00')]
    future_showings = []
    film_idx = 0

    res = cursor.execute("SELECT screen_id, total_capacity FROM screens ORDER BY screen_id")
    all_screens = res.fetchall()
    films_list = list(range(1, 9))

    for d_offset in range(8):  # Today + next 7 days
        target_date = (datetime.date.today() + datetime.timedelta(days=d_offset)).isoformat()
        for screen_id, capacity in all_screens:
            for show_type, show_time in show_types_times:
                film_id = films_list[film_idx % len(films_list)]
                future_showings.append((film_id, screen_id, target_date, show_time, show_type, capacity))
                film_idx += 1

    cursor.executemany("""
        INSERT INTO showings (film_id, screen_id, show_date, show_time, show_type, seats_remaining)
        VALUES (?, ?, ?, ?, ?, ?)
    """, future_showings)

    # 8. Create historical showings (past 6 months) for reports
    print("Seeding historical showings for reports...")
    historical_showings = []
    base_date = datetime.date.today()
    for i in range(1, 181):  # 6 months
        past_date = (base_date - datetime.timedelta(days=i)).isoformat()
        for screen_id, capacity in all_screens:
            stype, stime = random.choice(show_types_times)
            film_id = random.randint(1, 8)
            historical_showings.append((film_id, screen_id, past_date, stime, stype, capacity))

    cursor.executemany("""
        INSERT INTO showings (film_id, screen_id, show_date, show_time, show_type, seats_remaining)
        VALUES (?, ?, ?, ?, ?, ?)
    """, historical_showings)

    # 9. Create bookings and tickets for reports (past 6 months)
    print("Seeding bookings and tickets for reports...")
    cursor.execute("SELECT showing_id, screen_id FROM showings WHERE show_date < ?", (today,))
    past_showings = cursor.fetchall()

    booking_ref_counter = 1
    staff_ids = [4, 5, 6]  # staff1, staff2, staff3 user IDs

    for showing_id, screen_id in past_showings:  # Seed all past showings
        # Create 1-3 bookings per showing
        num_bookings = random.randint(1, 3)
        for _ in range(num_bookings):
            customer_name = f"Customer_{random.randint(1000, 9999)}"
            booking_ref = f"HCBS-{today}-{booking_ref_counter:04d}"
            booking_ref_counter += 1

            staff_id = random.choice(staff_ids)

            # Determine prices by show_type
            cursor.execute("SELECT show_type FROM showings WHERE showing_id = ?", (showing_id,))
            show_type = cursor.fetchone()[0]

            cursor.execute("""
                SELECT s.screen_id FROM showings s WHERE s.showing_id = ?
            """, (showing_id,))
            scr = cursor.fetchone()
            if not scr:
                continue

            # Get screen capacity to determine seat distribution
            cursor.execute("SELECT total_capacity FROM screens WHERE screen_id = ?", (scr[0],))
            cap_row = cursor.fetchone()
            if not cap_row:
                continue
            capacity = cap_row[0]

            # Random number of tickets (1-5)
            num_tickets = random.randint(1, min(5, capacity))

            # Calculate price
            cursor.execute("""
                SELECT sp.screen_id, c.city_id FROM screens sp
                JOIN cinemas c ON sp.cinema_id = c.cinema_id
                WHERE sp.screen_id = ?
            """, (scr[0],))
            screen_info = cursor.fetchone()
            if not screen_info:
                continue
            city_id = screen_info[1]

            cursor.execute("""
                SELECT lower_hall_price FROM prices
                WHERE city_id = ? AND show_type = ?
            """, (city_id, show_type))
            price_row = cursor.fetchone()
            base_price = price_row[0] if price_row else 5.0

            total_cost = base_price * num_tickets

            # Approximate booking time as 1 day before showing or Today if showing is today
            showing_date_res = cursor.execute(
                "SELECT show_date FROM showings WHERE showing_id = ?", (showing_id,)).fetchone()
            showing_date = datetime.date.fromisoformat(showing_date_res[0])
            booking_time = (showing_date - datetime.timedelta(days=random.randint(0, 7))).isoformat() + " 12:00:00"

            cursor.execute("""
                INSERT INTO bookings
                (
                    showing_id, booking_ref, customer_name, total_cost,
                    booking_status, booked_by_agent, staff_id, booking_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                showing_id, booking_ref, customer_name, total_cost,
                'Active', 1, staff_id, booking_time
            ))

            booking_id = cursor.lastrowid

            # Create tickets
            ticket_types = ['lower_hall'] * max(1, int(num_tickets * 0.6)) + \
                ['upper_gallery'] * max(1, int(num_tickets * 0.3)) + \
                ['vip'] * max(0, num_tickets - max(1, int(num_tickets * 0.6)) -
                              max(1, int(num_tickets * 0.3)))

            for idx, ticket_type in enumerate(ticket_types):
                seat_num = f"{chr(65 + idx // 10)}{idx % 10 + 1}"
                cursor.execute("""
                    INSERT INTO tickets (booking_id, seat_number, ticket_type, unit_price)
                    VALUES (?, ?, ?, ?)
                """, (booking_id, seat_num, ticket_type, base_price))

    # 10. Add waitlist entries
    print("Seeding waitlist...")
    cursor.execute("SELECT showing_id FROM showings WHERE show_date = ? ORDER BY RANDOM() LIMIT 5", (today,))
    today_showings_sample = cursor.fetchall()

    for showing_id, in today_showings_sample:
        for i in range(random.randint(1, 3)):
            now = datetime.datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO waitlist (
                    showing_id, customer_name, customer_email, customer_phone,
                    num_tickets, joined_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (showing_id, f"WaitlistCustomer_{random.randint(1000, 9999)}",
                  f"email_{random.randint(1, 9999)}@example.com", "12345678",
                  random.randint(1, 4), now, 'waiting'))

    # 11. Add loyalty points
    print("Seeding loyalty points...")
    cursor.execute("SELECT DISTINCT customer_name FROM bookings ORDER BY RANDOM() LIMIT 10")
    customers = cursor.fetchall()
    for customer, in customers:
        points = random.randint(50, 500)
        cursor.execute("""
            INSERT INTO loyalty_points (customer_name, points)
            VALUES (?, ?)
        """, (customer, points))

    # 12. Add agent logs
    print("Seeding agent logs...")
    cursor.execute("""
        INSERT INTO agent_logs (session_id, tool_name, tool_input, tool_output)
        VALUES (?, ?, ?, ?)
    """, ('sess_001', 'check_availability', '{"film":"Inception"}', '{"available": true}'))


def main():
    print(f"Creating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    create_tables(cursor)
    print("Tables created successfully.")

    print("Seeding data (this might take a few seconds due to bcrypt)...")
    seed_data(cursor)
    conn.commit()

    # Print summary
    tables = [
        'cities', 'cinemas', 'screens', 'films', 'showings', 'prices',
        'users', 'bookings', 'tickets', 'waitlist', 'loyalty_points', 'agent_logs'
    ]
    print("\n--- Setup Summary ---")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table.ljust(15)}: {count} rows")
    print("---------------------")

    conn.close()
    print("\nDatabase setup complete.")


if __name__ == "__main__":
    main()
