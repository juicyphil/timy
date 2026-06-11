// ─── State ─────────────────────────────────────────────
const state = {
  view: 'clock',
  today: null,
  settings: null,
  liveClock: null
};
let navInitialized = false;

// ─── Helpers ───────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function api(path, opts = {}) {
  if (path.startsWith('/api/login') || path.startsWith('/api/users')) {
    // no uid needed
  } else {
    const userId = localStorage.getItem('timy_user_id');
    if (userId) {
      path += (path.includes('?') ? '&' : '?') + 'uid=' + userId;
    }
  }
  return fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  }).then(r => {
    if (!r.ok) return r.json().then(e => { throw new Error(e.detail || 'Fehler') });
    const ct = r.headers.get('content-type') || '';
    if (ct.includes('text/csv')) return r.blob();
    return r.json();
  });
}

function fmtMin(m) {
  const h = Math.floor(Math.abs(m) / 60);
  const min = Math.abs(m) % 60;
  return (m < 0 ? '-' : '') + h + 'h ' + String(min).padStart(2, '0') + 'min';
}

function fmtMinShort(m) {
  const h = Math.floor(Math.abs(m) / 60);
  const min = Math.abs(m) % 60;
  return (m < 0 ? '-' : '') + h + ':' + String(min).padStart(2, '0');
}

function todayStr() { return new Date().toISOString().slice(0, 10); }

function parseHHMM(s) { if (!s) return null; const [h, m] = s.split(':'); return parseInt(h) * 60 + parseInt(m); }

// ─── Navigation ────────────────────────────────────────
function initNav() {
  $$('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      if (!view) return;
      $$('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.view = view;
      renderView(view);
    });
  });
}

function renderView(view) {
  const content = $('#content');
  if (!content) return;
  if (view === 'clock') renderClock(content);
  else if (view === 'overview') renderOverview(content);
  else if (view === 'absences') renderAbsences(content);
  else if (view === 'dashboard') renderDashboard(content);
  else if (view === 'export') renderExport(content);
  else if (view === 'settings') renderSettings(content);
}

// ─── API: today + clock actions ────────────────────────
function refreshToday() {
  return api('/api/today').then(d => { state.today = d; return d; });
}

// ─── Clock View ────────────────────────────────────────
function renderClock(host) {
  refreshToday().then(d => {
    host.innerHTML = clockHTML(d);
    startLiveClock(host);
    bindClockButtons();
    // Re-render every 30s to keep stats fresh
    if (state._clockTimer) clearInterval(state._clockTimer);
    state._clockTimer = setInterval(() => {
      refreshToday().then(d => {
        const timeEl = host.querySelector('.clock-time');
        if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('de-DE');
        const stats = host.querySelector('.clock-stats');
        if (stats) stats.outerHTML = clockStatsHTML(d);
      });
    }, 30000);
  });
}

function clockHTML(d) {
  const now = new Date();
  const time = now.toLocaleTimeString('de-DE');
  const date = now.toLocaleDateString('de-DE', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  const statusLabels = { off: 'Nicht eingestempelt', working: 'Arbeitet', pausing: 'In Pause' };
  const statusClasses = { off: 'clock-status--off', working: 'clock-status--working', pausing: 'clock-status--pausing' };

  return `
    <div class="card">
      <div class="clock-display">
        <div class="clock-time" id="live-time">${time}</div>
        <div class="clock-date">${date}</div>
        <div class="clock-status ${statusClasses[d.status] || ''}">${statusLabels[d.status] || d.status}</div>
      </div>

      <div class="clock-buttons">
        ${d.status === 'off'
          ? '<button class="clock-btn clock-btn--in" data-action="clock-in">&#9654; Kommen</button>'
          : ''}
        ${d.status === 'working'
          ? '<button class="clock-btn clock-btn--pause" data-action="pause-start">&#9201; Pause Start</button><button class="clock-btn clock-btn--out" data-action="clock-out">&#9632; Gehen</button>'
          : ''}
        ${d.status === 'pausing'
          ? '<button class="clock-btn clock-btn--resume" data-action="pause-end">&#9654; Pause Ende</button><button class="clock-btn clock-btn--out" data-action="clock-out">&#9632; Gehen</button>'
          : ''}
      </div>

      ${clockStatsHTML(d)}

      <div class="text-center">
        <button class="btn btn-ghost btn-sm" onclick="showManualEntry()">&#9998; Manuelle Buchung</button>
      </div>
    </div>
  `;
}

function clockStatsHTML(d) {
  const otClass = d.overtime >= 0 ? 'stat-value--positive' : 'stat-value--negative';
  const otSign = d.overtime >= 0 ? '+' : '';
  return `
    <div class="clock-stats">
      <div class="stat-box">
        <div class="stat-value">${fmtMinShort(d.total_working)}</div>
        <div class="stat-label">Arbeitszeit</div>
      </div>
      <div class="stat-box">
        <div class="stat-value">${fmtMinShort(d.total_pause)}</div>
        <div class="stat-label">Pausenzeit</div>
      </div>
      <div class="stat-box">
        <div class="stat-value">${fmtMinShort(d.target)}</div>
        <div class="stat-label">Sollzeit</div>
      </div>
      <div class="stat-box">
        <div class="stat-value ${otClass}">${otSign}${fmtMinShort(d.overtime)}</div>
        <div class="stat-label">&Uuml;berstunden</div>
      </div>
    </div>
  `;
}

function startLiveClock(host) {
  if (state.liveClock) clearInterval(state.liveClock);
  state.liveClock = setInterval(() => {
    const el = host.querySelector('#live-time');
    if (el) el.textContent = new Date().toLocaleTimeString('de-DE');
  }, 1000);
}

function bindClockButtons() {
  $$('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      btn.disabled = true;
      api('/api/' + action.replace('-', '/'), { method: 'POST' })
        .then(() => refreshToday())
        .then(d => {
          state.today = d;
          const host = $('#content');
          if (host && state.view === 'clock') renderClock(host);
        })
        .catch(err => { alert(err.message); btn.disabled = false; });
    });
  });
}

