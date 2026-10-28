"""Step 8: Defense Coach - one likely committee question a day, with an answer outline."""
from __future__ import annotations

from .common import STATE, clip, llm_json, log, read_json, short_hash, utc_today, write_json, MOCK

PATH = STATE / "defense.json"
TYPES = ["theory", "methods", "limitations", "contribution", "generalisability", "practical relevance", "alternative explanations"]


def _mock(n):
    return {"questions": [{"q": f"[SAMPLE] Question {i + 1}: why did you choose this approach?", "type": TYPES[i % len(TYPES)],
                           "outline": ["[SAMPLE] State your reason", "[SAMPLE] Name the alternative", "[SAMPLE] Explain the trade-off"],
                           "pitfall": "[SAMPLE] Do not overclaim.",
                           "follow_up": "[SAMPLE] What evidence would change your choice?",
                           "bring": "[SAMPLE] Bring a validation example and name its limits.",
                           "self_check": ["[SAMPLE] State your reasoning", "[SAMPLE] Address alternatives", "[SAMPLE] Acknowledge uncertainty"]} for i in range(n)]}


def run(cfg: dict, prof: dict) -> dict:
    dc = cfg.get("defense", {}) or {}
    if not dc.get("enabled", True):
        return {"enabled": False}
    sig = short_hash("defense-v2", cfg.get("research_question"), dc.get("title"), dc.get("chapters"), dc.get("methods"), dc.get("main_claims"))
    st = read_json(PATH, {})
    if st.get("sig") != sig:
        scopes = [{"scope": "the whole thesis", "info": cfg.get("research_question")}]
        for ch in dc.get("chapters") or []:
            scopes.append({"scope": ch.get("title"), "info": ch.get("summary", "")})
        bank = []
        for sc in scopes:
            r = llm_json(f"""A PhD student in "{prof.get('field_summary')}" will defend a thesis. Thesis title: {dc.get('title') or '(not given)'}.
Research question: {cfg.get('research_question')}. Methods: {dc.get('methods') or '(not given)'}. Main claims: {dc.get('main_claims') or '(not given)'}.
Scope for these questions: {sc['scope']}. Details: {sc['info']}

Write 6 tough but fair questions a committee member might ask about this scope, of different types
(theory, methods, limitations, contribution, generalisability, practical relevance, alternative explanations).
Base them only on the information above and on general scholarly practice - do not invent results.
Include probing questions about validation, alternative explanations, modelled supply versus
observed benefits, uncertainty and transferability between cities when relevant to this scope.
Add one tougher follow-up, an example of evidence the student should bring, and a self-check.
Use conditional answer guidance, not invented first-person claims about completed analyses.
Return JSON {{"questions": [{{"q": max 160 chars, "type": one of the types, "outline": 3 bullets max 90 chars on how to structure a strong answer,
"pitfall": max 110 chars, "follow_up": max 160 chars, "bring": max 160 chars,
"self_check": 3 short criteria for assessing the student's spoken answer}}]}}""", mock=lambda: _mock(6))
            for q in r.get("questions", []):
                bank.append({"id": short_hash(sc["scope"], q.get("q")), "scope": clip(sc["scope"] or "", 60), "q": clip(q.get("q", ""), 170),
                             "type": q.get("type", ""), "outline": [clip(o, 100) for o in q.get("outline", [])][:3],
                             "pitfall": clip(q.get("pitfall", ""), 120),
                             "follow_up": clip(q.get("follow_up", ""), 170),
                             "bring": clip(q.get("bring", ""), 170),
                             "self_check": [clip(x, 110) for x in q.get("self_check", [])][:3]})
        st = {"sig": sig, "bank": bank, "asked": [], "today": None, "today_date": None}
    today = utc_today().isoformat()
    if st.get("today_date") != today:
        left = [q for q in st["bank"] if q["id"] not in st["asked"]]
        if not left:  # restart the cycle
            st["asked"], left = [], st["bank"]
        if left:
            st["today"] = left[0]
            st["asked"].append(left[0]["id"])
        st["today_date"] = today
    write_json(PATH, st)
    return {"enabled": True, "date": today, "basis": "Configured study themes and methods; no unpublished findings or full thesis supplied", "today": st.get("today"), "bank_total": len(st["bank"]),
            "asked": len(st["asked"]), "upcoming": [q["q"] for q in [x for x in st["bank"] if x["id"] not in st["asked"]][:5]]}
