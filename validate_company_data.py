"""Fail-closed arithmetic and provenance checks for manually entered company research.

Does not fetch SEC filings or attest that transcribed numbers match them.
Missing company fields are permitted but must not be scored.
"""
import json
from datetime import date
from pathlib import Path

FILE = Path(__file__).parent / "docs" / "company-fundamentals.json"
def near(actual, expected, tolerance=0.16):
    return abs(float(actual)-float(expected)) <= tolerance
def check(data):
    errors=[]
    for company in data.get("companies",[]):
        ticker=company.get("ticker","?")
        def bad(msg):errors.append(f"{ticker}: {msg}")
        history=company.get("quarterly_history",[])
        if not history:
            if company.get("reported",{}).get("incremental_margin_pct") is not None:
                bad("reported margin with no quarterly provenance")
            continue
        if len(history)<2:bad("insufficient historical periods")
        source_dates={s.get("date") for s in company.get("sources",[]) if s.get("url","").startswith("https://")}
        if not source_dates:bad("historical financials lack dated HTTPS sources")
        previous=None
        for row in history:
            try:
                period=row["period"]; revenue=float(row["revenue"]);income=float(row["operating_income"])
                published=date.fromisoformat(row["publication_date"])
                if revenue<=0:bad(f"{period}: invalid revenue")
                if published > date.today():bad(f"{period}: publication in future")
                if row.get("accounting_basis")!="GAAP":bad(f"{period}: unknown accounting basis")
                if not near(row["operating_margin_pct"],100*income/revenue):bad(f"{period}: operating margin arithmetic mismatch")
                if previous is None:
                    if row.get("sequential_incremental_margin_pct") is not None:bad(f"{period}: first period should have null incremental margin")
                else:
                    delta_rev=revenue-float(previous["revenue"])
                    if abs(delta_rev)<1e-8:
                        if row.get("sequential_incremental_margin_pct") is not None:bad(f"{period}: zero change in revenue")
                    elif not near(row["sequential_incremental_margin_pct"],100*(income-float(previous["operating_income"]))/delta_rev):
                        bad(f"{period}: incremental margin mismatch")
                previous=row
            except (KeyError,ValueError,TypeError,ZeroDivisionError) as exc:bad(f"malformed historical row: {exc}")
        rep=company.get("reported",{})
        if rep.get("incremental_margin_pct") is not None:
            try:
                expected=100*(float(rep["current_operating_income"])-float(rep["prior_operating_income"]))/(float(rep["current_revenue"])-float(rep["prior_revenue"]))
                if not near(rep["incremental_margin_pct"],expected):bad("reported incremental margin arithmetic mismatch")
            except (KeyError,ValueError,TypeError,ZeroDivisionError):bad("reported increment cannot be calculated")
        guide=company.get("guidance",{})
        if guide.get("guide_midpoint_incremental_margin_pct") is not None:
            try:
                rev=(float(guide["guided_revenue_low"])+float(guide["guided_revenue_high"]))/2
                income=(float(guide["guided_operating_income_low"])+float(guide["guided_operating_income_high"]))/2
                val=100*(income-float(guide["baseline_operating_income"]))/(rev-float(guide["baseline_revenue"]))
                if not near(guide["guide_midpoint_incremental_margin_pct"],val):bad("guidance midpoint incremental margin arithmetic mismatch")
                if not guide.get("basis"):bad("missing guidance basis")
            except (KeyError,ValueError,TypeError,ZeroDivisionError):bad("guidance midpoint cannot be calculated")
    return errors

if __name__=="__main__":
    dataset=json.loads(FILE.read_text())
    problems=check(dataset)
    if problems:raise SystemExit("COMPANY DATA VALIDATION FAILED:\n"+"\n".join(problems))
    print("Company research arithmetic checks passed; source values still require independent filing verification.")
