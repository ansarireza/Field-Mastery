"""Step 9: weekly review, built from this week's own log (no new searching)."""
from __future__ import annotations

from .common import DATA, STATE, clip, iso_week, llm_json, read_json, utc_today, write_json


def run(cfg: dict, prof: dict, force: bool = False) -> dict | None:
    today = utc_today()
    # Give new installations an initial partial review, then refresh weekly.
    if not force and today.weekday() != int(cfg.get("weekly_review_day", 6)) and read_json(DATA / "weekly.json"):
        return None
    log = read_json(STATE / "week_log.json", {})
    days = sorted(log)[-7:]
    papers = [h for d in days for h in log[d].get("papers", [])]
    radar = [h for d in days for h in log[d].get("radar", [])]
    lessons = [h for d in days for h in log[d].get("lessons", [])]
    tools = [h for d in days for h in log[d].get("tools", [])]
    r = llm_json(f"""Write a weekly review for a PhD student in "{prof.get('field_summary')}" using ONLY the lists below.

Papers seen this week: {papers}
Radar items: {radar}
Concepts studied: {lessons}
These are materials introduced by the app, not proof that the student read or mastered them.
Software releases: {tools}

Return JSON {{"themes": 4 strings max 120 chars (what moved in the field this week, only if supported by the lists),
"learned": 1 string max 140 chars summarising what was studied,
"next": 3 strings max 100 chars suggesting what to read or review next week}}""",
                 mock={"themes": ["[SAMPLE] Weekly themes appear here."], "learned": "[SAMPLE] You studied several concepts.", "next": ["[SAMPLE] Review weak topics."]})
    out = {"week": iso_week(today), "date": today.isoformat(), "partial": today.weekday() != int(cfg.get("weekly_review_day", 6)), "themes": [clip(t, 130) for t in r.get("themes", [])][:4],
           "learned": clip(r.get("learned", ""), 150), "next": [clip(n, 110) for n in r.get("next", [])][:3],
           "counts": {"papers": len(papers), "radar": len(radar), "lessons": len(lessons)}}
    return out