// ─── Overview View ─────────────────────────────────────
function renderOverview(host) {
  host.innerHTML = `
    <div class="card">
      <div class="sub-nav">
        <button class="sub-nav-btn" data-sub="day">Tag</button>
        <button class="sub-nav-btn" data-sub="week">Woche</button>
        <button class="sub-nav-btn active" data-sub="month">Monat</button>
      </div>
      <div id="overview-content"></div>
    </div>
  `;

  host.querySelectorAll('.sub-nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      host.querySelectorAll('.sub-nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderOverviewSub(btn.dataset.sub);
    });
  });

  renderOverviewSub('month');
}

function renderOverviewSub(sub) {
  const oc = $('#overview-content');
  if (!oc) return;
  if (sub === 'day') renderDayView(oc);
  else if (sub === 'week') renderWeekView(oc);
  else if (sub === 'month') renderMonthView(oc);
}

function renderDayView(host) {
  const d = state._ovDay || todayStr();
  host.innerHTML = `
    <div class="form-row">
      <div class="form-group">
        <label>Datum</label>
        <input type="date" id="ov-day" value="${d}">
      </div>
    </div>
    <div id="ov-day-content"></div>
  `;

  $('#ov-day').addEventListener('change', e => {
    state._ovDay = e.target.value;
    loadDayEntries(e.target.value);
  });

  loadDayEntries(d);
}

function loadDayEntries(date) {
  const host = $('#ov-day-content');
  if (!host) return;
  host.innerHTML = '<p class="text-secondary">Lade...</p>';

  Promise.all([
    api('/api/entries?date=' + date),
    api('/api/settings')
  ]).then(([entries, settings]) => {
    const weekly = settings.weekly_hours;
    const targetMin = (new Date(date + 'T12:00:00').getDay() % 6 === 0) ? 0 : Math.round(weekly / 5 * 60);

    if (entries.length === 0) {
      host.innerHTML = `<div class="empty-state">Keine Eintr&auml;ge f&uuml;r diesen Tag</div>`;
      return;
    }

    let total = 0, totalPause = 0;
    let html = `<div class="table-wrap"><table>
      <tr><th>Kommen</th><th>Gehen</th><th>Pause</th><th>Zeit</th><th>Soll</th><th>&Uuml;berstd.</th><th></th></tr>`;

    entries.forEach(e => {
      const work = calcWorkMin(e);
      const pause = calcPauseMin(e);
      total += work;
      totalPause += pause;
      const ot = work - targetMin;
      const otCls = ot >= 0 ? 'stat-value--positive' : 'stat-value--negative';
      html += `<tr>
        <td>${e.clock_in || '-'}</td>
        <td>${e.clock_out || '-'}</td>
        <td>${e.pause_start && e.pause_end ? fmtMinShort(pause) : '-'}</td>
        <td>${fmtMinShort(work)}</td>
        <td>${fmtMinShort(targetMin)}</td>
        <td class="${otCls}">${ot >= 0 ? '+' : ''}${fmtMinShort(ot)}</td>
        <td><button class="btn btn-ghost btn-sm" onclick="editEntry(${e.id}, '${e.date}')">&#9998;</button></td>
      </tr>`;
    });

    const totalOt = total - (targetMin * entries.length);
    html += `<tr style="font-weight:600">
      <td></td><td></td><td>Summe Pause: ${fmtMinShort(totalPause)}</td>
      <td>${fmtMinShort(total)}</td>
      <td>${fmtMinShort(targetMin * entries.length)}</td>
      <td class="${totalOt >= 0 ? 'stat-value--positive' : 'stat-value--negative'}">${totalOt >= 0 ? '+' : ''}${fmtMinShort(totalOt)}</td>
      <td></td>
    </tr>`;
    html += '</table></div>';
    host.innerHTML = html;
  }).catch(err => { host.innerHTML = `<div class="empty-state">Fehler: ${err.message}</div>`; });
}

