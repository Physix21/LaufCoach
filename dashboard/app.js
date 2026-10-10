'use strict';

// Datumslogik ohne UTC-Verschiebung: Ein Wochenwechsel gilt im lokalen Kalender.
function localDate(value = new Date()) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}
function mondayFor(value) {
  const day = new Date(value + 'T12:00:00');
  day.setDate(day.getDate() - (day.getDay() + 6) % 7);
  return localDate(day);
}
function addDays(value, days) {
  const day = new Date(value + 'T12:00:00');
  day.setDate(day.getDate() + days);
  return localDate(day);
}
function nearTermWeeks(weeks, today) {
  const monday = mondayFor(today);
  return [monday, addDays(monday, 7)].map(start => {
    const found = weeks.find(week => week.plan.week_start === start);
    return found && !found.plan.generated ? found : {
      plan: {week_start: start, week_end: addDays(start, 6), planned_sessions: []},
      warnings: [], week_summary: {}, intensity: {}, missing: true
    };
  });
}
function sessionStatus(session, today) {
  if (session.display_status === 'erledigt') return session.matched_activity_id ? 'Aktivität zugeordnet' : 'Erledigt';
  if (session.display_status === 'optional') return 'Optional';
  if (session.scheduled_date < today) return session.type === 'strength' ? 'Status nicht erfasst' : 'Nicht dokumentiert';
  return session.scheduled_date === today ? 'Heute geplant' : 'Geplant';
}
function formatPace(seconds) {
  if (seconds == null) return '–';
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')} min/km`;
}
if (typeof module !== 'undefined') module.exports = {localDate, mondayFor, addDays, nearTermWeeks, sessionStatus, formatPace};

