import hashlib

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime

from .database import init_db, get_connection
from .models import TimeEntry, Absence, Settings, LoginRequest, CreateUser, AbsenceNoteUpdate
from .calc import (
    parse_time, format_minutes, format_minutes_short,
    calc_working_minutes, calc_pause_minutes,
    get_target_minutes, get_week_dates, get_month_range, is_weekday,
    get_absence_dates_set, get_absence_info_by_date, get_adjusted_target_for_month,
    get_working_days_in_month, get_cumulative_overtime, DAYS
)
from .export import export_times_csv, export_absences_csv

app = FastAPI(title="timy")

@app.on_event("startup")
def startup():
    init_db()

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ─── Root ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((static_dir / "index.html").read_text(encoding="utf-8"))

# ─── Login / Users ──────────────────────────────────────────────────────

@app.post("/api/login")
def login(data: LoginRequest):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE name=?", (data.name,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, "Benutzer nicht gefunden")
    ph = hashlib.sha256(data.pin.encode()).hexdigest()
    if user["pin_hash"] != ph:
        raise HTTPException(401, "Falsche PIN")
    return {"success": True, "user": {"id": user["id"], "name": user["name"], "role": user["role"]}}

@app.post("/api/users")
def create_user(data: CreateUser):
    conn = get_connection()
    try:
        ph = hashlib.sha256(data.pin.encode()).hexdigest()
        conn.execute("INSERT INTO users (name, pin_hash) VALUES (?, ?)", (data.name, ph))
        conn.commit()
        u = dict(conn.execute("SELECT id, name, role FROM users WHERE name=?", (data.name,)).fetchone())
        conn.close()
        return {"success": True, "user": u}
    except Exception:
        conn.close()
        raise HTTPException(400, "Benutzer existiert bereits")

def get_user_start_date(conn, uid):
    user = conn.execute("SELECT start_date, created_at FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        return datetime.now().strftime("%Y-%m-%d")
    return user["start_date"] or user["created_at"][:10]

@app.get("/api/users")
def list_users(uid: int = Query(1)):
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not user or user["role"] != "ausbilder":
        conn.close()
        raise HTTPException(403, "Keine Berechtigung")
    users = conn.execute("SELECT id, name, role, created_at FROM users ORDER BY name").fetchall()
    conn.close()
    return [dict(u) for u in users]

@app.get("/api/ausbilder/overview")
def ausbilder_overview(year: int = Query(...), month: int = Query(...), uid: int = Query(1), max_day: int = Query(None)):
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not user or user["role"] != "ausbilder":
        conn.close()
        raise HTTPException(403, "Keine Berechtigung")
    
    users = conn.execute("SELECT id, name FROM users WHERE role != 'ausbilder' ORDER BY name").fetchall()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))
    last_day = get_month_range(year, month)
    calc_day = min(last_day, max_day) if max_day else last_day
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{calc_day:02d}"
    
    result = []
    for u in users:
        uid_u = u["id"]
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE date BETWEEN ? AND ? AND user_id=? ORDER BY date",
            (start, end, uid_u)
        ).fetchall()
        total_working = sum(calc_working_minutes(dict(r)) for r in rows)
        
        abs_rows = conn.execute(
            "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=?",
            (f"{year:04d}-{month:02d}-{last_day:02d}", start, uid_u)
        ).fetchall()
        abs_list = [dict(a) for a in abs_rows]
        working_days = get_working_days_in_month(year, month, abs_list, max_day=calc_day)
        target = get_adjusted_target_for_month(year, month, weekly_hours, abs_list, max_day=calc_day, friday_hours=friday_hours)
        
        user_start = get_user_start_date(conn, uid_u)
        cumulative_ot = get_cumulative_overtime(conn, uid_u, user_start, end, weekly_hours, friday_hours)
        
        result.append({
            "user_id": uid_u,
            "name": u["name"],
            "working_minutes": total_working,
            "target_minutes": target,
            "overtime_minutes": cumulative_ot,
            "working_days": working_days,
            "absence_count": len(abs_list)
        })
    
    conn.close()
    return {"year": year, "month": month, "users": result}

