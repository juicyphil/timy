# timy – Lokale Zeiterfassung (Konzept & Plan)

## 1. Philosophie

**Lokal. Offline. Einfach.**

timy ist eine bewusst schlanke Zeiterfassung für den Einzelplatz oder kleine Teams.
Kein Account, keine Cloud, keine Internetabhängigkeit. Die App startet per Doppelklick
und läuft sofort – auf Windows und Linux identisch.

---

## 2. Technologie-Stack (Empfehlung)

### Gewählt: Python + SQLite + lokale Web-Oberfläche (via Webbrowser)

| Komponente | Technologie | Begründung |
|---|---|---|
| Sprache | Python 3.10+ | Plattformunabhängig, riesige Stdlib, kein Compiler |
| GUI | Lokaler Webserver (FastAPI) + Browser | Modernes UI ohne GUI-Toolkit-Abhängigkeit |
| Datenhaltung | SQLite (primär) | Built-in in Python, transaktional, zuverlässig |
| Export/Import | CSV + openpyxl (Excel .xlsx) | Export für Auswertungen, Import für Migration |
| Packaging | PyInstaller (Win) / natives Python (Linux) | Standalone .exe für Windows |
| Frontend | Vanilla HTML + CSS + JS | Null Build-Tooling, maximale Wartbarkeit |

### Warum nicht …

- **Tauri/Electron?** Würde Node.js/npm/Rust erfordern – zu viel Overhead.
- **Excel als Hauptspeicher?** Keine Transaktionen, keine Integrität, Konflikte.
  **Empfehlung: SQLite intern, Excel/CSV nur für Export/Import.**
- **Reines Python-GUI (tkinter/PyQt)?** Aufwändiger, oft weniger modern als Web-UI.

### Architektur-Skizze

```
Webbrowser (Chrome/Firefox/Edge)   <-- Modernes Frontend
         |  HTTP (localhost:8765)
Python-Server (FastAPI)            <-- Nur auf 127.0.0.1 gebunden
         |  sqlite3
SQLite-Datenbank (~/.timy/timy.db) <-- Eine Datei
         |
CSV/Excel-Export (optional)
```

Der Server startet beim App-Start automatisch und öffnet den Browser.
Kein Port ist von außen erreichbar (Binding an 127.0.0.1).

---

## 3. Datenmodell

### SQLite-Tabellen

**employees**
- id (INTEGER PK), name (TEXT), weekly_hours (REAL), vacation_entitlement (REAL)
- start_date (TEXT), is_active (INTEGER), created_at (TEXT)

**time_entries**
- id (INTEGER PK), employee_id (INTEGER FK), date (TEXT ISO)
- clock_in (TEXT HH:MM), clock_out (TEXT), pause_start (TEXT), pause_end (TEXT)
- note (TEXT), is_manual (INTEGER 0/1), created_at (TEXT)

**absences**
- id (INTEGER PK), employee_id (INTEGER FK)
- type (TEXT: vacation/sick/holiday/other)
- start_date (TEXT), end_date (TEXT), days (REAL), note (TEXT), created_at (TEXT)

**settings**
- key (TEXT PK), value (TEXT)

**public_holidays** (optional, v2)
- date (TEXT PK), name (TEXT), region (TEXT)

### Excel-Alternativ-Mapping (falls gewünscht)

- Stammdaten.xlsx -> Sheet "Mitarbeiter" = employees
- Buchungen.xlsx -> Sheet "Zeiten" = time_entries
- Buchungen.xlsx -> Sheet "Abwesenheiten" = absences
- Einstellungen.xlsx -> Sheet "Settings" = settings

**Nachteil Excel:** Dateisperre, keine atomaren Transaktionen, aufwändige Abfragen.
**Empfehlung: SQLite + CSV/Excel-Export.**

---

## 4. Benutzeroberfläche

### Struktur (Single-Page-App mit Navigation)

```
+--------------------------------------------------+
|  timy                     [Dashboard] [Export]   |
|  [Stempeln] [Uebersicht] [Abwesenheit]           |
+--------------------------------------------------+
|                                                    |
|  Inhalt des jeweiligen Bereichs                    |
|                                                    |
+--------------------------------------------------+
```

### Bereich "Stempeln" (Startseite)

- Große Uhrzeit + Datum
- Buttons: Kommen, Gehen, Pause Start, Pause Ende
- Heutige Arbeitszeit, Pausenzeit, Überstunden (Live)
- Letzte Buchung (Uhrzeit + Typ)
- Status-Anzeige: "Active: Eingestempelt seit 08:15"

### Bereich "Übersicht"

