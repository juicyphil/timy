import csv
import io
import re
import zipfile

TYPE_NAMES_REVERSE = {
    "Urlaub": "vacation",
    "Krank": "sick",
    "Feiertag": "holiday",
    "BBS": "bbs",
    "Überstunden Abbau": "ueberstunden_abbau",
    "Sonstige": "other"
}

def _split_sections(content):
    lines = content.split("\n")
    sections = {}
    current_section = None
    current_lines = []

    for line in lines:
        m = re.match(r'^=== (.+) ===\s*$', line.strip())
        if m:
            if current_section:
                sections[current_section] = "\n".join(current_lines)
            current_section = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines)

    return sections

def _try_read_zip(raw_bytes):
    try:
        buf = io.BytesIO(raw_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            return {name: zf.read(name).decode("utf-8-sig") for name in zf.namelist()}
    except Exception:
        return None

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

def import_all(conn, raw_bytes, user_id):
    result = {}

    zip_content = _try_read_zip(raw_bytes)
    if zip_content:
        for name, data in zip_content.items():
            lower = name.lower()
            if "zeit" in lower:
                result["times_imported"] = import_times_csv(conn, data, user_id)
            elif "abwesen" in lower or "absence" in lower:
                result["absences_imported"] = import_absences_csv(conn, data, user_id)
        return result

    content = raw_bytes.decode("utf-8-sig")
    sections = _split_sections(content)
    if sections:
        if "Zeiten" in sections:
            result["times_imported"] = import_times_csv(conn, sections["Zeiten"], user_id)
        if "Abwesenheiten" in sections:
            result["absences_imported"] = import_absences_csv(conn, sections["Abwesenheiten"], user_id)
        return result

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return result
    headers = [h.strip() for h in reader.fieldnames]
    if "Datum" in headers:
        result["times_imported"] = import_times_csv(conn, content, user_id)
    if "Typ" in headers:
        result["absences_imported"] = import_absences_csv(conn, content, user_id)

    return result
