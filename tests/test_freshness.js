'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const freshness = require('../docs/freshness.js');
const at = value => Date.parse(value);
const cutoff = '2026-10-14T11:30:00Z';

function snapshot(overrides = {}) {
  return {
    asof: '2026-10-13', generated_utc: cutoff,
    session: {
      calendar: 'NYSE', timezone: 'America/New_York', cutoff_utc: cutoff,
      expected_latest_completed_session: '2026-10-13', expected_latest_completed_close_utc: '2026-10-13T20:00:00Z',
      actual_session: '2026-10-13', actual_close_utc: '2026-10-13T20:00:00Z', lag_sessions: 0,
      next_session: '2026-10-14', next_session_close_utc: '2026-10-14T20:00:00Z',
      status: 'current', fallback_reason: null, ...overrides
    },
    watchlist: [{ticker: 'SOXL', close: 100, day_pct: 1}, {ticker: 'SOXX', close: 200, day_pct: 2}],
    chart: {soxl: [99, 100]}, signal: {regime: 'BULLISH', score: 7, opportunity: 'FAVORABLE', comment: 'Synthetic test', components: []}, backtest: []
  };
}
function fallback() {
  const d = snapshot({actual_session: '2026-10-12', actual_close_utc: '2026-10-12T20:00:00Z', lag_sessions: 1,
    status: 'fallback', fallback_reason: 'Required symbols did not all cover 2026-10-13.'});
  d.asof = '2026-10-12';
  return d;
}

// Independent of the visitor's timezone, machine weekday, and any calendar-day heuristic.
test('valid completed snapshot is current with separate market and generation dates', () => {
  const f = freshness.evaluate(snapshot(), at(cutoff));
  assert.equal(f.state, 'current'); assert.equal(f.isCurrent, true);
  assert.equal(f.actualSession, '2026-10-13'); assert.equal(f.expectedSession, '2026-10-13');
  assert.equal(f.generatedUTC, cutoff);
  assert.equal(freshness.formatUtc(cutoff), '2026-10-14 11:30:00 UTC');
});

test('a one-session fallback is a warning, even when generated just now', () => {
  const f = freshness.evaluate(fallback(), at(cutoff));
  assert.equal(f.state, 'fallback'); assert.equal(f.isCurrent, false);
  assert.match(f.label, /1 SESSION BEHIND/); assert.match(f.detail, /2026-10-12/); assert.match(f.detail, /2026-10-13/);
});

test('legacy snapshots never become current because of recent timestamps', () => {
  const legacy = snapshot(); delete legacy.session;
  const f = freshness.evaluate(legacy, at(cutoff));
  assert.equal(f.state, 'unverified'); assert.equal(f.isCurrent, false);
  assert.equal(f.actualLabel, '2026-10-13'); assert.equal(f.expectedLabel, 'Unverified');
  assert.equal(f.generatedUTC, cutoff);
});

test('current becomes overdue at the exact next close without JSON changing', () => {
  const d = snapshot();
  assert.equal(freshness.evaluate(d, at('2026-10-14T19:59:59.999Z')).state, 'current');
  const f = freshness.evaluate(d, at('2026-10-14T20:00:00Z'));
  assert.equal(f.state, 'expired'); assert.equal(f.isCurrent, false);
  assert.equal(f.expectedLabel, 'At least 2026-10-14 · refresh required');
  assert.match(f.detail, /Later completed sessions cannot be determined/);
  assert.equal(freshness.evaluate(d, at('2027-02-02T20:00:00Z')).state, 'expired');
});

test('a fallback also ages when its next recorded session closes', () => {
  assert.equal(freshness.evaluate(fallback(), at('2026-10-14T20:00:00Z')).state, 'expired');
});

test('server calendar preserves a holiday weekend and expires at a post-holiday early close', () => {
  const d = snapshot({cutoff_utc: '2026-11-26T15:00:00Z', actual_session: '2026-11-25',
    actual_close_utc: '2026-11-25T21:00:00Z', expected_latest_completed_session: '2026-11-25',
    expected_latest_completed_close_utc: '2026-11-25T21:00:00Z', next_session: '2026-11-27',
    next_session_close_utc: '2026-11-27T18:00:00Z'});
  d.asof = '2026-11-25'; d.generated_utc = '2026-11-26T15:00:00Z';
  assert.equal(freshness.evaluate(d, at('2026-11-26T22:00:00Z')).state, 'current');
  assert.equal(freshness.evaluate(d, at('2026-11-27T17:59:59Z')).state, 'current');
  assert.equal(freshness.evaluate(d, at('2026-11-27T18:00:00Z')).state, 'expired');
});