function calcWorkMin(e) {
  const ci = parseHHMM(e.clock_in);
  const co = parseHHMM(e.clock_out);
  const ps = parseHHMM(e.pause_start);
  const pe = parseHHMM(e.pause_end);
  if (ci == null || co == null) return 0;
  let t = co - ci;
  if (ps != null && pe != null) t -= (pe - ps);
  return Math.max(0, t);
}

function calcPauseMin(e) {
  const ps = parseHHMM(e.pause_start);
  const pe = parseHHMM(e.pause_end);
  if (ps != null && pe != null) return Math.max(0, pe - ps);
  return 0;
}

function getWeekDatesForCheck(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const day = d.getDay();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((day + 6) % 7));
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const dd = new Date(monday);
    dd.setDate(monday.getDate() + i);
    dates.push(dd.toISOString().slice(0, 10));
  }
  return dates;
}

// ─── Week View ────────────────────────────────────────
function renderWeekView(host) {
  const d = state._ovWeek || todayStr();
  host.innerHTML = `
    <div class="form-row">
      <div class="form-group">
        <label>Woche (Tag in der Woche)</label>
        <input type="date" id="ov-week" value="${d}">
      </div>
    </div>
    <div id="ov-week-content"></div>
  `;

  $('#ov-week').addEventListener('change', e => {
    state._ovWeek = e.target.value;
    loadWeek(e.target.value);
  });

  loadWeek(d);
}

function loadWeek(date) {
  const host = $('#ov-week-content');
  if (!host) return;
  host.innerHTML = '<p class="text-secondary">Lade...</p>';

  const now = new Date();
  const weekDates = getWeekDatesForCheck(date);
  const today = todayStr();
  const isCurrentWeek = weekDates.includes(today);
  const maxDateParam = isCurrentWeek ? `&max_date=${today}` : '';

  api('/api/week?date=' + date + maxDateParam).then(days => {
    const maxMin = Math.max(...days.map(d => d.working_minutes), 480);
    let totalWork = 0, totalTarget = 0, totalOt = 0;

    let html = '';
    days.forEach(d => {
      totalWork += d.working_minutes;
      totalTarget += d.target_minutes;
      totalOt += d.overtime_minutes;

      const pct = Math.min(100, (d.working_minutes / Math.max(maxMin, 1)) * 100);
      let barClass = 'week-bar--missing';
      if (d.working_minutes > 0 && d.working_minutes >= d.target_minutes) barClass = 'week-bar--ok';
      else if (d.working_minutes > 0) barClass = 'week-bar--partial';

      const isWeekend = d.day_name === 'Sa' || d.day_name === 'So';

      html += `<div class="week-row">
        <div style="width:40px;font-size:0.85rem;font-weight:600">${d.day_name}</div>
        <div class="week-day" style="flex:1">
          <div class="week-bar-wrap">
            <div class="week-bar ${barClass}" style="width:${pct}%"></div>
            <span class="week-bar-label">${fmtMinShort(d.working_minutes)}${!isWeekend ? ' / ' + fmtMinShort(d.target_minutes) : ' (frei)'}</span>
          </div>
        </div>
      </div>`;
    });

    const otLabel = isCurrentWeek ? '&Uuml;berstd. (bis heute):' : '&Uuml;berstd.:';
    html += `<div style="margin-top:1rem;display:flex;gap:2rem;flex-wrap:wrap;font-size:0.9rem">
      <span><strong>Ist:</strong> ${fmtMinShort(totalWork)}</span>
      <span><strong>Soll:</strong> ${fmtMinShort(totalTarget)}</span>
      <span style="color:${totalOt >= 0 ? 'var(--green)' : 'var(--red)'}"><strong>${otLabel}</strong> ${totalOt >= 0 ? '+' : ''}${fmtMinShort(totalOt)}</span>
    </div>`;

    host.innerHTML = html;
  }).catch(err => { host.innerHTML = `<div class="empty-state">Fehler: ${err.message}</div>`; });
}

// ─── Month View ────────────────────────────────────────
function renderMonthView(host) {
  const now = new Date();
  const y = state._ovMonthYear || now.getFullYear();
  const m = state._ovMonth || (now.getMonth() + 1);

  host.innerHTML = `
    <div class="form-row">
      <div class="form-group">
        <label>Monat</label>
        <input type="month" id="ov-month" value="${y}-${String(m).padStart(2, '0')}">
      </div>
    </div>
    <div id="ov-month-content"></div>
  `;

  $('#ov-month').addEventListener('change', e => {
    const [yr, mo] = e.target.value.split('-');
    state._ovMonthYear = parseInt(yr);
    state._ovMonth = parseInt(mo);
    loadMonth(parseInt(yr), parseInt(mo));
  });

  loadMonth(y, m);
}

