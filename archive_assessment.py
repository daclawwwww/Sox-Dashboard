"""Append the current published qualitative review into historical snapshots.
Does not modify strategy backtests or infer a qualitative trading score.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent/"docs"
def main():
    current=json.loads((ROOT/"qualitative.json").read_text())
    if current.get("status")!="published" or not current.get("asof") or not current.get("sources"):return
    path=ROOT/"assessment-history.json"
    d=json.loads(path.read_text()) if path.exists() else {"schema_version":1,"assessments":[]}
    items=d.get("assessments",[])
    # One dated snapshot, deduplicated by published timestamp.
    if any(x.get("published_utc")==current.get("published_utc") for x in items):return
    keys=("asof","published_utc","headline","overall","factors","risks","invalidation","sources")
    items.append({key:current.get(key) for key in keys})
    d["assessments"]=sorted(items,key=lambda x:x["published_utc"])
    path.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
    print("Saved new qualitative research snapshot:",current["asof"])
if __name__=="__main__":main()