test('server next-session time keeps Friday snapshot current through a three-day weekend', () => {
  const d = snapshot({cutoff_utc: '2026-05-23T01:00:00Z', actual_session: '2026-05-22', actual_close_utc: '2026-05-22T20:00:00Z',
    expected_latest_completed_session: '2026-05-22', expected_latest_completed_close_utc: '2026-05-22T20:00:00Z',
    next_session: '2026-05-26', next_session_close_utc: '2026-05-26T20:00:00Z'});
  d.asof = '2026-05-22'; d.generated_utc = '2026-05-23T01:00:00Z';
  assert.equal(freshness.evaluate(d, at('2026-05-25T23:00:00Z')).state, 'current');
  assert.equal(freshness.evaluate(d, at('2026-05-26T20:00:00Z')).state, 'expired');
});

for (const [name, change] of [
  ['missing next close', d => delete d.session.next_session_close_utc],
  ['missing actual close evidence', d => delete d.session.actual_close_utc],
  ['unknown calendar', d => d.session.calendar = 'weekday-guess'],
  ['unknown timezone', d => d.session.timezone = 'UTC'],
  ['inconsistent actual session', d => d.session.actual_session = '2026-10-12'],
  ['inconsistent status', d => d.session.status = 'fallback'],
  ['nonzero current lag', d => d.session.lag_sessions = 1],
  ['string lag', d => d.session.lag_sessions = '0'],
  ['impossible expected date', d => d.session.expected_latest_completed_session = '2026-02-30'],
  ['next session precedes expected', d => d.session.next_session = '2026-10-12'],
  ['next close already before cutoff', d => d.session.next_session_close_utc = '2026-10-14T10:00:00Z'],
  ['actual close date mismatch', d => d.session.actual_close_utc = '2026-10-12T20:00:00Z'],
  ['naive timestamp', d => d.session.next_session_close_utc = '2026-10-14T20:00:00'],
  ['invalid timestamp', d => d.generated_utc = 'not a date'],
  ['invalid hour', d => d.generated_utc = '2026-10-13T24:00:00Z'],
  ['future publication', d => d.generated_utc = '2026-10-14T12:00:00Z'],
  ['publication before cutoff', d => d.generated_utc = '2026-10-14T11:00:00Z'],
  ['publication crosses next close', d => d.generated_utc = '2026-10-14T20:00:00Z'],
  ['missing generated timestamp', d => delete d.generated_utc],
  ['malformed actual date', d => d.asof = '2026-10-13T00:00:00Z'],
]) {
  test('fail closed: ' + name, () => {
    const d = snapshot(); change(d);
    const f = freshness.evaluate(d, at(cutoff));
    assert.equal(f.state, 'unverified'); assert.equal(f.isCurrent, false);
  });
}

test('missing inputs and invalid visitor clock fail closed', () => {
  for (const d of [null, undefined, {}, [], 'bad']) assert.equal(freshness.evaluate(d, at(cutoff)).state, 'unverified');
  assert.equal(freshness.evaluate(snapshot(), NaN).state, 'unverified');
  assert.equal(freshness.evaluate(snapshot(), at('2026-10-13T19:00:00Z')).state, 'unverified');
  assert.equal(freshness.formatUtc('2026-02-30T12:00:00Z'), 'Unavailable');
});

test('fallback without a reason or with contradictory lag is unverified', () => {
  for (const field of [{fallback_reason: null}, {fallback_reason: ''}, {lag_sessions: 0}]) {
    const d = fallback(); Object.assign(d.session, field);
    assert.equal(freshness.evaluate(d, at(cutoff)).state, 'unverified');
  }
});

