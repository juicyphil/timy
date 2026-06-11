# timy

Lokale Zeiterfassung mit Stempeluhr, Überstunden-Tracking und Abwesenheitsverwaltung.

## Features

- Stempeluhr (Kommen/Gehen/Pause)
- Manuelle Buchungen
- Tages-/Wochen-/Monatsübersicht mit Überstunden
- Dashboard mit KPIs (Ist/Soll, Überstunden, Urlaub, Krankheit, Anwesenheit)
- Abwesenheiten (Urlaub, Krank, Feiertag, BBS)
- CSV-Export
- Multi-User mit PIN-Login
- Dark Mode

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Datenbank:** SQLite
- **Frontend:** Vanilla HTML/CSS/JS (SPA)
- **Deployment:** Docker + docker-compose

## Starten

```bash
docker compose up -d
# oder
make up
```

App läuft auf http://localhost:8765

## Standard-Login

- Benutzer: `Admin`
- PIN: `0000`