if (typeof document !== 'undefined') (() => {
  const d = window.DASHBOARD_DATA;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const num = (value, digits = 1) => value == null || value === '' ? '–' : Number(value).toLocaleString('de-DE', {maximumFractionDigits: digits});
  const fmtDate = value => value ? new Intl.DateTimeFormat('de-DE', {day:'2-digit', month:'2-digit', year:'numeric'}).format(new Date(value + 'T12:00:00')) : '–';
  const dayDate = value => new Intl.DateTimeFormat('de-DE', {weekday:'short', day:'2-digit', month:'2-digit'}).format(new Date(value + 'T12:00:00'));
  const sport = value => ({run:'Lauf', bike:'Rad', strength:'Kraft', rest:'Ruhetag'}[value] || value);
  const row = (label, value) => value ? `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>` : '';
  const weekNumber = value => {
    const day = new Date(value + 'T12:00:00Z');
    day.setUTCDate(day.getUTCDate() + 4 - (day.getUTCDay() || 7));
    return Math.ceil(((day - Date.UTC(day.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
  };
  const sessionCard = (s, today) => {
    const done = s.display_status === 'erledigt';
    const status = sessionStatus(s, today);
    const extra = row('Geräte & Aufbau', s.setup) + row(s.type === 'run' ? 'Rad statt Lauf' : 'Übungsalternativen', s.alternatives) + row('Belastungsziel', s.rpe_target ? `RPE ${s.rpe_target}` : '');
    const actual = s.matched_activity_id && d.recent_activities.find(a => a.activity_id === s.matched_activity_id);
    return `<article class="session ${done ? 'done' : ''} ${s.target_intensity === 'hard' ? 'quality' : ''}">
      <div class="session-top"><span>${esc(dayDate(s.scheduled_date))} · ${esc(sport(s.type))}</span><span class="badge ${done ? 'done' : ''}">${esc(status)}</span></div>
      <h4>${esc(s.title)}</h4>
      <p class="session-target">${s.duration_is_estimate ? 'ca. ' : ''}${num(s.target_duration_min)} min gesamt${s.target_distance_km ? ` · ca. ${num(s.target_distance_km)} km` : ''}</p>
      <p class="pace">${esc(s.target_pace)}</p>
      ${s.condition ? `<p class="session-condition"><strong>Voraussetzung:</strong> ${esc(s.condition)}</p>` : ''}
      <dl class="workout">${row(s.type === 'strength' ? 'Aufwärmen' : 'Einlaufen', s.warmup)}${row('Hauptteil', s.main_set)}${row('Pausen', s.recovery)}${row(s.type === 'strength' ? 'Abschluss' : 'Auslaufen', s.cooldown)}</dl>
      ${s.description ? `<p class="session-note">${esc(s.description)}</p>` : ''}
      ${s.completion_note ? `<p class="matched"><strong>Ausgeführt:</strong> ${esc(s.completion_note)}</p>` : ''}
      ${s.fallback ? `<p class="session-note"><strong>Falls noch nicht passend:</strong> ${esc(s.fallback)}</p>` : ''}
      ${actual ? `<p class="matched">Zugeordnet: ${esc(sport(actual.sport))} am ${fmtDate(actual.date)} · ${num(actual.duration_min)} min. Vorgaben oben bleiben der Plan.</p>` : ''}
      ${extra ? `<details class="session-extra"><summary>${s.type === 'run' ? 'Radalternative & Belastungsziel' : 'Geräte, Alternativen & Belastungsziel'}</summary><dl>${extra}</dl></details>` : ''}
    </article>`;
  };
  const weekContent = (week, title, today, id = '') => {
    const p = week.plan;
    const sessions = [...(p.planned_sessions || [])].filter(s => s.type !== 'plan').sort((a,b) => (a.scheduled_date || '').localeCompare(b.scheduled_date || '') || (a.priority || 0) - (b.priority || 0));
    const runs = sessions.filter(s => s.type === 'run');
    const strength = sessions.filter(s => s.type === 'strength');
    return `<section ${id ? `id="${id}"` : ''} class="week" aria-label="${esc(title)}">
      <div class="week-heading"><div><p class="eyebrow">KW ${weekNumber(p.week_start)} · ${fmtDate(p.week_start)}–${fmtDate(p.week_end)}</p><h3>${esc(title)}</h3></div>${p.provisional ? '<span class="badge">Anpassbarer Sollplan</span>' : ''}</div>
      ${sessions.length ? `<p class="week-total">${runs.length} Läufe · ${strength.length} Kraft · ca. ${num(runs.reduce((sum,s) => sum + (s.target_distance_km || 0), 0))} km Laufen</p><p class="week-focus">${esc(p.focus)}</p>${p.planning_note ? `<p class="planning-note">${esc(p.planning_note)}</p>` : ''}<div class="sessions">${sessions.map(s => sessionCard(s, today)).join('')}</div><p class="rest-note">An den übrigen Tagen: Erholung. Verschobene Einheiten mit ausreichendem Abstand planen; ausgefallene Einheiten nicht nachholen.</p>` : '<p class="notice">Für diese Woche ist noch kein konkreter Trainingsplan hinterlegt. Bitte den Wochenplan aktualisieren.</p>'}
    </section>`;
  };
  const metrics = entries => entries.map(([label, value]) => `<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join('');

  let selectedWeekStart = '';
  function renderPlanner(today) {
    const all = (d.plan_weeks || []).filter(w => !w.plan.generated).sort((a,b) => a.plan.week_start.localeCompare(b.plan.week_start));
    const select = $('plan-week-select');
    select.innerHTML = '<option value="">Diese &amp; nächste Woche</option>' + all.map(w => `<option value="${esc(w.plan.week_start)}">KW ${weekNumber(w.plan.week_start)} · ${fmtDate(w.plan.week_start)} · ${esc(w.plan.focus)}</option>`).join('');
    select.value = selectedWeekStart;
    const selected = all.find(w => w.plan.week_start === selectedWeekStart);
    $('weeks').hidden = Boolean(selected);
    $('other-week').hidden = !selected;
    $('other-week').innerHTML = selected ? weekContent(selected, selected.plan.phase || 'Trainingswoche', today) : '';
    const index = all.findIndex(w => w.plan.week_start === (selectedWeekStart || mondayFor(today)));
    $('previous-week').disabled = index <= 0;
    $('next-week').disabled = index < 0 || index >= all.length - 1;
    $('plan-selection-status').textContent = selected ? `Woche ${index+1} von ${all.length} · ${fmtDate(selected.plan.week_start)}–${fmtDate(selected.plan.week_end)}` : `${all.length} konkrete Planwochen · aktuelle und nächste Woche im Überblick`;
    const choose = start => { selectedWeekStart = start; renderPlanner(localDate()); };
    select.onchange = () => choose(select.value);
    $('previous-week').onclick = () => { if (index > 0) choose(all[index-1].plan.week_start); };
    $('next-week').onclick = () => { if (index >= 0 && index < all.length-1) choose(all[index+1].plan.week_start); };
    $('show-near-weeks').onclick = () => choose('');
    $('nav-current').onclick = () => choose('');
    $('nav-next').onclick = () => choose('');
    for (const [id,goal] of [['show-test-week', d.season?.test_goal], ['show-race-week', d.season?.primary_goal]]) {
      const start = goal?.date ? mondayFor(goal.date) : '';
      $(id).disabled = !all.some(w => w.plan.week_start === start);
      $(id).onclick = () => choose(start);
    }
  }

  function renderCalendar() {
    const today = localDate();
    const weeks = nearTermWeeks(d.plan_weeks || [], today);
    $('weeks').innerHTML = weeks.map((w,i) => weekContent(w, i ? 'Nächste Woche' : 'Diese Woche', today, i ? 'naechste-woche' : 'diese-woche')).join('');
    $('plan-alert').innerHTML = weeks.some(w => w.missing || !w.plan.planned_sessions.length) ? '<p class="notice">Die Planung deckt die nächsten zwei Wochen noch nicht vollständig ab. Fehlende Wochen werden nicht automatisch aus dem Jahresplan abgeleitet.</p>' : '';
    const current = weeks[0];
    $('plan-alert').innerHTML += (current.warnings || []).filter(w => ['warning', 'critical'].includes(w.level)).map(w => `<p class="notice ${esc(w.level)}">${esc(w.text)}</p>`).join('');
    const summary = current.week_summary || {};
    $('summary-period').textContent = `Diese Woche · ${fmtDate(current.plan.week_start)}–${fmtDate(current.plan.week_end)}`;
    $('week-metrics').innerHTML = metrics([['Laufen erfasst',`${num(summary.run_km ?? 0)} km`],['Läufe erfasst',summary.run_sessions ?? 0],['Rad erfasst',`${num(summary.bike_hours ?? 0)} h`]]);
    $('warnings').innerHTML = (current.warnings || []).filter(w => !w.text.includes('Prioritätseinheit')).map(w => `<p class="notice ${esc(w.level)}">${esc(w.text)}</p>`).join('') || '<p class="muted">Keine weiteren Trainingshinweise hinterlegt.</p>';
    const intensity = current.intensity || {};
    $('intensity').textContent = `Erfasste Ausdauereinheiten: ${intensity.LIT || 0} locker · ${intensity.moderate || 0} moderat · ${intensity.hard || 0} hart. Gezählt werden ganze Einheiten, keine Zeitanteile.`;
    const unmatched = current.unmatched_activities || [];
    $('unmatched').textContent = unmatched.length ? `${unmatched.length} Aktivitäten ohne Planzuordnung: ${unmatched.map(a => a.session_name).join(', ')}` : '';
    renderPlanner(today);
    const pr = d.progression_roadmap;
    $('roadmap').innerHTML = pr.rows.map(p => `<article class="phase ${p.start <= today && today <= p.end ? 'current' : ''}"><p class="eyebrow">${esc(p.period)}</p><h4>${esc(p.phase)}</h4><p>${esc(p.focus)}</p></article>`).join('');
  }
  const last = d.recent_activities[0];
  $('data-status').innerHTML = `Letzte Aktivität<br><strong>${last ? fmtDate(last.date) : 'Noch keine erfasst'}</strong>`;
  const weeks = d.weekly_summary;
  const max = Math.max(1, ...weeks.map(w => w.run_km));
  $('weekly-chart').innerHTML = weeks.map(w => `<div class="bar-column" role="listitem" aria-label="${esc(w.week_label)} ab ${fmtDate(w.week_start)}: ${num(w.run_km)} km"><strong>${num(w.run_km)}</strong><div class="bar-track"><i style="height:${w.run_km / max * 100}%"></i></div><span>${esc(w.week_label)}</span></div>`).join('');
  $('activities').innerHTML = d.recent_activities.map(a => `<article class="activity"><div><p class="eyebrow">${fmtDate(a.date)} · ${esc(sport(a.sport))}</p><h3>${esc(a.session_name)}</h3></div><p>${num(a.duration_min)} min${a.distance_km != null ? ` · ${num(a.distance_km,2)} km` : ''} · ${a.sport === 'bike' ? (a.avg_power != null ? `${num(a.avg_power,0)} W` : 'Leistung fehlt') : formatPace(a.avg_pace_sec_per_km)}</p><details><summary>Messwerte & Notizen</summary><dl>${row('Herzfrequenz', `${num(a.avg_hr,0)} Ø / ${num(a.max_hr,0)} max bpm`)}${row('Intensität', ({LIT:'Locker', moderate:'Moderat', hard:'Hart'}[a.intensity] || 'Nicht bestimmt'))}${a.rpe != null ? row('RPE',a.rpe) : ''}${row('Notizen',a.notes || 'Keine hinterlegt')}</dl></details></article>`).join('') || '<p class="muted">Noch keine Aktivitäten importiert.</p>';
  const g = d.metrics.goal;
  $('goal-metrics').innerHTML = metrics([[`5-km-Anker · ${fmtDate(g.current_5k_date)}`,g.current_5k],['Ziel · 22.06.2027',`${g.target_5k} · ${g.target_pace}`],['Abstand zum Ziel',g.gap_to_goal]]);
  $('season-goals').innerHTML = d.season ? [d.season.test_goal, d.season.primary_goal].map((goal,i) => `<article><p class="eyebrow">${i ? 'HAUPTZIEL' : 'ZWISCHENTEST'}</p><h2>${esc(goal.title)}</h2><p>${fmtDate(goal.date)} · ${esc(goal.date_status)}</p></article>`).join('') : '';
  $('rep-target-note').textContent = d.repetition_targets.note;
  $('rep-targets').innerHTML = d.repetition_targets.rows.map(r => `<article class="target"><h4>${r.distance_m} m</h4><dl>${row('Zielsplit', `${r.target_label} · ${r.target_pace_label}`)}${row('Letzte Serie', r.source ? `${r.current_label} · Ø aus ${r.source.repetitions} Wiederholungen am ${fmtDate(r.source.date)}` : 'Keine passende Serie erfasst')}</dl></article>`).join('');
  $('roadmap-note').textContent = 'Phasen aus dem Jahresplan. Die konkreten Trainingsvorgaben stehen in den Wochenplänen oben.';
  $('generated').textContent = new Intl.DateTimeFormat('de-DE', {dateStyle:'medium', timeStyle:'short'}).format(new Date(d.generated_at));
  renderCalendar();
  let renderedDay = localDate();
  const refreshCalendar = () => {
    if (localDate() !== renderedDay) {
      renderedDay = localDate();
      renderCalendar();
    }
  };
  window.addEventListener('focus', refreshCalendar);
  document.addEventListener('visibilitychange', refreshCalendar);
  window.setInterval(refreshCalendar, 60000);
})();
