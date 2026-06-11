import sqlite3
import os
import hashlib

DB_PATH = "/app/data/timy.db"

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

    # 3. Migrate time_entries
    conn.execute("UPDATE time_entries SET user_id=? WHERE user_id=1", (phil_id,))
    # 4. Migrate absences
    conn.execute("UPDATE absences SET user_id=? WHERE user_id=1", (phil_id,))

    conn.commit()
    migrated_t = conn.execute("SELECT COUNT(*) as c FROM time_entries WHERE user_id=?", (phil_id,)).fetchone()["c"]
    migrated_a = conn.execute("SELECT COUNT(*) as c FROM absences WHERE user_id=?", (phil_id,)).fetchone()["c"]
    print(f"Migriert: {migrated_t} Zeiteinträge, {migrated_a} Abwesenheiten → User 'Phil' (id={phil_id})")
    conn.close()

if __name__ == "__main__":
    migrate()