function loadMonth(year, month) {
  const host = $('#ov-month-content');
  if (!host) return;
  host.innerHTML = '<p class="text-secondary">Lade...</p>';

  const now = new Date();
  const isCurrentMonth = year === now.getFullYear() && month === (now.getMonth() + 1);
  const maxDayParam = isCurrentMonth ? `&max_day=${now.getDate()}` : '';

  api(`/api/month?year=${year}&month=${month}${maxDayParam}`).then(data => {
    const firstDay = new Date(year, month - 1, 1).getDay(); // 0=Sun
    const offset = (firstDay + 6) % 7; // 0=Mon
    const today = todayStr();

    const typeNames = { vacation: 'Urlaub', sick: 'Krank', holiday: 'Feiertag', bbs: 'BBS', other: 'Sonstige' };

    // Absence lookup
    const absMap = {};
    data.absences.forEach(a => {
      const sd = new Date(a.start_date + 'T12:00:00');
      const ed = new Date(a.end_date + 'T12:00:00');
      for (let d = new Date(sd); d <= ed; d.setDate(d.getDate() + 1)) {
        const ds = d.toISOString().slice(0, 10);
        absMap[ds] = a.type;
      }
    });

    let html = `<div class="month-grid">
      <div class="month-header">Mo</div><div class="month-header">Di</div><div class="month-header">Mi</div>
      <div class="month-header">Do</div><div class="month-header">Fr</div><div class="month-header">Sa</div>
      <div class="month-header">So</div>`;

    // Empty cells
    for (let i = 0; i < offset; i++) {
      html += '<div class="month-day month-day--empty"></div>';
    }

    const ot = data.totals.overtime_minutes;
    const otCls = ot >= 0 ? 'stat-value--positive' : 'stat-value--negative';

    for (let d = 1; d <= 31; d++) {
      if (d > data.days.length) break;
      const day = data.days[d - 1];
      if (!day) break;

      const ds = day.date;
      let cls = '';
      let info = '';

      if (day.day_name === 'Sa' || day.day_name === 'So') {
        cls = 'month-day--weekend';
      } else if (absMap[ds]) {
        cls = absMap[ds] === 'vacation' ? 'month-day--vacation' :
              absMap[ds] === 'sick' ? 'month-day--sick' :
              absMap[ds] === 'bbs' ? 'month-day--bbs' : 'month-day--partial';
        info = typeNames[absMap[ds]] || '';
      } else if (day.working_minutes > 0 && day.working_minutes >= day.target_minutes) {
        cls = 'month-day--worked';
        info = fmtMinShort(day.working_minutes);
      } else if (day.working_minutes > 0) {
        cls = 'month-day--partial';
        info = fmtMinShort(day.working_minutes);
      }

      if (ds === today) cls += ' month-day--today';

      html += `<div class="month-day ${cls}">
        <div class="month-day-num">${d}</div>
        <div class="month-day-info">${info}</div>
      </div>`;
    }

    html += '</div>';

    const otLabel = isCurrentMonth ? '&Uuml;berstd. (bis heute):' : '&Uuml;berstd.:';
    html += `<div style="margin-top:1rem;display:flex;gap:1.5rem;flex-wrap:wrap;font-size:0.9rem">
      <span><strong>Ist:</strong> ${fmtMinShort(data.totals.working_minutes)}</span>
      <span><strong>Soll:</strong> ${fmtMinShort(data.totals.target_minutes)}</span>
      <span style="color:${ot >= 0 ? 'var(--green)' : 'var(--red)'}"><strong>${otLabel}</strong> ${ot >= 0 ? '+' : ''}${fmtMinShort(ot)}</span>
    </div>`;

    host.innerHTML = html;
  }).catch(err => { host.innerHTML = `<div class="empty-state">Fehler: ${err.message}</div>`; });
}

