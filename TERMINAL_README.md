# SEMI // Investment Terminal

A mobile-first investment research dashboard backed by daily adjusted prices.

## Launch the website (one-time setup)
1. Visit **Settings → Pages** for this repository.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch **main**, folder **/docs**, then **Save**.
4. Website will be at https://daclawwwww.github.io/Sox-Dashboard/ after Pages deploys.

## First market data refresh
Open **Actions → Refresh Terminal Market Data → Run workflow**.
The job downloads up to 10 years of adjusted Yahoo Finance prices with yfinance, computes indicators, strategy comparisons and exports docs/market.json.
The site separates market-data date from capture time. Completed-session checks
use the US equity exchange calendar; one-session fallback data is flagged
immediately, legacy metadata is unverified, and the browser marks a refresh
overdue at the next scheduled exchange close. See [README.md](README.md) for
validation, regression protection and source-date diagnostics.
The scheduled workflow runs Monday–Friday at 22:25 UTC and commits the new snapshot. Actions must have **Read and write permissions** for GITHUB_TOKEN (Settings → Actions → General) if the commit step is denied.

## Sections
- **Market Pulse:** Sector score, SOXL chart, related stocks.
- **Opportunity Radar:** Rule-based candidate screens and 63-session drawdowns.
- **Strategy Lab:** Buy & hold, momentum, dip + trend, and combined strategy diagnostics.
- **Trade Journal:** Browser-local entry log with CSV export. It does not sync between devices.

## Model and caveats
Signals originate from SOXX price action vs SPY, not from SOXL itself except a tactical moving-average check. Signal changes are applied with a one-session lag. An illustrative 10 bps cost is charged per unit turnover; cash earns zero. A chronological last-30% segment is displayed, but thresholds remain unvalidated and the holdout is not independently untouched. The historical comparison excludes taxes, intraday fills, bid-ask spread, leverage financing effects beyond those embedded in the fund prices, and slippage beyond the assumed cost.

Prices use Yahoo Finance adjusted daily closes. This is **not real-time or premarket pricing**. Independent validation of price bars, corporate actions, model logic and walk-forward results is necessary before relying on any signal for real trades.

## Existing research app
The original Streamlit `App.py` and Python `backtest.py` remain in the repository. The new terminal is independent and can be hosted on GitHub Pages.
