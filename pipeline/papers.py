"""Step 2: find new papers (OpenAlex), rank them, explain the best ones in plain language."""
from __future__ import annotations

import datetime as dt
import os

from . import mock_data
from .common import (STATE, clip, http_json, llm_json, log, log_week, read_json, utc_today, write_json, MOCK)

OA = "https://api.openalex.org"
SELECT = ("id,doi,title,publication_date,abstract_inverted_index,primary_location,"
          "authorships,cited_by_count,open_access,type")
GOOD_TYPES = {"article", "review", "preprint", None}


def oa_get(path: str, params: dict):
    params = dict(params)
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    else:
        log("warning: OPENALEX_API_KEY not set - only a tiny free budget is available")
    return http_json(f"{OA}{path}", params)


def abstract_from_inverted(inv) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def norm_work(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    auths = w.get("authorships") or []
    return {
        "id": (w.get("id") or "").rsplit("/", 1)[-1],
        "doi": w.get("doi"),
        "title": (w.get("title") or "").strip(),
        "date": w.get("publication_date"),
        "venue": src.get("display_name") or "",
        "authors": [a["author"]["display_name"] for a in auths[:6] if a.get("author")],
        "n_authors": len(auths),
        "abstract": abstract_from_inverted(w.get("abstract_inverted_index")),
        "cited_by": w.get("cited_by_count", 0),
        "oa": bool((w.get("open_access") or {}).get("is_oa")),
        "url": w.get("doi") or loc.get("landing_page_url") or w.get("id"),
        "type": w.get("type"),
    }


def score(work: dict, prof: dict, cfg: dict) -> float:
    t, a = work["title"].lower(), work["abstract"].lower()
    s = 0.0
    for term in prof.get("must_terms", []):
        term = term.lower()
        if term in t:
            s += 3
        elif term in a:
            s += 1
    s += min(4.5, 1.5 * sum(1 for r in prof.get("region_terms", []) if r.lower() in t + " " + a))
    if work["oa"]:
        s += 1
    journals = {j.lower() for j in cfg["papers"].get("watch_journals", [])}
    if work["venue"].lower() in journals:
        s += 2
    return s


def fetch_candidates(prof: dict, cfg: dict) -> list[dict]:
    if MOCK:
        return [dict(w) for w in mock_data.WORKS]
    pc = cfg["papers"]
    since = (utc_today() - dt.timedelta(days=int(pc.get("days_back", 3)))).isoformat()
    out = {}
    for q in prof.get("queries", [])[: int(pc.get("max_queries", 8))]:
        try:
            data = oa_get("/works", {
                "search": q, "per_page": 25, "select": SELECT,
                "filter": f"from_publication_date:{since},has_abstract:true",
            })
        except Exception as e:  # keep going with the other queries
            log(f"papers: query '{q}' failed: {e}")
            continue
        for w in data.get("results", []):
            nw = norm_work(w)
            if nw["type"] in GOOD_TYPES and nw["title"] and nw["abstract"]:
                out[nw["id"]] = nw
    return list(out.values())


def fetch_watch(cfg: dict) -> list[dict]:
    """New papers that cite the student's key references."""
    refs = cfg["papers"].get("key_references") or []
    if not refs or MOCK:
        return []
    since = (utc_today() - dt.timedelta(days=int(cfg["papers"].get("days_back", 3)))).isoformat()
    ids_path = STATE / "watch_ids.json"
    ids = read_json(ids_path, {})
    found = {}
    for doi in refs:
        try:
            if doi not in ids:
                ids[doi] = oa_get(f"/works/https://doi.org/{doi}", {"select": "id"})["id"].rsplit("/", 1)[-1]
            data = oa_get("/works", {"filter": f"cites:{ids[doi]},from_publication_date:{since}",
                                     "per_page": 10, "select": SELECT})
        except Exception as e:
            log(f"watch: {doi} failed: {e}")
            continue
        for w in data.get("results", []):
            nw = norm_work(w)
            if nw["title"]:
                nw["watch"] = f"Cites your reference doi:{doi}"
                found[nw["id"]] = nw
    write_json(ids_path, ids)
    return list(found.values())


def digest_one(work: dict, prof: dict, cfg: dict) -> dict:
    prompt = f"""A PhD student working on "{prof.get('field_summary')}" wants to understand this new paper.
Their level: {cfg.get('level', 'intermediate')}. Explain as to a smart person new to this sub-topic.
Use ONLY the title and abstract below.
Study context (not evidence about the paper): {cfg.get('research_question')}.
Methods the student is preparing to defend: {cfg.get('defense', {}).get('methods', '')}.
Never invent the student's findings. Separate an actual conflicting finding from
a possible limitation, a transferable method, or an unanswered question.

Title: {work['title']}
Journal: {work['venue'] or 'unknown'}   Date: {work['date']}
Abstract: {work['abstract'][:2500]}

Return JSON with exactly these keys (respect the character limits):
- "headline": max 60 chars, plain language, says what was found
- "bullets": exactly 3 strings, max 90 chars each: what they did / what they found / why it matters
- "plain": object with "question", "method", "finding", "why" - each max 150 chars, very simple words, no jargon
- "explainer": 120-180 words, a simple-language retelling of the whole abstract
- "caveats": 1-3 short strings on limits of the study (only what the abstract supports; say "not stated" if unknown)
- "jargon": up to 4 objects {{"term", "definition"}} (definition max 100 chars) for technical terms in the abstract
- "fit": max 140 chars - how this connects to the field "{prof.get('field_summary')}"
- "relevance": integer 1-5 (5 = a must-read for this field)
- "thesis": {{"why": max 180 chars connecting to the student's research,
  "action": max 140 chars suggesting a useful reading or checking step,
  "relationship": "supports|challenges|method|context|unclear" (use unclear when no thesis claim is supplied)}}
- "critical": {{"question": max 160 chars a fair examiner challenge prompted by this abstract,
  "evidence": max 220 chars explaining exactly what in the abstract motivates it,
  "limit": max 160 chars on what cannot be established from the abstract,
  "check": max 140 chars telling the student what to verify in the full paper}}
"""
    d = llm_json(prompt, mock=mock_data.DIGEST)
    d["headline"] = clip(d.get("headline", work["title"]), 70)
    d["bullets"] = [clip(b, 100) for b in (d.get("bullets") or [])][:3]
    return d


def run(cfg: dict, prof: dict) -> dict:
    today = utc_today()
    seen = set(read_json(STATE / "seen_works.json", []))
    pc = cfg["papers"]
    cands = [w for w in fetch_candidates(prof, cfg) if w["id"] not in seen]
    for w in cands:
        w["score"] = score(w, prof, cfg)
    cands = [w for w in cands if w["score"] >= 2.5] or cands[:0]
    cands.sort(key=lambda w: (w["score"], w["cited_by"]), reverse=True)
    watch = [w for w in fetch_watch(cfg) if w["id"] not in seen]
    chosen = watch[:3] + [w for w in cands if w["id"] not in {x["id"] for x in watch}][: int(pc.get("top_n", 6))]
    rest = [w for w in cands if w["id"] not in {x["id"] for x in chosen}][: int(pc.get("more_n", 10))]

    items = []
    for w in chosen:
        try:
            d = digest_one(w, prof, cfg)
        except Exception as e:
            log(f"papers: digest failed for {w['id']}: {e}")
            continue
        items.append({
            "id": w["id"], "title": w["title"], "headline": d["headline"], "bullets": d["bullets"],
            "plain": d.get("plain", {}), "full": {
                "explainer": d.get("explainer", ""), "caveats": d.get("caveats", []),
                "jargon": d.get("jargon", []), "fit": d.get("fit", ""),
            },
            "thesis": d.get("thesis") if isinstance(d.get("thesis"), dict) else {},
            "critical": d.get("critical") if isinstance(d.get("critical"), dict) else {},
            "relevance": d.get("relevance", 3), "watch": w.get("watch"),
            "source": {"url": w["url"], "doi": w["doi"], "venue": w["venue"], "date": w["date"],
                       "authors": w["authors"], "n_authors": w["n_authors"], "open_access": w["oa"],
                       "basis": "abstract"},
        })
    items.sort(key=lambda i: (bool(i["watch"]), i["relevance"]), reverse=True)

    summary = []
    if len(items) >= 2:
        try:
            heads = "\n".join(f"- {i['headline']}: {i['bullets'][1] if len(i['bullets']) > 1 else ''}" for i in items)
            r = llm_json(f"""Here are today's new papers in the field "{prof.get('field_summary')}".
{heads}
Write 2-3 lines (max 110 chars each) describing the main themes of today. Use only the information above.
Return JSON: {{"summary": [..]}}""", mock={"summary": ["[SAMPLE] Today's themes appear here."]})
            summary = [clip(s, 120) for s in r.get("summary", [])][:3]
        except Exception as e:
            log(f"papers: summary failed: {e}")

    queue = read_json(STATE / "jargon_queue.json", [])
    for it in items:
        for j in it["full"]["jargon"][:2]:
            if j.get("term") and j["term"].lower() not in {q.lower() for q in queue}:
                queue.append(j["term"])
    write_json(STATE / "jargon_queue.json", queue[-60:])

    if not items and not rest:  # nothing new (e.g. a same-day re-run): keep the existing file
        return None

    seen.update(w["id"] for w in chosen + rest)
    write_json(STATE / "seen_works.json", sorted(seen)[-6000:])
    log_week(today, "papers", [i["headline"] for i in items])

    return {
        "date": today.isoformat(), "summary": summary, "items": items,
        "more": [{"title": clip(w["title"], 110), "url": w["url"], "venue": w["venue"], "date": w["date"]} for w in rest],
    }
