import sqlite3
import os
import hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "timy.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. Create Phil user
    ph = hashlib.sha256("0000".encode()).hexdigest()
    try:
        conn.execute("INSERT INTO users (name, pin_hash) VALUES (?, ?)", ("Phil", ph))
        print("User 'Phil' angelegt")
    except sqlite3.IntegrityError:
        print("User 'Phil' existiert bereits")

    phil = conn.execute("SELECT id FROM users WHERE name='Phil'").fetchone()
    phil_id = phil["id"]

    # 2. Count existing data
    time_count = conn.execute("SELECT COUNT(*) as c FROM time_entries WHERE user_id=1").fetchone()["c"]
    abs_count = conn.execute("SELECT COUNT(*) as c FROM absences WHERE user_id=1").fetchone()["c"]
    print(f"Gefunden: {time_count} Zeiteinträge, {abs_count} Abwesenheiten bei user_id=1")

    # 3. Set start_date to 1 June 2026
    conn.execute("UPDATE users SET start_date=? WHERE name='Phil'", ("2026-06-01",))
    # 4. Set start_date = created_at for all other users (if not already set)
    conn.execute("UPDATE users SET start_date=substr(created_at,1,10) WHERE start_date IS NULL")
    print(f"Startdate gesetzt: Phil → 2026-06-01, andere → created_at")

    # 5. Migrate time_entries
    conn.execute("UPDATE time_entries SET user_id=? WHERE user_id=1", (phil_id,))
    # 6. Migrate absences
    conn.execute("UPDATE absences SET user_id=? WHERE user_id=1", (phil_id,))

    conn.commit()
    migrated_t = conn.execute("SELECT COUNT(*) as c FROM time_entries WHERE user_id=?", (phil_id,)).fetchone()["c"]
    migrated_a = conn.execute("SELECT COUNT(*) as c FROM absences WHERE user_id=?", (phil_id,)).fetchone()["c"]
    print(f"Migriert: {migrated_t} Zeiteinträge, {migrated_a} Abwesenheiten → User 'Phil' (id={phil_id})")
    conn.close()

if __name__ == "__main__":
    migrate()
