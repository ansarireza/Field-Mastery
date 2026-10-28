"""Step 1: turn the research question + keywords into a structured search profile."""
from __future__ import annotations

from . import mock_data
from .common import STATE, llm_json, read_json, short_hash, write_json, log

PATH = STATE / "profile.json"


def ensure_profile(cfg: dict) -> dict:
    sig = short_hash(cfg.get("research_question"), cfg.get("keywords"), cfg.get("regions"), cfg.get("level"))
    cur = read_json(PATH)
    if cur and cur.get("_sig") == sig:
        return cur
    log("profile: generating search profile")
    prompt = f"""A PhD student describes their field. Break it down into a search profile.

Research question: {cfg.get('research_question')}
Keywords: {', '.join(cfg.get('keywords', []))}
Regions: {', '.join(cfg.get('regions', []))}

Return JSON with exactly these keys:
- "field_summary": one sentence (max 160 chars) describing the field
- "areas": 10 sub-areas of knowledge a PhD in this field must master (short names, max 5 words each)
- "queries": 8 literature search queries (2-6 words each, no quotes, no boolean operators), covering different angles and synonyms
- "must_terms": 12 lowercase terms/phrases whose presence signals a relevant paper (singular, e.g. "ecosystem service")
- "region_terms": 10 lowercase words marking the geography/context of interest
- "policy_queries": 6 news-search queries about regulations, policies, treaties and funding that affect this field (3-6 words each)
- "event_queries": 3 news-search queries to find conferences or calls for papers in this field
- "debates": 6 objects {{"title": a real open debate in the field phrased as a question, "query": a 3-6 word literature search query for it}}
"""
    prof = llm_json(prompt, mock=mock_data.PROFILE)
    prof["_sig"] = sig
    write_json(PATH, prof)
    return prof
