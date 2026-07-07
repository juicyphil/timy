# timy

A local time tracking app with clock-in/out, overtime tracking, absence management, and multi-user support.

> **Note:** The UI is currently German only.

## Features

- Clock in/out with automatic pause insertion
- Manual time entries with edit and delete
- Day/week/month overview with overtime calculation
- Overtime calculated up to today (not end of month)
- Dashboard with KPIs (actual vs target, overtime, vacation, sick days, attendance)
- Flexible daily targets (e.g. 8:30 Mon-Thu, 6:00 Fri)
- Configurable auto-pause duration
- Absence management (vacation, sick, holiday, BBS, overtime reduction, other)
- CSV export and import
- Multi-user with PIN login and role management
- Ausbilder (supervisor) overview across all users
- User management with admin role
- Dark mode

## Roles

| Role | Description |
|------|-------------|
| `user` | Default role — can track time, manage absences, export data |
| `ausbilder` | Supervisor — sees an overview of all users' time and absences |
| `admin` | User management — can promote users to ausbilder, delete users, change own PIN |

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JS (SPA)
- **Deployment:** Docker + docker-compose

## Getting started

```bash
docker compose up -d
# or
make up
```

App runs at http://localhost:8765

## Default login

| User | PIN | Role |
|------|-----|------|
| `Admin` | `0000` | admin |
| `Ausbilder` | `1234` | ausbilder |
