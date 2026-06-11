from datetime import datetime, timedelta
import calendar

DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

def parse_time(t):
    if not t:
        return None
    parts = str(t).split(":")
    return int(parts[0]) * 60 + int(parts[1])

def format_minutes(m):
    h = abs(m) // 60
    mins = abs(m) % 60
    sign = "-" if m < 0 else ""
    return f"{sign}{h}h {mins:02d}min"

def format_minutes_short(m):
    h = abs(m) // 60
    mins = abs(m) % 60
    sign = "-" if m < 0 else ""
    return f"{sign}{h}:{mins:02d}"

def calc_working_minutes(entry):
    ci = parse_time(entry.get("clock_in"))
    co = parse_time(entry.get("clock_out"))
    ps = parse_time(entry.get("pause_start"))
    pe = parse_time(entry.get("pause_end"))

    if ci is None or co is None:
        return 0

    total = co - ci
    if ps is not None and pe is not None:
        total -= (pe - ps)

    return max(0, total)

def calc_pause_minutes(entry):
    ps = parse_time(entry.get("pause_start"))
    pe = parse_time(entry.get("pause_end"))
    if ps is not None and pe is not None:
        return max(0, pe - ps)
    return 0

def get_target_minutes(date_str, weekly_hours):
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.weekday() >= 5:
            return 0
        return int((weekly_hours / 5) * 60)
    except:
        return 0

def get_week_dates(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start = dt - timedelta(days=dt.weekday())
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

def get_month_range(year, month):
    _, last_day = calendar.monthrange(year, month)
    return last_day

def is_weekday(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.weekday() < 5

def get_absence_dates_set(absences):
    dates = set()
    for a in absences:
        try:
            sd = datetime.strptime(a["start_date"], "%Y-%m-%d")
            ed = datetime.strptime(a["end_date"], "%Y-%m-%d")
            d = sd
            while d <= ed:
                dates.add(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)
        except (KeyError, ValueError):
            pass
    return dates

def get_adjusted_target_for_month(year, month, weekly_hours, absences, max_day=None):
    last_day = max_day if max_day is not None else get_month_range(year, month)
    daily_target = int((weekly_hours / 5) * 60)
    absence_dates = get_absence_dates_set(absences)
    total = 0
    for day_num in range(1, last_day + 1):
        d = f"{year:04d}-{month:02d}-{day_num:02d}"
        if not is_weekday(d) or d in absence_dates:
            continue
        total += daily_target
    return total

def get_working_days_in_month(year, month, absences, max_day=None):
    last_day = max_day if max_day is not None else get_month_range(year, month)
    absence_dates = get_absence_dates_set(absences)
    count = 0
    for day_num in range(1, last_day + 1):
        d = f"{year:04d}-{month:02d}-{day_num:02d}"
        if is_weekday(d) and d not in absence_dates:
            count += 1
    return count