@app.get("/api/ausbilder/day")
def ausbilder_day(date: str = Query(...), uid: int = Query(1)):
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not user or user["role"] != "ausbilder":
        conn.close()
        raise HTTPException(403, "Keine Berechtigung")
    
    users = conn.execute("SELECT id, name FROM users WHERE role != 'ausbilder' ORDER BY name").fetchall()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))
    target = get_target_minutes(date, weekly_hours, friday_hours)
    
    result = []
    for u in users:
        uid_u = u["id"]
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE date=? AND user_id=? ORDER BY id",
            (date, uid_u)
        ).fetchall()
        entries = [dict(r) for r in rows]
        working = sum(calc_working_minutes(dict(r)) for r in rows)
        pause = sum(calc_pause_minutes(dict(r)) for r in rows)
        
        abs_row = conn.execute(
            "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=? LIMIT 1",
            (date, date, uid_u)
        ).fetchone()
        absence = dict(abs_row) if abs_row else None
        
        user_start = get_user_start_date(conn, uid_u)
        cumulative_ot = get_cumulative_overtime(conn, uid_u, user_start, date, weekly_hours, friday_hours)
        
        result.append({
            "user_id": uid_u,
            "name": u["name"],
            "entries": entries,
            "working_minutes": working,
            "pause_minutes": pause,
            "target_minutes": target,
            "overtime_minutes": cumulative_ot,
            "absence": absence
        })
    
    conn.close()
    return {"date": date, "users": result}

@app.get("/api/ausbilder/year")
def ausbilder_year(year: int = Query(...), uid: int = Query(1)):
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not user or user["role"] != "ausbilder":
        conn.close()
        raise HTTPException(403, "Keine Berechtigung")
    
    users = conn.execute("SELECT id, name FROM users WHERE role != 'ausbilder' ORDER BY name").fetchall()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))
    
    now = datetime.now()
    is_current_year = year == now.year
    
    result = []
    for u in users:
        uid_u = u["id"]
        total_working = 0
        total_target = 0
        total_absence_days = 0
        
        max_month = now.month if is_current_year else 12
        
        for month in range(1, max_month + 1):
            last_day = get_month_range(year, month)
            max_day = now.day if (is_current_year and month == now.month) else last_day
            start = f"{year:04d}-{month:02d}-01"
            end = f"{year:04d}-{month:02d}-{max_day:02d}"
            
            rows = conn.execute(
                "SELECT * FROM time_entries WHERE date BETWEEN ? AND ? AND user_id=? ORDER BY date",
                (start, end, uid_u)
            ).fetchall()
            total_working += sum(calc_working_minutes(dict(r)) for r in rows)
            
            abs_rows = conn.execute(
                "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=?",
                (f"{year:04d}-{month:02d}-{last_day:02d}", start, uid_u)
            ).fetchall()
            abs_list = [dict(a) for a in abs_rows]
            total_target += get_adjusted_target_for_month(year, month, weekly_hours, abs_list, max_day=max_day, friday_hours=friday_hours)
            total_absence_days += len(abs_list)
        
        user_start = get_user_start_date(conn, uid_u)
        year_end = f"{year:04d}-{max_month:02d}-{now.day if is_current_year else 31:02d}"
        cumulative_ot = get_cumulative_overtime(conn, uid_u, user_start, year_end, weekly_hours, friday_hours)
        
        result.append({
            "user_id": uid_u,
            "name": u["name"],
            "working_minutes": total_working,
            "target_minutes": total_target,
            "overtime_minutes": cumulative_ot,
            "absence_count": total_absence_days
        })
    
    conn.close()
    return {"year": year, "users": result}

# ─── Settings ───────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    s = {r["key"]: r["value"] for r in rows}
    return {
        "weekly_hours": float(s.get("weekly_hours", 40)),
        "vacation_days": float(s.get("vacation_days", 30)),
        "employee_name": s.get("employee_name", "Benutzer"),
        "pause_duration": float(s.get("pause_duration", 30)),
        "friday_hours": float(s.get("friday_hours", 0))
    }

