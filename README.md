# Semiconductor & SOXL Signal Tracker

Install dependencies with `pip install -r requirements.txt`, then run
`streamlit run App.py`. For the separate static investment terminal, see
[TERMINAL_README.md](TERMINAL_README.md).

The current app and terminal retain main's price-only 0–7 sector score, SOXL
tactical assessment, and historical strategy comparisons. Simulated macro votes,
fixed sales growth, and unverified legacy DRAM/NAND/book-to-bill data are excluded
from the actionable score. The older draft PR's 60/40 technical/macro model has
been superseded; it is not restored by this change. Neither current entry point
requires a FRED key.

## Price-data safeguards

Both download paths use the NYSE regular-session calendar (the common US equity
session schedule for these instruments), including exchange holidays, early
closes and New York daylight saving time. Each download run captures one UTC
cutoff before fetching anything. A daily bar is eligible only after that
session's scheduled close; an in-progress daily bar is excluded even if Yahoo
already supplies a numeric close. This establishes session completion, not a
vendor guarantee that an adjusted price will never be revised.

The expected market date is the latest completed session, separate from the
actual observed date and the generation timestamp. A missing latest close can
produce a **clearly labeled fallback of at most one completed session**. Larger
lags, future/non-session dates, duplicate dates, invalid historical closes,
infinite or non-positive prices fail closed. No missing prices are forward
filled. SOXX/SOXL/SPY use their actual overlapping observations; lagging auxiliary
watchlist rows are omitted. Streamlit rechecks session freshness on cached reruns.

The publisher records each symbol's latest source date, usable completed date,
missing completed dates and excluded in-progress dates. Snapshot session metadata
records the UTC cutoff, actual and expected sessions, lag, close times and next
session close. It logs these diagnostics before rejecting a regressing snapshot.
A previously published newer snapshot blocks regression only if its completed-
session metadata is consistent with the calendar and its nonfuture capture
occurred after that session's close. Legacy snapshots have no reliable fetch
cutoff and remain unverified, even if generated after the close; they cannot pin
an invalid market date forever. No existing snapshot is silently certified or
restored as a finalized close.

The static site displays actual market date, expected completed session and
capture time separately. Legacy/malformed metadata is unverified, one-session
fallbacks are warned immediately, and the badge becomes refresh-overdue when the
next scheduled exchange close passes, even if the JSON does not refresh. It does
not guess later exchange sessions from weekdays or treat a recent generation
stamp as fresh market data. Failed publisher runs leave the previous file intact.

Calendar schedules depend on the maintained calendar package and cannot predict
unannounced exchange closures. These checks do not establish corporate-action
correctness or predictive value. Historical session gaps remain omitted rather
than imputed, so indicator windows refer to available overlapping observations.

## Offline tests

Run `pip install -r requirements.txt pytest`, `python -m pytest -q`, and
`node --test tests/test_freshness.js`. Tests cover price validation,
the current Streamlit app (including outage and warm-cache reruns), and the
terminal publisher using synthetic downloads and temporary output files. They
do not call live Yahoo/FRED services, refresh committed snapshots, or deploy.
CI runs the same tests on pull requests and the fix branch. No trading-performance
claim is made.