- Tab "Tag": Detailansicht eines Tages (editierbar)
- Tab "Woche": 7-Tage-Balken mit Soll/Ist/Überstunden
- Tab "Monat": Kalenderansicht mit farbigen Markierungen
  - Grün = gearbeitet, Blau = Urlaub, Orange = Krank, Rot = Fehltag
- Klick auf Eintrag -> Popup zum Bearbeiten (manuelle Korrektur)

### Bereich "Abwesenheit"

- Formular: Typ (Urlaub/Krank/Sonstiges), Start/Ende, Notiz
- Liste bestehender Abwesenheiten
- Urlaubsverbrauch: "5 von 30 Tagen verbraucht, 25 Rest"

### Bereich "Dashboard"

- KPI-Kacheln: Ist-Zeit, Soll-Zeit, Überstunden (Monat)
- Urlaub: Verbraucht / Rest
- Krankheitstage (Monat/Jahr)
- Anwesenheitsquote in %
- Kleine Sparkline: Ist vs. Soll pro Woche
- Monatsauswahl zum Navigieren

### Bereich "Export"

- Format: CSV oder Excel (.xlsx)
- Zeitraum: Tag/Woche/Monat/Benutzerdefiniert
- Daten: Zeiten / Abwesenheiten / Beides
- Datei-Dialog zum Speichern

---

## 5. MVP-Umfang (Version 1)

### Enthalten

- Single-User (1 Mitarbeiter)
- Zeiterfassung: Kommen, Gehen, Pause Start, Pause Ende
- Tages-/Wochen-/Monatsübersicht mit Berechnung:
  - Arbeitszeit (clock_out - clock_in - pause)
  - Sollzeit (aus weekly_hours / Werktage)
  - Überstunden (Ist - Soll)
- Abwesenheiten: Urlaub und Krankheit erfassen
- Dashboard: Ist-Zeit, Soll-Zeit, Überstunden, Resturlaub
- Manuelle Korrektur von Buchungen
- CSV-Export aller Zeitbuchungen und Abwesenheiten
- Lokaler Betrieb: Start per Doppelklick, Browser öffnet sich
- SQLite-DB in ~/.timy/timy.db

### Nicht enthalten (v1)

- Multi-User / Team
- Feiertagsautomatik
- Jahresbericht
- Automatische Pausenabzüge
- Mobile App / Cloud-Sync
- PDF-Export

### Version 2 (Ausblick)

- Multi-Employee (kleines Team)
- Automatische Feiertage (DE/Region)
- Jahresbericht mit Diagrammen
- PDF-Export
- Unterschiedliche Sollzeiten pro Wochentag
- Tray-Icon mit Schnellstempeln

---

## 6. Projektstruktur

```
timy/
├── main.py               # Einstiegspunkt: Startet Server + Browser
├── requirements.txt      # fastapi, uvicorn, openpyxl
├── timy.db               # SQLite-DB (wird automatisch angelegt)
├── server/
│   ├── __init__.py
│   ├── app.py            # FastAPI-App, Routen
│   ├── database.py       # SQLite-Init, CRUD-Helfer
│   ├── models.py         # Pydantic-Modelle
│   └── export.py         # CSV-/Excel-Export
├── static/
│   ├── index.html        # Single-Page-App
│   ├── style.css         # Styling (schlicht, responsiv)
│   ├── app.js            # Hauptlogik (Fetch-API)
│   └── dashboard.js      # Dashboard-Logik
└── build/
    └── timy.spec         # PyInstaller-Spec
```

---

## 7. Begründung: SQLite > Excel

| Kriterium | SQLite | Excel/CSV |
|---|---|---|
| Transaktionen | Ja (atomic, rollback) | Nein |
| Datenintegrität | Constraints, FKs | Nein |
| Gleichzeitigkeit | Mehrere Lesezugriffe | Dateisperre |
| Abfragen | SQL (GROUP BY, SUM) | Manuelle Formeln |
| Portabilität | Eine .db-Datei | Eine .xlsx-Datei |
| Export | CSV/Excel-Export | Native Formate |
| Performance | Sehr gut (10k+) | Langsam ab ~1000 Z. |

**Fazit:** SQLite ist technisch überlegen. Export nach CSV/Excel ist als Feature
verfügbar, sodass der Nutzer jederzeit seine Daten in Excel öffnen kann.

---

## 8. Nächste Schritte

1. Plan freigeben und ggf. anpassen
2. MVP implementieren (Datenmodell + API + UI)
3. Testen auf Windows + Linux
4. Verpacken (PyInstaller für Windows, Python-Skript für Linux)

---

## 9. Offene Fragen

1. Multi-Employee (Team) schon im MVP oder erst v2?
2. SQLite (primär) oder Excel (primär) – oder beides parallel?
3. Sprache der UI: Deutsch oder Englisch?
4. Portable .exe (USB-Stick) oder installierbar?