@app.put("/api/settings")
def update_settings(settings: Settings):
    conn = get_connection()
    conn.execute("UPDATE settings SET value=? WHERE key='weekly_hours'", (str(settings.weekly_hours),))
    conn.execute("UPDATE settings SET value=? WHERE key='vacation_days'", (str(settings.vacation_days),))
    conn.execute("UPDATE settings SET value=? WHERE key='employee_name'", (settings.employee_name,))
    conn.execute("UPDATE settings SET value=? WHERE key='pause_duration'", (str(settings.pause_duration),))
    conn.execute("UPDATE settings SET value=? WHERE key='friday_hours'", (str(settings.friday_hours),))
    conn.commit()
    conn.close()
    return {"success": True}

# ─── Clock (stempeln) ───────────────────────────────────────────────────

@app.get("/api/today")
def get_today(uid: int = Query(1)):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    entries = conn.execute(
        "SELECT * FROM time_entries WHERE date=? AND user_id=? ORDER BY id", (today, uid)
    ).fetchall()

    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))

    current_entry = dict(entries[-1]) if entries else None
    status = "off"

    if current_entry:
        if current_entry["clock_in"] and not current_entry["clock_out"]:
            status = "pausing" if (current_entry["pause_start"] and not current_entry["pause_end"]) else "working"

    total_working = sum(calc_working_minutes(dict(e)) for e in entries)
    total_pause = sum(calc_pause_minutes(dict(e)) for e in entries)
    target = get_target_minutes(today, weekly_hours, friday_hours)
    start_date = get_user_start_date(conn, uid)
    overtime = get_cumulative_overtime(conn, uid, start_date, today, weekly_hours, friday_hours)

    conn.close()
    return {
        "status": status,
        "date": today,
        "current_entry": current_entry,
        "total_working": total_working,
        "total_pause": total_pause,
        "target": target,
        "overtime": overtime
    }

@app.post("/api/clock-in")
def clock_in(uid: int = Query(1)):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    conn = get_connection()

    open_entry = conn.execute(
        "SELECT id FROM time_entries WHERE date=? AND user_id=? AND clock_in IS NOT NULL AND clock_out IS NULL LIMIT 1",
        (date_str, uid)
    ).fetchone()
    if open_entry:
        conn.close()
        raise HTTPException(400, "Bereits eingestempelt")

    conn.execute("INSERT INTO time_entries (date, clock_in, user_id) VALUES (?, ?, ?)", (date_str, time_str, uid))
    conn.commit()
    entry = dict(conn.execute("SELECT * FROM time_entries WHERE id=last_insert_rowid()").fetchone())
    conn.close()
    return {"success": True, "entry": entry}

@app.post("/api/clock-out")
def clock_out(uid: int = Query(1)):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    conn = get_connection()

    entry = conn.execute(
        "SELECT * FROM time_entries WHERE date=? AND user_id=? AND clock_in IS NOT NULL AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (date_str, uid)
    ).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(400, "Nicht eingestempelt")

    if entry["pause_start"] and not entry["pause_end"]:
        conn.execute("UPDATE time_entries SET pause_end=? WHERE id=?", (time_str, entry["id"]))

    if not entry["pause_start"]:
        s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
        pause_min = int(float(s.get("pause_duration", 30)))
        if pause_min > 0:
            ci = parse_time(entry["clock_in"])
            co = parse_time(time_str)
            if ci is not None and co is not None:
                mid = ci + (co - ci) // 2
                ps_h, ps_m = divmod(mid, 60)
                pe_mid = mid + pause_min
                pe_h, pe_m = divmod(pe_mid, 60)
                pause_start = f"{ps_h:02d}:{ps_m:02d}"
                pause_end = f"{pe_h:02d}:{pe_m:02d}"
                conn.execute("UPDATE time_entries SET pause_start=?, pause_end=? WHERE id=?",
                             (pause_start, pause_end, entry["id"]))

    conn.execute("UPDATE time_entries SET clock_out=? WHERE id=?", (time_str, entry["id"]))
    conn.commit()
    result = dict(conn.execute("SELECT * FROM time_entries WHERE id=?", (entry["id"],)).fetchone())
    conn.close()
    return {"success": True, "entry": result}

