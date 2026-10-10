'use strict';

const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {mondayFor, addDays, nearTermWeeks, sessionStatus, formatPace} = require('../dashboard/app.js');

test('calendar handles Sunday, Monday, year boundary and daylight saving', () => {
  assert.equal(mondayFor('2030-12-29'), '2030-12-23');
  assert.equal(mondayFor('2030-12-30'), '2030-12-30');
  assert.equal(addDays('2030-12-30', 7), '2031-01-06');
  assert.equal(addDays('2030-03-25', 7), '2030-04-01');
  assert.equal(addDays('2030-10-21', 7), '2030-10-28');
});

test('missing weeks cannot become old plans or generated frames', () => {
  const plans = [{plan:{week_start:'2030-12-23', planned_sessions:[{}]}}, {plan:{week_start:'2030-12-30', generated:true}}];
  const near = nearTermWeeks(plans, '2030-12-29');
  assert.equal(near[0], plans[0]);
  assert.equal(near[1].missing, true);
  assert.deepEqual(near[1].plan.planned_sessions, []);
  assert.equal(nearTermWeeks(plans, '2031-01-01')[0].plan.week_start, '2030-12-30');
  assert.equal(nearTermWeeks([], '2031-01-01')[1].plan.week_start, '2031-01-06');
});

test('status distinguishes a plan from an activity match and missing records', () => {
  const s = {type:'run', scheduled_date:'2030-12-24', display_status:'offen'};
  assert.equal(sessionStatus(s, '2030-12-23'), 'Geplant');
  assert.equal(sessionStatus(s, '2030-12-24'), 'Heute geplant');
  assert.equal(sessionStatus(s, '2030-12-25'), 'Nicht dokumentiert');
  assert.equal(sessionStatus({...s, type:'strength'}, '2030-12-25'), 'Status nicht erfasst');
  assert.equal(sessionStatus({...s, display_status:'erledigt', matched_activity_id:'test'}, '2030-12-25'), 'Aktivität zugeordnet');
});

test('pace rounding never produces 4:60', () => {
  assert.equal(formatPace(299.8), '5:00 min/km');
  assert.equal(formatPace(null), '–');
});

test('full rendering uses real template IDs, shows both weeks and updates on Monday', () => {
  const root = path.resolve(__dirname, '..');
  const template = fs.readFileSync(path.join(root, 'scripts/dashboard_template.html'), 'utf8');
  const elements = Object.fromEntries([...template.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {innerHTML:'', textContent:'', value:'0'}]));
  let now = '2030-12-29T12:00:00';
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } }
  const listeners = {};
  const makeWeek = start => ({plan: {week_start:start, week_end:addDays(start,6), focus:'Test', planned_sessions:[{
    title:'<script>test</script>', type:'run', scheduled_date:addDays(start,1), target_duration_min:30,
    target_pace:'5:30 min/km', warmup:'10 min', main_set:'15 min', recovery:'Keine', cooldown:'5 min', alternatives:'Rad locker'
  }]}, week_summary:{run_km:5, run_sessions:1}, intensity:{LIT:1}, warnings:[]});
  const data = {plan_weeks:[makeWeek('2030-12-23'),makeWeek('2030-12-30')], recent_activities:[], weekly_summary:[],
    progression_roadmap:{rows:[]}, metrics:{goal:{}}, repetition_targets:{rows:[]}, generated_at:'2030-12-29T12:00:00Z'};
  const context = {
    Date:Clock, Intl,
    window:{DASHBOARD_DATA:data, addEventListener:(name, fn) => listeners[name] = fn, setInterval:fn => listeners.tick = fn},
    document:{getElementById:id => {assert.ok(elements[id], `Template ID missing: ${id}`); return elements[id];}, addEventListener:(name,fn) => listeners[name] = fn}
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'dashboard/app.js'), 'utf8'), context);
  const html = elements.weeks.innerHTML;
  assert.ok(html.includes('Diese Woche') && html.includes('Nächste Woche'));
  assert.equal((html.match(/class="workout"/g) || []).length, 2);
  assert.ok(html.includes('5:30 min/km') && html.includes('Einlaufen') && html.includes('Auslaufen'));
  assert.ok(!html.includes('<script>test</script>'));
  assert.ok(html.includes('&lt;script&gt;test&lt;/script&gt;'));
  now = '2030-12-30T00:01:00';
  listeners.focus();
  assert.ok(elements.weeks.innerHTML.includes('06.01.2031'));
  assert.ok(elements['plan-alert'].innerHTML.includes('nicht vollständig'));
  assert.equal(elements['other-weeks-panel'].hidden, false);
  elements['plan-week-select'].onchange();
  assert.ok(elements['other-week'].innerHTML.includes('Gespeicherter Plan'));
});
