"""Step 5: daily micro-lessons + quiz questions (feeds the Recall deck in the apps)."""
from __future__ import annotations

from . import mock_data
from .common import (DATA, STATE, clip, llm_json, log, log_week, read_json, short_hash, utc_today, write_json, MOCK)

CUR = STATE / "curriculum.json"
ARCHIVE = DATA / "learn_archive.json"


def _mock_topics():
    base = ["ecosystem service cascade", "total economic value", "contingent valuation", "choice experiment",
            "payments for ecosystem services", "additionality", "leakage", "ecosystem disservices",
            "social-ecological system", "common-pool resources"]
    return {"topics": [{"term": t, "area": mock_data.PROFILE["areas"][i % 10], "kind": "concept"} for i, t in enumerate(base)]}


def ensure_curriculum(cfg: dict, prof: dict) -> dict:
    cur = read_json(CUR, {"queue": [], "done": []})
    if len(cur["queue"]) >= 8:
        return cur
    done = [d for d in cur["done"]][-150:]
    r = llm_json(f"""Design the next part of a self-study curriculum for a PhD student in: "{prof.get('field_summary')}".
Level: {cfg.get('level', 'intermediate')}. Sub-areas: {', '.join(prof.get('areas', []))}.
Already covered or queued (do not repeat): {', '.join(done + [q['term'] for q in cur['queue']]) or 'nothing yet'}.

Return JSON {{"topics": [...]}} with 40 items {{"term": a concept, method, framework, policy instrument or foundational idea (max 6 words),
"area": one of the sub-areas above, "kind": "concept|method|framework|policy|classic_idea"}}.
Order from foundational to advanced, mixing sub-areas so every area is revisited regularly. Include adjacent knowledge the student
may lack (e.g. basic urban planning, economics, remote sensing, statistics) when relevant to the field.""", mock=_mock_topics)
    have = {t.lower() for t in done} | {q["term"].lower() for q in cur["queue"]}
    for t in r.get("topics", []):
        term = clip(t.get("term", ""), 60)
        if term and term.lower() not in have:
            cur["queue"].append({"term": term, "area": t.get("area", ""), "kind": t.get("kind", "concept")})
            have.add(term.lower())
    write_json(CUR, cur)
    return cur


def make_lesson(topic: dict, prof: dict, cfg: dict) -> dict:
    r = llm_json(f"""Write a micro-lesson for a PhD student in "{prof.get('field_summary')}" (level: {cfg.get('level', 'intermediate')}).
Topic: {topic['term']}  (type: {topic.get('kind', 'concept')}, area: {topic.get('area', '')})

Rules: plain simple English. Do NOT cite specific papers, authors, years or statistics unless you are certain; otherwise describe the idea generally.
If the topic is ambiguous or you are unsure, say so briefly in "plain".

Return JSON with keys:
"definition": max 150 chars, one sentence;
"plain": max 320 chars, explain it simply as to a smart newcomer;
"example": max 220 chars, a concrete example (prefer a Global South setting);
"connects": max 150 chars, how it relates to other ideas in the field;
"quiz": exactly 2 objects {{"q": short question max 110 chars, "a": short answer max 150 chars}};
"search": a 3-6 word query to find good sources on this topic.""",
                 mock={"definition": "[SAMPLE] A short definition.", "plain": "[SAMPLE] A plain-language explanation appears here.",
                       "example": "[SAMPLE] An example from a Global South setting.", "connects": "[SAMPLE] Links to related ideas.",
                       "quiz": [{"q": "[SAMPLE] What is it?", "a": "[SAMPLE] A sample answer."}, {"q": "[SAMPLE] Why does it matter?", "a": "[SAMPLE] Sample."}],
                       "search": "sample topic"})
    today = utc_today().isoformat()
    return {
        "id": short_hash(topic["term"]), "date": today, "term": topic["term"], "area": topic.get("area", ""),
        "kind": topic.get("kind", "concept"), "definition": clip(r.get("definition", ""), 170),
        "plain": clip(r.get("plain", ""), 350), "example": clip(r.get("example", ""), 240),
        "connects": clip(r.get("connects", ""), 170),
        "quiz": [{"q": clip(q.get("q", ""), 120), "a": clip(q.get("a", ""), 170)} for q in (r.get("quiz") or [])][:2],
        "search": r.get("search", topic["term"]),
    }


def run(cfg: dict, prof: dict) -> dict:
    today = utc_today().isoformat()
    archive = read_json(ARCHIVE, [])
    if archive and archive[-1]["date"] == today:  # already done today (re-runs)
        todays = [a for a in archive if a["date"] == today]
    else:
        cur = ensure_curriculum(cfg, prof)
        queue = read_json(STATE / "jargon_queue.json", [])
        todays = []
        n = int(cfg.get("learn", {}).get("lessons_per_day", 2))
        for _ in range(n):
            if queue:
                topic = {"term": queue.pop(0), "area": "From today's papers", "kind": "concept"}
            elif cur["queue"]:
                topic = cur["queue"].pop(0)
            else:
                break
            if any(a["id"] == short_hash(topic["term"]) for a in archive):
                continue
            try:
                lesson = make_lesson(topic, prof, cfg)
            except Exception as e:
                log(f"learn: lesson '{topic['term']}' failed: {e}")
                continue
            todays.append(lesson)
            archive.append(lesson)
            cur["done"].append(topic["term"])
        write_json(CUR, cur)
        write_json(STATE / "jargon_queue.json", queue)
        write_json(ARCHIVE, archive[-1500:])
    log_week(utc_today(), "lessons", [t["term"] for t in todays])
    return {"date": today, "lessons": todays, "total_learned": len(archive)}