// ─── Absences View ─────────────────────────────────────
function renderAbsences(host) {
  host.innerHTML = `
    <div class="card">
      <h2>Abwesenheit eintragen</h2>
      <div class="form-row">
        <div class="form-group">
          <label>Typ</label>
          <select id="abs-type">
            <option value="vacation">Urlaub</option>
            <option value="sick">Krankheit</option>
            <option value="holiday">Feiertag</option>
            <option value="bbs">BBS</option>
            <option value="other">Sonstige</option>
          </select>
        </div>
        <div class="form-group">
          <label>Start</label>
          <input type="date" id="abs-start">
        </div>
        <div class="form-group">
          <label>Ende</label>
          <input type="date" id="abs-end">
        </div>
        <div class="form-group">
          <label>Halbe Tage</label>
          <select id="abs-half">
            <option value="1">Nein (ganze Tage)</option>
            <option value="0.5">Ja (halbe Tage)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Notiz</label>
          <input type="text" id="abs-note" placeholder="optional">
        </div>
        <div class="form-group">
          <button class="btn btn-primary" id="abs-submit">Speichern</button>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>Bestehende Abwesenheiten</h2>
      <div id="abs-list"></div>
    </div>
  `;

  const today = todayStr();
  $('#abs-start').value = today;
  $('#abs-end').value = today;
  $('#abs-half').value = '1';

  $('#abs-submit').addEventListener('click', () => {
    const type = $('#abs-type').value;
    const start = $('#abs-start').value;
    const end = $('#abs-end').value;
    const half = parseFloat($('#abs-half').value);
    const note = $('#abs-note').value;

    if (!start || !end) { alert('Start- und Enddatum auswählen'); return; }

    // Calculate days
    const sd = new Date(start + 'T12:00:00');
    const ed = new Date(end + 'T12:00:00');
    let days = 0;
    for (let d = new Date(sd); d <= ed; d.setDate(d.getDate() + 1)) {
      if (d.getDay() !== 0 && d.getDay() !== 6) days++;
    }
    if (half === 0.5) days = Math.max(0.5, days * 0.5);

    api('/api/absences', {
      method: 'POST',
      body: JSON.stringify({ type, start_date: start, end_date: end, days, note })
    }).then(() => {
      $('#abs-note').value = '';
      loadAbsencesList();
    }).catch(err => alert(err.message));
  });

  loadAbsencesList();
}

function loadAbsencesList() {
  const host = $('#abs-list');
  if (!host) return;

  api('/api/absences').then(absences => {
    const typeNames = { vacation: 'Urlaub', sick: 'Krankheit', holiday: 'Feiertag', bbs: 'BBS', other: 'Sonstige' };

    if (absences.length === 0) {
      host.innerHTML = '<div class="empty-state">Keine Abwesenheiten eingetragen</div>';
      return;
    }

    let html = `<div class="table-wrap"><table>
      <tr><th>Typ</th><th>Start</th><th>Ende</th><th>Tage</th><th>Notiz</th><th></th></tr>`;
    absences.forEach(a => {
      html += `<tr>
        <td>${typeNames[a.type] || a.type}</td>
        <td>${a.start_date}</td>
        <td>${a.end_date}</td>
        <td>${a.days}</td>
        <td>${a.note || '-'}</td>
        <td><button class="btn btn-red btn-sm" onclick="deleteAbsence(${a.id})">L&ouml;schen</button></td>
      </tr>`;
    });
    html += '</table></div>';
    host.innerHTML = html;
  }).catch(err => { host.innerHTML = `<div class="empty-state">Fehler: ${err.message}</div>`; });
}

function showConfirmModal(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal confirm-modal">
        <p style="margin-bottom:1.5rem;font-size:1rem">${message}</p>
        <div class="btn-group">
          <button class="btn btn-red" id="confirm-yes">L\u00f6schen</button>
          <button class="btn btn-ghost" id="confirm-no">Abbrechen</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    $('#confirm-yes').addEventListener('click', () => { overlay.remove(); resolve(true); });
    $('#confirm-no').addEventListener('click', () => { overlay.remove(); resolve(false); });
    overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
  });
}

async function deleteAbsence(id) {
  const confirmed = await showConfirmModal('Abwesenheit wirklich l\u00f6schen?');
  if (!confirmed) return;
  api('/api/absences/' + id, { method: 'DELETE' }).then(() => loadAbsencesList());
}

// ─── Dashboard View ────────────────────────────────────
function renderDashboard(host) {
  const now = new Date();
  const y = state._dashYear || now.getFullYear();
  const m = state._dashMonth || (now.getMonth() + 1);

  host.innerHTML = `
    <div class="card">
      <div class="flex-between">
        <h2>Dashboard</h2>
        <div class="form-row" style="margin-bottom:0">
          <div class="form-group">
            <input type="month" id="dash-month" value="${y}-${String(m).padStart(2, '0')}">
          </div>
        </div>
      </div>
      <div id="dash-content"></div>
    </div>
  `;

  $('#dash-month').addEventListener('change', e => {
    const [yr, mo] = e.target.value.split('-');
    state._dashYear = parseInt(yr);
    state._dashMonth = parseInt(mo);
    loadDashboard(parseInt(yr), parseInt(mo));
  });

  loadDashboard(y, m);
}