@app.post("/api/pause-start")
def pause_start(uid: int = Query(1)):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    conn = get_connection()

    entry = conn.execute(
        "SELECT * FROM time_entries WHERE date=? AND user_id=? AND clock_in IS NOT NULL AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (date_str, uid)
    ).fetchone()
    if not entry:
        conn.close()
        raise HTTPException(400, "Nicht eingestempelt")
    if entry["pause_start"] and not entry["pause_end"]:
        conn.close()
        raise HTTPException(400, "Pause bereits aktiv")

    conn.execute("UPDATE time_entries SET pause_start=? WHERE id=?", (time_str, entry["id"]))
    conn.commit()
    result = dict(conn.execute("SELECT * FROM time_entries WHERE id=?", (entry["id"],)).fetchone())
    conn.close()
    return {"success": True, "entry": result}

@app.post("/api/pause-end")
def pause_end(uid: int = Query(1)):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    conn = get_connection()

    entry = conn.execute(
        "SELECT * FROM time_entries WHERE date=? AND user_id=? AND clock_in IS NOT NULL AND clock_out IS NULL ORDER BY id DESC LIMIT 1",
        (date_str, uid)
    ).fetchone()
    if not entry or not entry["pause_start"]:
        conn.close()
        raise HTTPException(400, "Keine aktive Pause")
    if entry["pause_end"]:
        conn.close()
        raise HTTPException(400, "Pause bereits beendet")

    conn.execute("UPDATE time_entries SET pause_end=? WHERE id=?", (time_str, entry["id"]))
    conn.commit()
    result = dict(conn.execute("SELECT * FROM time_entries WHERE id=?", (entry["id"],)).fetchone())
    conn.close()
    return {"success": True, "entry": result}

# ─── Entries CRUD ───────────────────────────────────────────────────────

@app.get("/api/entries")
def get_entries(date: str = Query(...), uid: int = Query(1)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM time_entries WHERE date=? AND user_id=? ORDER BY id", (date, uid)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/entries")
def create_entry(entry: TimeEntry, uid: int = Query(1)):
    conn = get_connection()
    conn.execute(
        "INSERT INTO time_entries (date, clock_in, clock_out, pause_start, pause_end, note, is_manual, user_id) VALUES (?,?,?,?,?,?,1,?)",
        (entry.date, entry.clock_in, entry.clock_out, entry.pause_start, entry.pause_end, entry.note, uid)
    )
    conn.commit()
    e = dict(conn.execute("SELECT * FROM time_entries WHERE id=last_insert_rowid()").fetchone())
    conn.close()
    return e

@app.put("/api/entries/{entry_id}")
def update_entry(entry_id: int, entry: TimeEntry, uid: int = Query(1)):
    conn = get_connection()
    cur = conn.execute(
        "UPDATE time_entries SET clock_in=?, clock_out=?, pause_start=?, pause_end=?, note=?, is_manual=1 WHERE id=? AND user_id=?",
        (entry.clock_in, entry.clock_out, entry.pause_start, entry.pause_end, entry.note, entry_id, uid)
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404)
    e = dict(conn.execute("SELECT * FROM time_entries WHERE id=?", (entry_id,)).fetchone())
    conn.close()
    return e

@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: int, uid: int = Query(1)):
    conn = get_connection()
    conn.execute("DELETE FROM time_entries WHERE id=? AND user_id=?", (entry_id, uid))
    conn.commit()
    conn.close()
    return {"success": True}

# ─── Week / Month ───────────────────────────────────────────────────────

