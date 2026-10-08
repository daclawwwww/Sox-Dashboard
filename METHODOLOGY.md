## Live scoring

This is a transparent directional heuristic, not a calibrated forecast or a backtested investment strategy. Data-quality safeguards do not establish predictive accuracy.

Technical indicators have a fixed 60% group weight; observed macro has 40%. The live score is `0.60 × mean(technical votes) + 0.40 × mean(eligible macro votes)`, in [-1, +1]. These are explicit design weights, not optimized estimates. Each eligible component within its group has equal weight. With all inputs available, each technical vote weighs 15%, each macro vote 13.33%; with two available macro votes each weighs 20%. Weight never moves between groups. Coverage is always displayed.

Require **all four technical votes and at least two of the three macro votes**. Otherwise display **INSUFFICIENT DATA**, with no numeric aggregate. A valid neutral vote is zero; unavailable, invalid, stale or unverified observations have no vote. BUY requires score >= +0.25; SELL requires <= -0.25; HOLD is between. These symmetric thresholds replace the old rule that called zero SELL. They require validation before reliance and are not comparable to the old raw total.

| Input | +1 | -1 | Maximum age |
|---|---|---|---|
| RSI (14) | >55 | <45 | 5 calendar days |
| MACD histogram (12/26/9) | >0.2 | <-0.2 | 5 days |
| ROC (63 sessions) | >5% | <-2% | 5 days |
| SOXX/SPY relative-strength mean change over latest five aligned closes | >0.001 | <-0.001 | 5 days |
| FRED A34SNO | >25,000 | <24,000 | 100 days |
| FRED NEWORDER | Above prior month | Below prior month | 100 days |
| SIA/WSTS global semiconductor sales YoY | >0% | <0% | 100 days |

Values between the stated thresholds receive zero. Original technical formulas and thresholds are retained, using full precision rather than rounded display values. Price downloads explicitly use adjusted prices and handle yfinance MultiIndex columns. At least 64 positive SOXX closes are required. Relative strength requires five aligned closes and matching latest dates. Missing, non-finite, duplicate-date, future-dated, and stale observations are rejected. A malformed latest value is not silently replaced with an older value. No fallback to stale cached data is eligible.

Age uses UTC calendar dates. Five days allows ordinary weekends/holidays but is not an exchange-calendar guarantee. Monthly FRED dates mark the beginning of the reference month; 100 days accommodates publication lag. NEWORDER also requires consecutive valid months. These conservative configurable code constants are operational limits, not learned model parameters. Cached raw downloads are revalidated every rerun. Set the `FRED_API_KEY` environment variable to enable FRED; failures appear as unavailable.

A34SNO measures computer/electronic-product new orders in millions of dollars; it is neither ISM PMI nor semiconductor orders. FRED specifically notes semiconductor new orders are unavailable. The retained dollar thresholds are legacy heuristics and are not inflation-adjusted. NEWORDER covers nondefense capital goods excluding aircraft. SIA monthly sales are three-month moving averages. These series are correlated proxies; the dashboard does not claim independent evidence or confidence probabilities.

## Semiconductor data and update policy

- `data/semiconductor_sales.csv` holds manual, sourced observations with reference month-end, YoY percent, publication date and primary-source URL. The August 2026 observation was published October 5, 2026 and verified October 7. It expires automatically after 100 days from the reference date. There is no automatic SIA refresh. Append verified actual releases, never forecasts; preserve publication dates and units. A future publication date cannot score.
- The original DRAM and NAND files end April 14, 2025 and do not specify product, units or provenance. They remain visible for audit but are **never included in the live model**, even if dates are edited. Legacy absolute-price/trend functions now reject stale observations; usable future memory scoring requires verified consistent product history and separately reviewed thresholds.
- `data/memory_spot_context.csv` records primary-source session-average quotes for explicitly identified chips, verified October 7, 2026. These are context only, each with its own date and 14-day stale flag. They do not establish continuity with the old CSVs or justify the old price thresholds. No automated/licensed historical feed is configured.
- SEMI says its North America book-to-bill report ended in 2017, with December 2016 the final bookings publication. The repository's 2025 ratio observations have no verifiable provenance and are excluded. Equipment billings are a different measure and must not be substituted for book-to-bill.
- The five mock macro votes are displayed only in the hypothetical sandbox. They cannot affect score, coverage, weights or recommendation.

## Primary sources audited October 7, 2026

- [SIA August 2026 sales release](https://www.semiconductors.org/year-to-date-global-semiconductor-sales-top-1-trillion-through-august/)
- [DRAMeXchange product-specific spot prices](https://www.dramexchange.com/)
- [SEMI report discontinuation notice](https://www.semi.org/zh/products-services/market-data/equipment/billings-report)
- [FRED A34SNO definition](https://fred.stlouisfed.org/series/A34SNO)
- [FRED NEWORDER definition](https://fred.stlouisfed.org/series/NEWORDER)

This dashboard evaluates current available observations only. It does not reconstruct historical data vintages or support a point-in-time backtest. Revisions, overlapping indicators, memory-product changes and uncalibrated thresholds remain model risks.