function loadDashboard(year, month) {
  const host = $('#dash-content');
  if (!host) return;
  host.innerHTML = '<p class="text-secondary">Lade...</p>';

  const now = new Date();
  const isCurrentMonth = year === now.getFullYear() && month === (now.getMonth() + 1);
  const maxDayParam = isCurrentMonth ? `&max_day=${now.getDate()}` : '';

  api(`/api/dashboard?year=${year}&month=${month}${maxDayParam}`).then(d => {
    const otClass = d.overtime_minutes >= 0 ? 'stat-value--positive' : 'stat-value--negative';
    const otSign = d.overtime_minutes >= 0 ? '+' : '';

    host.innerHTML = `
      <div class="dash-grid">
        <div class="dash-card">
          <div class="dash-value" style="color:var(--green)">${fmtMinShort(d.working_minutes)}</div>
          <div class="dash-label">Ist-Zeit</div>
        </div>
        <div class="dash-card">
          <div class="dash-value">${fmtMinShort(d.target_minutes)}</div>
          <div class="dash-label">Soll-Zeit (${d.working_days} Tage)</div>
        </div>
        <div class="dash-card">
          <div class="dash-value ${otClass}">${otSign}${fmtMinShort(d.overtime_minutes)}</div>
          <div class="dash-label">&Uuml;berstunden${isCurrentMonth ? ' (bis heute)' : ''}</div>
        </div>
        <div class="dash-card">
          <div class="dash-value" style="color:var(--blue)">${d.vacation_used} / ${d.vacation_total}</div>
          <div class="dash-label">Urlaub (genutzt/gesamt)</div>
        </div>
        <div class="dash-card">
          <div class="dash-value" style="color:var(--orange)">${d.sick_days}</div>
          <div class="dash-label">Krankheitstage</div>
        </div>
        <div class="dash-card">
          <div class="dash-value" style="color:${d.presence_pct >= 80 ? 'var(--green)' : 'var(--red)'}">${d.presence_pct}%</div>
          <div class="dash-label">Anwesenheit</div>
        </div>
      </div>
      <div>
        <h3>Anwesenheit</h3>
        <div class="presence-bar-wrap">
          <div class="presence-bar-fill" style="width:${Math.min(100, d.presence_pct)}%"></div>
        </div>
        <div class="flex-between text-secondary">
          <span>0%</span>
          <span>${d.presence_pct}%</span>
          <span>100%</span>
        </div>
      </div>
    `;
  }).catch(err => { host.innerHTML = `<div class="empty-state">Fehler: ${err.message}</div>`; });
}

// ─── Export View ───────────────────────────────────────
function renderExport(host) {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  host.innerHTML = `
    <div class="card">
      <h2>Export</h2>
      <div class="form-row">
        <div class="form-group">
          <label>Von</label>
          <input type="date" id="exp-from" value="${firstDay.toISOString().slice(0, 10)}">
        </div>
        <div class="form-group">
          <label>Bis</label>
          <input type="date" id="exp-to" value="${lastDay.toISOString().slice(0, 10)}">
        </div>
        <div class="form-group">
          <label>Daten</label>
          <select id="exp-type">
            <option value="all">Zeiten + Abwesenheiten</option>
            <option value="time">Nur Zeiten</option>
            <option value="absence">Nur Abwesenheiten</option>
          </select>
        </div>
        <div class="form-group">
          <label>&nbsp;</label>
          <button class="btn btn-primary" id="exp-btn">CSV Exportieren</button>
        </div>
      </div>
    </div>
  `;

  $('#exp-btn').addEventListener('click', () => {
    const from = $('#exp-from').value;
    const to = $('#exp-to').value;
    const type = $('#exp-type').value;

    if (!from || !to) { alert('Zeitraum wählen'); return; }

    const url = `/api/export/csv?from_date=${from}&to_date=${to}&type=${type}`;
    window.open(url, '_blank');
  });
}

// ─── Settings View ─────────────────────────────────────
function renderSettings(host) {
  const userName = localStorage.getItem('timy_user_name') || 'Benutzer';
  api('/api/settings').then(s => {
    host.innerHTML = `
      <div class="card">
        <div class="flex-between">
          <h2>Einstellungen</h2>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Name</label>
            <input type="text" id="set-name" value="${s.employee_name}">
          </div>
          <div class="form-group">
            <label>Wochenstunden</label>
            <input type="number" id="set-hours" value="${s.weekly_hours}" step="0.5" min="1" max="80">
          </div>
          <div class="form-group">
            <label>Urlaubstage / Jahr</label>
            <input type="number" id="set-vacation" value="${s.vacation_days}" step="0.5" min="0" max="50">
          </div>
          <div class="form-group">
            <label>&nbsp;</label>
            <button class="btn btn-primary" id="set-save">Speichern</button>
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Benutzer</h2>
        <p class="mb-1">Angemeldet als: <strong>${userName}</strong></p>
        <button class="btn btn-ghost" id="set-logout">Abmelden</button>
      </div>
      <div class="card">
        <p class="text-secondary" style="font-size:0.8rem">Datenbank: data/timy.db (SQLite, lokal, offline)</p>
      </div>
    `;

    $('#set-save').addEventListener('click', () => {
      const name = $('#set-name').value;
      const hours = parseFloat($('#set-hours').value);
      const vacation = parseFloat($('#set-vacation').value);
      if (!name || !hours || !vacation) { alert('Alle Felder ausfüllen'); return; }
      api('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({ employee_name: name, weekly_hours: hours, vacation_days: vacation })
      }).then(() => { alert('Gespeichert'); }).catch(err => alert(err.message));
    });

    $('#set-logout').addEventListener('click', () => {
      localStorage.removeItem('timy_user_id');
      localStorage.removeItem('timy_user_name');
      $('header').classList.add('hidden');
      navInitialized = false;
      renderLogin();
    });
  });
}