@app.get("/api/week")
def get_week(date: str = Query(...), uid: int = Query(1), max_date: str = Query(None)):
    conn = get_connection()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))

    week_dates = get_week_dates(date)
    end_of_week = week_dates[-1]
    result = []
    for d in week_dates:
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE date=? AND user_id=? ORDER BY id", (d, uid)
        ).fetchall()
        working = sum(calc_working_minutes(dict(r)) for r in rows)
        target = get_target_minutes(d, weekly_hours, friday_hours)
        dt = datetime.strptime(d, "%Y-%m-%d")
        count = max_date is None or d <= max_date
        result.append({
            "date": d,
            "day_name": DAYS[dt.weekday()],
            "entries": [dict(r) for r in rows],
            "working_minutes": working if count else 0,
            "target_minutes": target if count else 0,
            "overtime_minutes": (working - target) if count else 0
        })
    cutoff = max_date if max_date else end_of_week
    start_date = get_user_start_date(conn, uid)
    cumulative = get_cumulative_overtime(conn, uid, start_date, cutoff, weekly_hours, friday_hours)
    conn.close()
    return {"days": result, "cumulative_overtime_minutes": cumulative}

@app.get("/api/month")
def get_month(year: int = Query(...), month: int = Query(...), uid: int = Query(1), max_day: int = Query(None)):
    conn = get_connection()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    friday_hours = float(s.get("friday_hours", 0))

    last_day = get_month_range(year, month)
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    start = f"{year:04d}-{month:02d}-01"

    absences = conn.execute(
        "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=?",
        (end, start, uid)
    ).fetchall()
    absences_list = [dict(a) for a in absences]
    absence_info = get_absence_info_by_date(absences_list)

    count_day = min(last_day, max_day) if max_day else last_day

    days = []
    tw, tt, to, tp = 0, 0, 0, 0

    for day_num in range(1, last_day + 1):
        d = f"{year:04d}-{month:02d}-{day_num:02d}"
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE date=? AND user_id=? ORDER BY id", (d, uid)
        ).fetchall()
        w = sum(calc_working_minutes(dict(r)) for r in rows)
        t = get_target_minutes(d, weekly_hours, friday_hours)
        if d in absence_info:
            a = absence_info[d]
            if a["type"] == "ueberstunden_abbau":
                pass
            else:
                t = 0
        p = sum(calc_pause_minutes(dict(r)) for r in rows)
        dt = datetime.strptime(d, "%Y-%m-%d")
        if day_num <= count_day:
            tw += w; tt += t; to += (w - t); tp += p
        days.append({
            "date": d, "day_name": DAYS[dt.weekday()],
            "working_minutes": w, "target_minutes": t,
            "overtime_minutes": w - t, "pause_minutes": p,
            "has_entry": len(rows) > 0
        })

    cumulative_end = f"{year:04d}-{month:02d}-{count_day:02d}"
    start_date = get_user_start_date(conn, uid)
    cumulative_ot = get_cumulative_overtime(conn, uid, start_date, cumulative_end, weekly_hours, friday_hours)

    conn.close()

    return {
        "year": year, "month": month,
        "days": days,
        "totals": {"working_minutes": tw, "target_minutes": tt, "overtime_minutes": cumulative_ot, "pause_minutes": tp},
        "absences": absences_list
    }

# ─── Absences ───────────────────────────────────────────────────────────

@app.get("/api/absences")
def list_absences(uid: int = Query(1)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM absences WHERE user_id=? ORDER BY start_date DESC", (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/absences")
def create_absence(absence: Absence, uid: int = Query(1)):
    conn = get_connection()
    conn.execute(
        "INSERT INTO absences (type, start_date, end_date, days, note, user_id) VALUES (?,?,?,?,?,?)",
        (absence.type, absence.start_date, absence.end_date, absence.days, absence.note, uid)
    )
    conn.commit()
    a = dict(conn.execute("SELECT * FROM absences WHERE id=last_insert_rowid()").fetchone())
    conn.close()
    return a

@app.delete("/api/absences/{absence_id}")
def delete_absence(absence_id: int, uid: int = Query(1)):
    conn = get_connection()
    conn.execute("DELETE FROM absences WHERE id=? AND user_id=?", (absence_id, uid))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/absence-for-date")
