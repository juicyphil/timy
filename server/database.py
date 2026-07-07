import sqlite3
import os
import hashlib

DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "timy.db")

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            clock_in TEXT,
            clock_out TEXT,
            pause_start TEXT,
            pause_end TEXT,
            note TEXT DEFAULT '',
            is_manual INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('vacation','sick','holiday','bbs','other','ueberstunden_abbau')),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days REAL NOT NULL DEFAULT 1.0,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_entries(date);
        CREATE INDEX IF NOT EXISTS idx_absences_dates ON absences(start_date, end_date);
    """)

    defaults = {
        "weekly_hours": "40",
        "vacation_days": "30",
        "employee_name": "Benutzer",
        "pause_duration": "30",
        "friday_hours": "0"
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Migration: add 'bbs' to existing absences table
    try:
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='absences'"
        ).fetchone()
        if schema and 'bbs' not in schema[0]:
            conn.executescript("""
                ALTER TABLE absences RENAME TO absences_old;
                CREATE TABLE absences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('vacation','sick','holiday','bbs','other','ueberstunden_abbau')),
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    days REAL NOT NULL DEFAULT 1.0,
                    note TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                INSERT INTO absences SELECT * FROM absences_old;
                DROP TABLE absences_old;
            """)
    except:
        pass

    # Migration: add 'ueberstunden_abbau' to existing absences table
    try:
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='absences'"
        ).fetchone()
        if schema and 'ueberstunden_abbau' not in schema[0]:
            conn.executescript("""
                ALTER TABLE absences RENAME TO absences_old;
                CREATE TABLE absences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('vacation','sick','holiday','bbs','other','ueberstunden_abbau')),
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    days REAL NOT NULL DEFAULT 1.0,
                    note TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                INSERT INTO absences SELECT * FROM absences_old;
                DROP TABLE absences_old;
            """)
    except:
        pass

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # Migration: add user_id to existing tables
    for table in ['time_entries', 'absences']:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

    # Migration: add role to users table
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass

    # Migration: add start_date to users table
    try:
        conn.execute("ALTER TABLE users ADD COLUMN start_date TEXT")
    except sqlite3.OperationalError:
        pass

    # Default admin user (PIN: 0000)
    if not conn.execute("SELECT id FROM users LIMIT 1").fetchone():
        h = hashlib.sha256("0000".encode()).hexdigest()
        conn.execute("INSERT INTO users (name, pin_hash, role) VALUES (?, ?, ?)", ("Admin", h, "admin"))

    # Migration: set existing Admin user to admin role
    conn.execute("UPDATE users SET role='admin' WHERE name='Admin' AND role='user'")

    # Demo ausbilder account (PIN: 1234)
    if not conn.execute("SELECT id FROM users WHERE name='Ausbilder'").fetchone():
        h = hashlib.sha256("1234".encode()).hexdigest()
        conn.execute("INSERT INTO users (name, pin_hash, role) VALUES (?, ?, ?)", ("Ausbilder", h, "ausbilder"))

    conn.commit()
    conn.close()