// ─── Manual Entry Modal ────────────────────────────────
function showManualEntry() {
  const d = todayStr();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <h2>Manuelle Buchung</h2>
      <div class="form-row">
        <div class="form-group">
          <label>Datum</label>
          <input type="date" id="me-date" value="${d}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Kommen</label>
          <input type="time" id="me-in">
        </div>
        <div class="form-group">
          <label>Gehen</label>
          <input type="time" id="me-out">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Pause Start</label>
          <input type="time" id="me-ps">
        </div>
        <div class="form-group">
          <label>Pause Ende</label>
          <input type="time" id="me-pe">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group" style="flex:1">
          <label>Notiz</label>
          <input type="text" id="me-note" placeholder="optional">
        </div>
      </div>
      <div class="btn-group">
        <button class="btn btn-primary" id="me-save">Speichern</button>
        <button class="btn btn-ghost" id="me-cancel">Abbrechen</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  $('#me-cancel').addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

  $('#me-save').addEventListener('click', () => {
    const date = $('#me-date').value;
    const clock_in = $('#me-in').value || null;
    const clock_out = $('#me-out').value || null;
    const pause_start = $('#me-ps').value || null;
    const pause_end = $('#me-pe').value || null;
    const note = $('#me-note').value;

    api('/api/entries', {
      method: 'POST',
      body: JSON.stringify({ date, clock_in, clock_out, pause_start, pause_end, note, is_manual: 1 })
    }).then(() => {
      overlay.remove();
      if (state.view === 'clock') refreshToday().then(d => renderView('clock'));
    }).catch(err => alert(err.message));
  });
}

