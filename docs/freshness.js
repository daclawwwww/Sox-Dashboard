/* Exchange-session freshness for a static dashboard. No local trading-calendar guesses. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SnapshotFreshness = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const FUTURE_CLOCK_TOLERANCE_MS = 5 * 60 * 1000;

  function sessionDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const time = Date.parse(value + 'T00:00:00Z');
    return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? value : null;
  }

  function utcTime(value) {
    // A timezone is mandatory: never interpret a producer timestamp in the viewer's timezone.
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|\+00:00)$/.test(value)) return null;
    if (!sessionDate(value.slice(0, 10))) return null;
    const time = Date.parse(value);
    return Number.isFinite(time) ? time : null;
  }

  function formatUtc(value) {
    const time = utcTime(value);
    return time === null ? 'Unavailable' : new Date(time).toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
  }

  function evaluate(snapshot, now = Date.now()) {
    const d = snapshot && typeof snapshot === 'object' ? snapshot : {};
    const actual = sessionDate(d.asof);
    const generated = utcTime(d.generated_utc);
    const base = {
      state: 'unverified', isCurrent: false, label: 'SESSION UNVERIFIED',
      title: 'Market session status is unverified',
      detail: 'Completed-session evidence is missing or invalid. A recent generation time does not establish that prices are final or current. Current signals are withheld.',
      actualSession: actual, actualLabel: actual || 'Unavailable',
      expectedSession: null, expectedLabel: 'Unverified',
      generatedUTC: generated === null ? null : d.generated_utc,
      cutoffUTC: null, nextCloseUTC: null, nextSession: null, lagSessions: null
    };
    const s = d.session;
    if (!actual || !s || typeof s !== 'object' || !Number.isFinite(now) || generated === null) return base;
    const expected = sessionDate(s.expected_latest_completed_session);
    const next = sessionDate(s.next_session);
    const cutoff = utcTime(s.cutoff_utc);
    const actualClose = utcTime(s.actual_close_utc);
    const expectedClose = utcTime(s.expected_latest_completed_close_utc);
    const nextClose = utcTime(s.next_session_close_utc);
    const lag = s.lag_sessions;
    if (s.calendar !== 'NYSE' || s.timezone !== 'America/New_York' ||
        s.actual_session !== actual || !expected || !next ||
        [cutoff, actualClose, expectedClose, nextClose].some(x => x === null) ||
        !Number.isSafeInteger(lag) || lag < 0 ||
        actual > expected || expected >= next ||
        actualClose > expectedClose || expectedClose > cutoff || cutoff >= nextClose ||
        generated < cutoff || generated >= nextClose || generated > now + FUTURE_CLOCK_TOLERANCE_MS ||
        actualClose > now || expectedClose > now ||
        s.actual_close_utc.slice(0, 10) !== actual ||
        s.expected_latest_completed_close_utc.slice(0, 10) !== expected ||
        s.next_session_close_utc.slice(0, 10) !== next) return base;
    const isCurrent = actual === expected && actualClose === expectedClose && lag === 0 &&
      s.status === 'current' && s.fallback_reason === null;
    const isFallback = actual < expected && actualClose < expectedClose && lag > 0 &&
      s.status === 'fallback' && typeof s.fallback_reason === 'string' && s.fallback_reason.trim().length > 0;
    if (!isCurrent && !isFallback) return base;
    const verified = {
      ...base, expectedSession: expected, expectedLabel: expected,
      cutoffUTC: s.cutoff_utc, nextCloseUTC: s.next_session_close_utc,
      nextSession: next, lagSessions: lag
    };
    if (now >= nextClose) {
      return {
        ...verified, state: 'expired', label: 'REFRESH OVERDUE',
        title: 'Refresh overdue: current session status is unverified',
        expectedLabel: 'At least ' + next + ' · refresh required',
        detail: 'The next exchange session (' + next + ') has closed since this snapshot was generated. Market data still ends on ' + actual + '. Later completed sessions cannot be determined from this old snapshot. Current signals are withheld until new session evidence is published.'
      };
    }
    if (isFallback) {
      return {
        ...verified, state: 'fallback', label: 'FALLBACK · ' + lag + ' SESSION' + (lag === 1 ? '' : 'S') + ' BEHIND',
        title: 'Historical fallback: market data is behind the latest completed session',
        detail: 'Prices are from ' + actual + ', but the latest completed NYSE session is ' + expected + ' (' + lag + ' session' + (lag === 1 ? '' : 's') + ' behind). ' + s.fallback_reason.trim() + ' Current signals are withheld.'
      };
    }
    return {
      ...verified, state: 'current', isCurrent: true, label: 'CURRENT EOD SNAPSHOT',
      title: 'Latest completed exchange session covered',
      detail: 'Market data covers ' + actual + ', the latest completed NYSE session at the recorded cutoff. These are adjusted daily closes, not live or premarket quotes. Generation time is separate from the market date.'
    };
  }

  return Object.freeze({evaluate, formatUtc});
}));
