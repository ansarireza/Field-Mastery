"""Step 7: one open debate per week, argued from real highly-cited papers only."""
from __future__ import annotations

from . import mock_data
from .common import STATE, clip, iso_week, llm_json, read_json, utc_today, write_json, MOCK
from .papers import abstract_from_inverted, oa_get

PATH = STATE / "debates.json"


def run(cfg: dict, prof: dict) -> dict:
    week = iso_week(utc_today())
    state = read_json(PATH, {"week": None, "index": -1, "current": None})
    if state.get("week") == week and state.get("current"):
        return state
    debates = prof.get("debates", [])
    if not debates:
        return state
    idx = (state.get("index", -1) + 1) % len(debates)
    d = debates[idx]
    if MOCK:
        works = [{"title": "[SAMPLE] Paper A", "year": "2012", "url": "https://example.org/a", "abstract": "Sample abstract A."},
                 {"title": "[SAMPLE] Paper B", "year": "2018", "url": "https://example.org/b", "abstract": "Sample abstract B."}]
    else:
        res = oa_get("/works", {"search": d["query"], "sort": "cited_by_count:desc", "per_page": 8,
                                "filter": "has_abstract:true,type:article|review",
                                "select": "id,title,publication_date,doi,abstract_inverted_index"}).get("results", [])
        works = [{"title": w.get("title"), "year": (w.get("publication_date") or "")[:4], "url": w.get("doi") or w.get("id"),
                  "abstract": abstract_from_inverted(w.get("abstract_inverted_index"))[:900]} for w in res]
    if not works:
        state.update({"week": week, "index": idx})
        return state
    ctx = "\n".join(f"[{i}] ({w['year']}) {w['title']}: {w['abstract']}" for i, w in enumerate(works))
    r = llm_json(f"""Prepare a balanced debate briefing for a PhD student in "{prof.get('field_summary')}".
Debate: {d['title']}
Use ONLY the papers below as evidence and cite them by number [i]; do not invent references. If the papers do not cover a side, say so.

{ctx}

Return JSON: {{"question": the debate as a neutral question (max 100 chars),
"side_a": {{"claim": max 90 chars, "argument": max 260 chars, "cites": [numbers]}},
"side_b": {{"claim": max 90 chars, "argument": max 260 chars, "cites": [numbers]}},
"middle": max 200 chars (common ground or how the debate is evolving),
"committee": max 160 chars (what a committee might ask you about this)}}""",
                 mock={"question": "[SAMPLE] Should nature be given a monetary value?", "side_a": {"claim": "[SAMPLE] Yes", "argument": "[SAMPLE] Prices make nature visible in decisions.", "cites": [0]},
                       "side_b": {"claim": "[SAMPLE] No", "argument": "[SAMPLE] Values are plural and not all can be priced.", "cites": [1]},
                       "middle": "[SAMPLE] Many use mixed approaches.", "committee": "[SAMPLE] Where do you stand and why?"})

    def side(s):
        return {"claim": clip(s.get("claim", ""), 100), "argument": clip(s.get("argument", ""), 280),
                "cites": [c for c in s.get("cites", []) if isinstance(c, int) and 0 <= c < len(works)]}

    cur = {"title": d["title"], "question": clip(r.get("question", d["title"]), 110), "side_a": side(r.get("side_a", {})),
           "side_b": side(r.get("side_b", {})), "middle": clip(r.get("middle", ""), 220),
           "committee": clip(r.get("committee", ""), 180),
           "sources": [{"n": i, "title": clip(w["title"], 110), "year": w["year"], "url": w["url"]} for i, w in enumerate(works)]}
    state = {"week": week, "index": idx, "current": cur}
    write_json(PATH, state)
    return state