// ─── Edit Entry Modal ──────────────────────────────────
function editEntry(id, date) {
  if (!date) date = todayStr();
  api('/api/entries?date=' + date).then(entries => {
    const e = entries.find(x => x.id === id);
    if (!e) { alert('Eintrag nicht gefunden'); return; }

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h2>Eintrag bearbeiten</h2>
        <div class="form-row">
          <div class="form-group">
            <label>Kommen</label>
            <input type="time" id="ee-in" value="${e.clock_in || ''}">
          </div>
          <div class="form-group">
            <label>Gehen</label>
            <input type="time" id="ee-out" value="${e.clock_out || ''}">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Pause Start</label>
            <input type="time" id="ee-ps" value="${e.pause_start || ''}">
          </div>
          <div class="form-group">
            <label>Pause Ende</label>
            <input type="time" id="ee-pe" value="${e.pause_end || ''}">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:1">
            <label>Notiz</label>
            <input type="text" id="ee-note" value="${e.note || ''}">
          </div>
        </div>
        <div class="btn-group">
          <button class="btn btn-primary" id="ee-save">Speichern</button>
          <button class="btn btn-ghost" id="ee-cancel">Abbrechen</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    $('#ee-cancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

    $('#ee-save').addEventListener('click', () => {
      api('/api/entries/' + id, {
        method: 'PUT',
        body: JSON.stringify({
          date: e.date,
          clock_in: $('#ee-in').value || null,
          clock_out: $('#ee-out').value || null,
          pause_start: $('#ee-ps').value || null,
          pause_end: $('#ee-pe').value || null,
          note: $('#ee-note').value
        })
      }).then(() => {
        overlay.remove();
        if (state.view === 'overview') renderView('overview');
      }).catch(err => alert(err.message));
    });
  });
}

// ─── Login ──────────────────────────────────────────────
function renderLogin() {
  const content = $('#content');
  content.innerHTML = `
    <div class="login-page">
      <div class="login-box">
        <h1><span class="logo-icon">&#9200;</span> timy</h1>
        <p class="text-secondary" style="margin-bottom:1.5rem">Lokale Zeiterfassung</p>
        <div style="display:flex;flex-direction:column;gap:0.75rem">
          <div class="form-group">
            <label>Benutzername</label>
            <input type="text" id="login-name" placeholder="z.B. Admin">
          </div>
          <div class="form-group">
            <label>PIN</label>
            <input type="password" id="login-pin" placeholder="0000">
          </div>
          <button class="btn btn-primary" id="login-btn" style="width:100%;margin-top:0.5rem">Anmelden</button>
          <p class="text-secondary" style="font-size:0.8rem;text-align:center">
            Noch kein Benutzer?
            <a href="#" id="login-register-link" style="color:var(--primary)">Neuen anlegen</a>
          </p>
          <p id="login-error" style="color:var(--red);display:none;text-align:center;font-size:0.85rem"></p>
        </div>
      </div>
    </div>
  `;

  const doLogin = () => {
    const name = $('#login-name').value.trim();
    const pin = $('#login-pin').value;
    if (!name || !pin) { showLoginError('Name und PIN eingeben'); return; }
    api('/api/login', { method: 'POST', body: JSON.stringify({ name, pin }) })
      .then(res => {
        if (res.success) {
          localStorage.setItem('timy_user_id', res.user.id);
          localStorage.setItem('timy_user_name', res.user.name);
          showApp();
        }
      })
      .catch(err => showLoginError(err.message));
  };

  function showLoginError(msg) {
    const el = $('#login-error');
    el.textContent = msg;
    el.style.display = 'block';
  }

  $('#login-btn').addEventListener('click', doLogin);
  $('#login-pin').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

  $('#login-register-link').addEventListener('click', e => {
    e.preventDefault();
    showRegisterModal().then(({ name, pin }) => {
      if (!name) return;
      api('/api/users', { method: 'POST', body: JSON.stringify({ name, pin }) })
        .then(() => {
          $('#login-name').value = name;
          $('#login-pin').value = pin;
          doLogin();
        })
        .catch(err => showLoginError(err.message));
    });
  });
}

function showRegisterModal() {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h2>Neuen Benutzer anlegen</h2>
        <div class="form-row">
          <div class="form-group" style="flex:1">
            <label>Benutzername</label>
            <input type="text" id="reg-name" placeholder="z.B. Max">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:1">
            <label>PIN (mindestens 4 Zeichen)</label>
            <input type="password" id="reg-pin" placeholder="0000">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:1">
            <label>PIN wiederholen</label>
            <input type="password" id="reg-pin2" placeholder="0000">
          </div>
        </div>
        <p id="reg-error" style="color:var(--red);display:none;font-size:0.85rem;margin-bottom:0.5rem"></p>
        <div class="btn-group">
          <button class="btn btn-primary" id="reg-save">Anlegen</button>
          <button class="btn btn-ghost" id="reg-cancel">Abbrechen</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    function close() { overlay.remove(); resolve({}); }

    $('#reg-cancel').addEventListener('click', close);
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

    $('#reg-save').addEventListener('click', () => {
      const name = $('#reg-name').value.trim();
      const pin = $('#reg-pin').value;
      const pin2 = $('#reg-pin2').value;
      const errEl = $('#reg-error');
      if (!name) { errEl.textContent = 'Benutzername eingeben'; errEl.style.display = 'block'; return; }
      if (pin.length < 4) { errEl.textContent = 'PIN muss mindestens 4 Zeichen haben'; errEl.style.display = 'block'; return; }
      if (pin !== pin2) { errEl.textContent = 'PINs stimmen nicht überein'; errEl.style.display = 'block'; return; }
      overlay.remove();
      resolve({ name, pin });
    });

    $('#reg-name').addEventListener('keydown', e => { if (e.key === 'Enter') $('#reg-pin').focus(); });
    $('#reg-pin').addEventListener('keydown', e => { if (e.key === 'Enter') $('#reg-pin2').focus(); });
    $('#reg-pin2').addEventListener('keydown', e => { if (e.key === 'Enter') $('#reg-save').click(); });
  });
}

function showApp() {
  const header = $('header');
  if (header) header.classList.remove('hidden');
  if (!navInitialized) {
    initNav();
    navInitialized = true;
  }
  state.view = 'clock';
  renderView('clock');
}

// ─── Dark Mode ─────────────────────────────────────────
function initDarkMode() {
  const saved = localStorage.getItem('timy-dark') === 'true';
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved || (!('timy-dark' in localStorage) && prefersDark)) {
    document.body.classList.add('dark');
  }
  $('#darkmode-toggle').addEventListener('click', () => {
    document.body.classList.toggle('dark');
    localStorage.setItem('timy-dark', document.body.classList.contains('dark'));
  });
}

// ─── Init ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();
  const userId = localStorage.getItem('timy_user_id');
  if (userId) {
    showApp();
  } else {
    $('header').classList.add('hidden');
    renderLogin();
  }
});