const html = fs.readFileSync(path.join(__dirname, '../docs/index.html'), 'utf8');
function dashboard(helperAvailable = true) {
  const nodes = new Map();
  const makeNode = () => ({textContent: '', dataset: {}, children: [], style: {},
    replaceChildren() { this.children = []; }, append(...items) { this.children.push(...items); }, setAttribute() {}});
  for (const [, id] of html.matchAll(/id="([^"]+)"/g)) nodes.set(id, makeNode());
  const events = new Map(); const timeouts = [];
  let now = at(cutoff);
  class Clock extends Date { static now() { return now; } }
  const context = {
    Date: Clock, document: {getElementById: id => nodes.get(id), querySelectorAll: () => [],
      createElement: makeNode, createElementNS: makeNode, addEventListener: (event, fn) => events.set('document:' + event, fn)},
    setTimeout: (fn, ms) => { timeouts.push({fn, ms}); return timeouts.length; }, clearTimeout() {},
    setInterval: (fn, ms) => { events.set('interval', fn); assert.equal(ms, 30000); },
    fetch: () => new Promise(() => {}),
    addEventListener: (event, fn) => events.set('window:' + event, fn)
  };
  context.window = context;
  if (helperAvailable) context.SnapshotFreshness = freshness;
  vm.createContext(context);
  const inline = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  vm.runInContext(inline.slice(0, inline.indexOf("const storageKey=")), context);
  return {nodes, events, timeouts, render: d => context.render(d), setNow: value => {now = at(value);}};
}

test('dashboard renders dates accessibly and withholds all current assessments for fallback/legacy', () => {
  assert.match(html, /id="marketfreshness"[^>]*role="status"[^>]*aria-live="polite"/);
  assert.match(html, /<script src="\.\/freshness.js"><\/script>/);
  const ui = dashboard(); ui.render(snapshot());
  assert.equal(ui.nodes.get('marketfreshness').dataset.state, 'current');
  assert.equal(ui.nodes.get('marketdate').textContent, '2026-10-13');
  assert.equal(ui.nodes.get('generatedtime').textContent, '2026-10-14 11:30:00 UTC');
  assert.equal(ui.nodes.get('score').textContent, '7 / 7');
  ui.render(fallback());
  assert.equal(ui.nodes.get('headerfreshness').dataset.state, 'fallback');
  assert.equal(ui.nodes.get('expectedsession').textContent, '2026-10-13');
  assert.equal(ui.nodes.get('score').textContent, '— / 7');
  assert.equal(ui.nodes.get('opportunity').textContent, 'NO CURRENT SIGNAL');
  assert.equal(ui.nodes.get('soxl').textContent, '$100.00');
  assert.match(ui.nodes.get('qualtech').textContent, /^Historical BULLISH/);
  const legacy = snapshot(); delete legacy.session; ui.render(legacy);
  assert.equal(ui.nodes.get('headerfreshness').dataset.state, 'unverified');
  assert.equal(ui.nodes.get('regime').textContent, 'UNVERIFIED');
});

test('open dashboard ages on timer, focus and visibility changes without refetching', () => {
  const ui = dashboard(); ui.render(snapshot());
  assert.ok(ui.timeouts.some(t => t.ms === at('2026-10-14T20:00:00Z') - at(cutoff)));
  ui.setNow('2026-10-14T20:00:00Z'); ui.events.get('interval')();
  assert.equal(ui.nodes.get('headerfreshness').dataset.state, 'expired');
  assert.equal(ui.nodes.get('regime').textContent, 'OVERDUE');
  assert.equal(ui.nodes.get('opportunity').textContent, 'NO CURRENT SIGNAL');
  assert.equal(ui.nodes.get('expectedsession').textContent, 'At least 2026-10-14 · refresh required');
  assert.equal(typeof ui.events.get('window:focus'), 'function');
  assert.equal(typeof ui.events.get('document:visibilitychange'), 'function');
});

test('helper load failure cannot produce a green badge or current signal', () => {
  const ui = dashboard(false); ui.render(snapshot());
  assert.equal(ui.nodes.get('headerfreshness').dataset.state, 'unverified');
  assert.equal(ui.nodes.get('regime').textContent, 'UNVERIFIED');
  assert.equal(ui.nodes.get('score').textContent, '— / 7');
});
