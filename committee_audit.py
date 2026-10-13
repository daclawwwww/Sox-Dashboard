"""Deterministic coverage audit for investment committee evidence."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
CHECKS={
 "AI capex":"Quarter-over-quarter and year-over-year hyperscaler capex guidance, actual spending, and company filings.",
 "Semiconductor cycle":"Dated DRAM and NAND quotes, industry inventories, lead times, and chip-sales trend.",
 "Earnings revisions":"As-of-date consensus EPS estimates, guidance updates, and gross-margin revisions.",
 "Competition":"Documented customer shifts, custom ASIC deployments, export restrictions, and market share.",
 "Macro geopolitics":"Rates, export-control changes, Taiwan supply-chain risk, and associated event dates."
}
def main():
    doc=json.loads((ROOT/"docs/intelligence.json").read_text())
    groups=[]
    for x in doc["groups"]:
        articles=x.get("articles",[])
        groups.append({"factor":x["factor"],"status":"HEADLINES ONLY" if articles else "NO CURRENT COVERAGE",
          "article_count":len(articles),"latest_source_date":max((a.get("published_utc","")[:10] for a in articles),default=None),
          "next_evidence":CHECKS.get(x["factor"],"Verify with primary reporting and contemporaneous data."),
          "interpretation":"Not assessed — headlines cannot independently establish a fundamental trend."})
    out={"generated_utc":datetime.now(timezone.utc).isoformat(),
         "source_generated_utc":doc.get("generated_utc"),
         "method":"Deterministic source-coverage audit (NOT AI analysis)",
         "groups":groups}
    (ROOT/"docs/committee.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Coverage audit:", [(x["factor"],x["status"]) for x in groups])
if __name__=="__main__":
    main()
