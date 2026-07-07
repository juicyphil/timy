import csv
import io

TYPE_NAMES_REVERSE = {
    "Urlaub": "vacation",
    "Krank": "sick",
    "Feiertag": "holiday",
    "BBS": "bbs",
    "Überstunden Abbau": "ueberstunden_abbau",
    "Sonstige": "other"
}

def import_times_csv(conn, content, user_id):
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    for row in reader:
        date = row.get("Datum", "").strip()
        clock_in = row.get("Kommen", "").strip() or None
        clock_out = row.get("Gehen", "").strip() or None
        pause_start = row.get("Pause Start", "").strip() or None
        pause_end = row.get("Pause Ende", "").strip() or None
        note = row.get("Notiz", "").strip()

        if not date:
            continue

        conn.execute(
            "DELETE FROM time_entries WHERE date=? AND clock_in=? AND user_id=?",
            (date, clock_in, user_id)
        )
        conn.execute(
            "INSERT INTO time_entries (date, clock_in, clock_out, pause_start, pause_end, note, is_manual, user_id) VALUES (?,?,?,?,?,?,1,?)",
            (date, clock_in, clock_out, pause_start, pause_end, note, user_id)
        )
        imported += 1
    return imported

def import_absences_csv(conn, content, user_id):
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    for row in reader:
        type_label = row.get("Typ", "").strip()
        start_date = row.get("Start", "").strip()
        end_date = row.get("Ende", "").strip()
        days_str = row.get("Tage", "").strip()
        note = row.get("Notiz", "").strip()

        if not start_date or not end_date or not type_label:
            continue

        absence_type = TYPE_NAMES_REVERSE.get(type_label, type_label)
        try:
            days = float(days_str) if days_str else 1.0
        except ValueError:
            days = 1.0

        conn.execute(
            "DELETE FROM absences WHERE type=? AND start_date=? AND end_date=? AND user_id=?",
            (absence_type, start_date, end_date, user_id)
        )
        conn.execute(
            "INSERT INTO absences (type, start_date, end_date, days, note, user_id) VALUES (?,?,?,?,?,?)",
            (absence_type, start_date, end_date, days, note, user_id)
        )
        imported += 1
    return imported
