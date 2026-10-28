"""Step 6: 'Researcher of the week' - chosen from real citation data, described only from that data."""
from __future__ import annotations

from collections import Counter

from . import mock_data
from .common import STATE, clip, iso_week, llm_json, log, read_json, utc_today, write_json, MOCK
from .papers import oa_get

PATH = STATE / "people.json"


def top_authors(prof: dict) -> list[tuple[str, str]]:
    """Authors who most often appear on the most-cited papers for the field's core queries."""
    if MOCK:
        return list(mock_data.CANDIDATE_AUTHORS)
    counts, names = Counter(), {}
    for q in prof.get("queries", [])[:3]:
        try:
            data = oa_get("/works", {"search": q, "filter": "from_publication_date:2008-01-01,type:article|review",
                                     "sort": "cited_by_count:desc", "per_page": 50, "select": "id,authorships"})
        except Exception as e:
            log(f"people: query failed: {e}")
            continue
        for w in data.get("results", []):
            auths = w.get("authorships") or []
            for pos, a in enumerate(auths):
                au = a.get("author") or {}
                if not au.get("id"):
                    continue
                weight = 2 if pos == 0 or pos == len(auths) - 1 else 1
                aid = au["id"].rsplit("/", 1)[-1]
                counts[aid] += weight
                names[aid] = au.get("display_name", "")
    return [(a, names[a]) for a, _ in counts.most_common(40)]


def run(cfg: dict, prof: dict) -> dict:
    week = iso_week(utc_today())
    state = read_json(PATH, {"week": None, "current": None, "featured": []})
    if state.get("week") == week and state.get("current"):
        return state
    featured = set(state.get("featured", []))
    pick = next(((a, n) for a, n in top_authors(prof) if a not in featured), None)
    if not pick:
        return state if state.get("current") else {"week": week, "current": None, "featured": []}
    aid, _ = pick
    if MOCK:
        author, works = dict(mock_data.AUTHOR), [dict(w) for w in mock_data.TOP_WORKS]
    else:
        author = oa_get(f"/authors/{aid}", {"select": "id,display_name,last_known_institutions,works_count,cited_by_count,summary_stats,topics"})
        works = oa_get("/works", {"filter": f"author.id:{aid}", "sort": "cited_by_count:desc", "per_page": 5,
                                  "select": "id,title,publication_date,cited_by_count,doi"}).get("results", [])
    inst = ", ".join(i.get("display_name", "") for i in (author.get("last_known_institutions") or [])[:2])
    topics = [t.get("display_name", "") for t in (author.get("topics") or [])[:6]]
    facts = {"name": author.get("display_name"), "institution": inst, "works": author.get("works_count"),
             "citations": author.get("cited_by_count"), "h_index": (author.get("summary_stats") or {}).get("h_index"),
             "topics": topics, "top_papers": [{"n": i, "title": w.get("title"), "year": (w.get("publication_date") or "")[:4],
                                              "citations": w.get("cited_by_count")} for i, w in enumerate(works)]}
    r = llm_json(f"""Introduce a researcher to a PhD student in "{prof.get('field_summary')}".
Use ONLY these facts (from the OpenAlex database); do not add awards, positions, nationality or anything not listed.
Facts: {facts}

Return JSON: {{"headline": max 90 chars (who they are and what they are known for, based on topics and papers),
"known_for": 3 strings max 90 chars each, inferred cautiously from the topics and paper titles,
"why_follow": max 150 chars,
"read_first": [{{"n": paper number from top_papers, "why": max 90 chars what the paper title suggests it is about}}] (up to 3)}}""",
                 mock={"headline": "[SAMPLE] A researcher who works on ecosystem services", "known_for": ["[SAMPLE] Valuation", "[SAMPLE] Policy", "[SAMPLE] Methods"],
                       "why_follow": "[SAMPLE] Frequently appears on highly cited work.", "read_first": [{"n": 0, "why": "[SAMPLE] Foundational."}]})
    reads = []
    for x in r.get("read_first", [])[:3]:
        try:
            w = works[int(x["n"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        reads.append({"title": clip(w.get("title", ""), 110), "year": (w.get("publication_date") or "")[:4],
                      "citations": w.get("cited_by_count"), "url": w.get("doi") or w.get("id"), "why": clip(x.get("why", ""), 100)})
    current = {"name": facts["name"], "institution": inst, "headline": clip(r.get("headline", ""), 100),
               "known_for": [clip(k, 100) for k in r.get("known_for", [])][:3], "why_follow": clip(r.get("why_follow", ""), 160),
               "stats": {"works": facts["works"], "citations": facts["citations"], "h_index": facts["h_index"]},
               "read_first": reads, "profile_url": author.get("id"), "basis": "OpenAlex data"}
    state = {"week": week, "current": current, "featured": sorted(featured | {aid})}
    write_json(PATH, state)
    return state