def get_absence_for_date(date: str = Query(...), uid: int = Query(1)):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=? LIMIT 1",
        (date, date, uid)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

@app.put("/api/absences/{absence_id}/note")
def update_absence_note(absence_id: int, data: AbsenceNoteUpdate, uid: int = Query(1)):
    conn = get_connection()
    cur = conn.execute(
        "UPDATE absences SET note=? WHERE id=? AND user_id=?",
        (data.note, absence_id, uid)
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404)
    a = dict(conn.execute("SELECT * FROM absences WHERE id=?", (absence_id,)).fetchone())
    conn.close()
    return a

# ─── Dashboard ──────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(year: int = Query(...), month: int = Query(...), uid: int = Query(1), max_day: int = Query(None)):
    conn = get_connection()
    s = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    weekly_hours = float(s.get("weekly_hours", 40))
    vacation_days = float(s.get("vacation_days", 30))
    friday_hours = float(s.get("friday_hours", 0))

    last_day = get_month_range(year, month)
    start = f"{year:04d}-{month:02d}-01"
    calc_day = min(last_day, max_day) if max_day else last_day
    end = f"{year:04d}-{month:02d}-{calc_day:02d}"

    rows = conn.execute(
        "SELECT * FROM time_entries WHERE date BETWEEN ? AND ? AND user_id=? ORDER BY date", (start, end, uid)
    ).fetchall()
    total_working = sum(calc_working_minutes(dict(r)) for r in rows)

    abs_rows = conn.execute(
        "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=?",
        (f"{year:04d}-{month:02d}-{last_day:02d}", start, uid)
    ).fetchall()
    abs_list = [dict(a) for a in abs_rows]
    working_days = get_working_days_in_month(year, month, abs_list, max_day=calc_day)
    target = get_adjusted_target_for_month(year, month, weekly_hours, abs_list, max_day=calc_day, friday_hours=friday_hours)
    overtime = total_working - target

    sick_days = 0
    for a in abs_list:
        if a["type"] == "sick":
            sick_days += float(a["days"])

    all_vac = conn.execute(
        "SELECT SUM(days) as total FROM absences WHERE type='vacation' AND user_id=?",
        (uid,)
    ).fetchone()
    total_vacation_used = float(all_vac["total"] or 0)
    presence_pct = round(min(100, (total_working / target) * 100), 1) if target > 0 else 0

    start_date = get_user_start_date(conn, uid)
    cumulative_ot = get_cumulative_overtime(conn, uid, start_date, end, weekly_hours, friday_hours)

    conn.close()
    return {
        "year": year, "month": month,
        "working_minutes": total_working, "target_minutes": target,
        "overtime_minutes": cumulative_ot, "working_days": working_days,
        "vacation_used": total_vacation_used, "vacation_total": vacation_days,
        "sick_days": sick_days, "presence_pct": presence_pct
    }

# ─── Export ─────────────────────────────────────────────────────────────

@app.get("/api/export/csv")
def export_csv(
    from_date: str = Query(...),
    to_date: str = Query(...),
    type: str = "all",
    uid: int = Query(1)
):
    conn = get_connection()
    parts = []

    if type in ("time", "all"):
        entries = conn.execute(
            "SELECT * FROM time_entries WHERE date BETWEEN ? AND ? AND user_id=? ORDER BY date",
            (from_date, to_date, uid)
        ).fetchall()
        parts.append("=== Zeiten ===")
        parts.append(export_times_csv([dict(e) for e in entries]))

    if type in ("absence", "all"):
        absences = conn.execute(
            "SELECT * FROM absences WHERE start_date <= ? AND end_date >= ? AND user_id=? ORDER BY start_date",
            (to_date, from_date, uid)
        ).fetchall()
        parts.append("=== Abwesenheiten ===")
        parts.append(export_absences_csv([dict(a) for a in absences]))

    conn.close()
    content = "\n".join(parts)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=timy_export_{from_date}_{to_date}.csv"}
    )
