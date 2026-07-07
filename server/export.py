import csv
import io
import zipfile

from .calc import format_minutes, calc_working_minutes

TYPE_NAMES = {
    "vacation": "Urlaub",
    "sick": "Krank",
    "holiday": "Feiertag",
    "bbs": "BBS",
    "ueberstunden_abbau": "Überstunden Abbau",
    "other": "Sonstige"
}

def export_times_csv(entries):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Datum", "Kommen", "Gehen", "Pause Start", "Pause Ende", "Arbeitszeit", "Notiz"])
    for e in entries:
        mins = calc_working_minutes(e)
        writer.writerow([
            e["date"],
            e.get("clock_in") or "",
            e.get("clock_out") or "",
            e.get("pause_start") or "",
            e.get("pause_end") or "",
            format_minutes(mins),
            e.get("note") or ""
        ])
    return output.getvalue()

def export_absences_csv(absences):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Typ", "Start", "Ende", "Tage", "Notiz"])
    for a in absences:
        writer.writerow([
            TYPE_NAMES.get(a["type"], a["type"]),
            a["start_date"],
            a["end_date"],
            a["days"],
            a.get("note") or ""
        ])
    return output.getvalue()

def export_all_zip(entries, absences):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("zeiten.csv", export_times_csv(entries))
        zf.writestr("abwesenheiten.csv", export_absences_csv(absences))
    return buf.getvalue()
