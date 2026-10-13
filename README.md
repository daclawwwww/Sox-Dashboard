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

Both download paths reject empty, undated, duplicate-dated, missing, non-finite,
non-positive, future-dated, and more-than-five-calendar-day-old closes. SOXX,
SOXL, and SPY must share their latest observation date. Historical alignment
uses observed overlapping bars only, with no forward filling. Streamlit checks
freshness again on each rerun, including cached results. The terminal omits
lagging auxiliary watchlist rows rather than labeling them with a newer as-of
date. A rejected download leaves the previously published snapshot unchanged;
the static site's existing stale-data warning still applies to that snapshot.

Validation is deliberately fail-closed: even an invalid historical close blocks
that download. Missing historical sessions are omitted, so session-count windows
refer to the available overlapping sample, not a separately verified exchange
calendar. Feed outages and exchange/vendor date conventions still need real-feed
validation. These checks do not validate corporate actions or predictive value.

## Offline tests

Run `pip install pytest` and `python -m pytest -q`. Tests cover price validation,
the current Streamlit app (including outage and warm-cache reruns), and the
terminal publisher using synthetic downloads and temporary output files. They
do not call live Yahoo/FRED services, refresh committed snapshots, or deploy.
CI runs the same tests on pull requests and the fix branch. No trading-performance
claim is made.
