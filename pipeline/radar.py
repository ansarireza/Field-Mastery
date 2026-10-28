"""Step 3: regulations, policy, funding, conferences. Headline-level only (and says so)."""
from __future__ import annotations

import datetime as dt
import email.utils
import urllib.parse
import xml.etree.ElementTree as ET

from . import mock_data
from .common import (DATA, STATE, clip, http_text, llm_json, log, log_week, read_json, short_hash,
                     strip_html, utc_today, write_json, MOCK)

ATOM = "{http://www.w3.org/2005/Atom}"


def _txt(el, tag):
    c = el.find(tag)
    return (c.text or "").strip() if c is not None and c.text else ""


def _date(s: str) -> str:
    if not s:
        return utc_today().isoformat()
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        return s[:10]


def parse_feed(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for it in root.iter("item"):
        src = it.find("source")
        out.append({"title": _txt(it, "title"), "link": _txt(it, "link"), "date": _date(_txt(it, "pubDate")),
                    "source": (src.text or "").strip() if src is not None and src.text else "",
                    "desc": clip(strip_html(_txt(it, "description")), 240)})
    for e in root.iter(ATOM + "entry"):
        link = e.find(ATOM + "link")
        out.append({"title": _txt(e, ATOM + "title"), "link": link.get("href", "") if link is not None else "",
                    "date": (_txt(e, ATOM + "updated") or _txt(e, ATOM + "published"))[:10],
                    "source": "", "desc": clip(strip_html(_txt(e, ATOM + "summary")), 240)})
    return [x for x in out if x["title"] and x["link"]]


def gnews(q: str) -> str:
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:7d')}&hl=en&gl=US&ceid=US:en"


def gather(prof: dict, cfg: dict) -> list[dict]:
    if MOCK:
        return [dict(x) for x in mock_data.RSS]
    urls = [gnews(q) for q in (prof.get("policy_queries", [])[:6] + prof.get("event_queries", [])[:3])]
    urls += cfg["radar"].get("feeds", [])
    cutoff = (utc_today() - dt.timedelta(days=int(cfg["radar"].get("days_back", 7)))).isoformat()
    items = []
    for u in urls:
        try:
            items += parse_feed(http_text(u))
        except Exception as e:
            log(f"radar: feed skipped ({u[:60]}...): {e}")
    return [i for i in items if i["date"] >= cutoff]


def run(cfg: dict, prof: dict) -> dict:
    today = utc_today()
    seen = set(read_json(STATE / "seen_radar.json", []))
    uniq, keys = [], set()
    for i in gather(prof, cfg):
        k = short_hash(i["title"].lower()[:80])
        if k in seen or k in keys:
            continue
        keys.add(k)
        i["key"] = k
        uniq.append(i)
    uniq = uniq[:40]
    items = []
    if uniq:
        listing = "\n".join(f"{n}. [{i['date']}] {i['title']} ({i['source']})" for n, i in enumerate(uniq))
        mx = int(cfg["radar"].get("max_items", 12))
        r = llm_json(f"""A PhD student works on: "{prof.get('field_summary')}".
Below are news headlines. Pick at most {mx} that genuinely matter for staying current in this field:
regulation or law changes, policy reports and treaty decisions, funding calls, conferences / calls for papers, or major science news.
Skip duplicates, opinion fluff and unrelated items. Use ONLY the headline text; do not add facts that are not in it.

{listing}

Return JSON {{"items": [{{"i": index, "category": "regulation|policy|funding|event|news",
"title": max 80 chars, "one_liner": max 130 chars restating what happened,
"why": max 120 chars on why it matters for this field (hedge if unsure), "urgency": 1-3 (3 = act soon)}}]}}""",
                     mock={"items": [
                         {"i": 0, "category": "regulation", "title": "[SAMPLE] EU delays deforestation rules", "one_liner": "Sample: rules postponed again.", "why": "Sample: affects supply-chain research.", "urgency": 2},
                         {"i": 1, "category": "event", "title": "[SAMPLE] Conference 2027 call for abstracts", "one_liner": "Sample call for abstracts.", "why": "Possible venue for your results.", "urgency": 3},
                     ]})
        for it in r.get("items", [])[:mx]:
            try:
                src = uniq[int(it["i"])]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            items.append({
                "id": src["key"], "category": it.get("category", "news"), "title": clip(it.get("title", src["title"]), 90),
                "one_liner": clip(it.get("one_liner", ""), 140), "why": clip(it.get("why", ""), 130),
                "urgency": int(it.get("urgency", 1) or 1), "date": src["date"], "url": src["link"],
                "source": src["source"], "basis": "headline",
            })
        items.sort(key=lambda x: (x["urgency"], x["date"]), reverse=True)
        seen.update(k for k in keys)
        write_json(STATE / "seen_radar.json", sorted(seen)[-4000:])

    if not items:  # nothing new today: keep showing last week's items instead of an empty screen
        prev = read_json(DATA / "radar.json", {})
        if prev.get("date") and (today - dt.date.fromisoformat(prev["date"])).days <= int(cfg["radar"].get("days_back", 7)):
            items = prev.get("items", [])

    events = []
    for e in cfg["radar"].get("events") or []:
        for field, label in (("deadline", "Deadline"), ("date", "Event")):
            d = e.get(field)
            if not d:
                continue
            d = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))
            left = (d - today).days
            if left >= 0:
                events.append({"name": e.get("name", ""), "kind": label, "date": d.isoformat(), "days_left": left,
                               "url": e.get("url", ""), "note": e.get("note", "")})
    events.sort(key=lambda x: x["days_left"])
    log_week(today, "radar", [i["title"] for i in items[:5]])
    return {"date": today.isoformat(), "items": items, "events": events}
