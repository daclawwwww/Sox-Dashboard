"""Public news headline feed. Does not fabricate summaries or scores.
RSS availability is best-effort; failure preserves the previous dated feed.
"""
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

QUERIES = {
 "AI capex": 'Microsoft Amazon Google Meta AI capex data center chips',
 "Semiconductor cycle": 'DRAM NAND prices memory semiconductor inventory',
 "Earnings revisions": 'Nvidia TSMC Micron Broadcom AMD earnings guidance estimates',
 "Competition": 'China semiconductor restrictions custom AI ASIC competition',
 "Macro geopolitics": 'semiconductor export controls Taiwan tariffs interest rates'
}
ROOT=Path(__file__).resolve().parent

def fetch(category, query):
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(query+" when:3d")+"&hl=en-US&gl=US&ceid=US:en"
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; SEMI-research-feed/1.0)"})
    with urllib.request.urlopen(request,timeout=12) as response:
        xml=response.read(500000)
    rss=ET.fromstring(xml)
    articles=[]
    for node in rss.findall(".//item")[:5]:
        title=(node.findtext("title") or "").strip()
        link=(node.findtext("link") or "").strip()
        stamp=(node.findtext("pubDate") or "").strip()
        origin=node.find("source")
        source=(origin.text or "").strip() if origin is not None else ""
        if not title or not link.startswith("https://"):
            continue
        try:
            date=parsedate_to_datetime(stamp).astimezone(timezone.utc).isoformat()
        except Exception:
            continue
        articles.append({"title":title,"url":link,"source":source,"published_utc":date})
    return articles

def main():
    groups=[]
    errors=[]
    for category,query in QUERIES.items():
        try:
            articles=fetch(category,query)
            if not articles: errors.append(category+": no returned articles")
            groups.append({"factor":category,"articles":articles})
        except Exception as exc:
            errors.append(category+": "+str(exc)[:200])
            groups.append({"factor":category,"articles":[]})
    if not any(g["articles"] for g in groups):
        raise RuntimeError("All RSS categories unavailable: refusing to overwrite prior feed")
    out=ROOT/"docs"/"intelligence.json"
    out.write_text(json.dumps({
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "coverage":"Recent public news headlines; not verified fundamental data or AI financial analysis",
        "groups":groups,"errors":errors
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Wrote",out,"articles",sum(len(x["articles"]) for x in groups),"errors",len(errors))

if __name__=="__main__":
    main()
