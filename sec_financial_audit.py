"""Read-only SEC companyfacts cross-check for manually captured company results.

No overwrite of research source data. Require exact fiscal period end and direct
quarter durations; otherwise flag unresolved instead of making up quarterlies.
"""
import json, os, urllib.request
from datetime import datetime, timezone, date
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CIKS={"MU":"0000723125","AVGO":"0001730168"}
TAGS={"revenue":["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"],
      "operating_income":["OperatingIncomeLoss"]}
HEADERS={"User-Agent":os.environ.get("SEC_USER_AGENT","SEMI research admin contact via SEC_USER_AGENT environment variable"),
         "Accept":"application/json"}
def companyfacts(cik):
    req=urllib.request.Request("https://data.sec.gov/api/xbrl/companyfacts/CIK"+cik+".json",headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def direct_quarter(record,kind,period_end):
    facts=record.get("facts",{}).get("us-gaap",{})
    matched=[]
    for tag in TAGS[kind]:
        for v in facts.get(tag,{}).get("units",{}).get("USD",[]):
            if v.get("end")!=period_end or v.get("form") not in ("10-Q","10-K"):continue
            if not v.get("start") or not v.get("filed"):continue
            days=(date.fromisoformat(v["end"])-date.fromisoformat(v["start"])).days
            if not 70<=days<=110:continue
            matched.append((v["filed"],v.get("accn",""),v["val"]/1e6,tag))
    if not matched:return None
    matched.sort(reverse=True)
    filed,accession,amount,tag=matched[0]
    return {"value_usd_millions":round(amount,3),"filed":filed,"accession":accession,"tag":tag}
def main():
    if not os.environ.get("SEC_USER_AGENT"):
        raise RuntimeError("Set SEC_USER_AGENT with a real contact address before SEC requests")
    source=json.loads((ROOT/"docs/company-fundamentals.json").read_text())
    rows=[]
    for company in source["companies"]:
        ticker=company["ticker"]
        if ticker not in CIKS:continue
        try:record=companyfacts(CIKS[ticker])
        except Exception as exc:
            rows.append({"ticker":ticker,"status":"SOURCE_UNAVAILABLE","message":str(exc)[:220]})
            continue
        fiscal_year_end={"MU":"08-31","AVGO":"11-01"}
        results=[]
        for row in company.get("quarterly_history",[]):
            # Exact period-end dates required: fiscal labels alone aren't reliable SEC locators.
            end=row.get("period_end")
            if not end:
                results.append({"period":row["period"],"status":"PERIOD_END_REQUIRED",
                    "reason":"Provide verified fiscal quarter end before matching SEC XBRL observations"})
                continue
            rev=direct_quarter(record,"revenue",end)
            oi=direct_quarter(record,"operating_income",end)
            if not rev or not oi:
                results.append({"period":row["period"],"status":"UNRESOLVED",
                                "reason":"Missing exact direct-quarter revenue or operating income SEC fact","period_end":end})
                continue
            revenue_ok=abs(rev["value_usd_millions"]-row["revenue"])<=1
            oi_ok=abs(oi["value_usd_millions"]-row["operating_income"])<=1
            results.append({"period":row["period"],"period_end":end,
                "status":"MATCH" if revenue_ok and oi_ok else "MISMATCH",
                "reported_revenue":row["revenue"],"sec_revenue":rev,
                "reported_operating_income":row["operating_income"],"sec_operating_income":oi})
        rows.append({"ticker":ticker,"status":"CHECKED","quarters":results})
    out={"generated_utc":datetime.now(timezone.utc).isoformat(),"source":"SEC companyfacts (read-only)",
         "method":"Period-end and direct quarterly fact matching, 1 USD million tolerance; no silent overwrites.",
         "results":rows}
    (ROOT/"docs/financial-audit.json").write_text(json.dumps(out,indent=2)+"\n")
    print([(x["ticker"],x["status"]) for x in rows])
if __name__=="__main__":main()
