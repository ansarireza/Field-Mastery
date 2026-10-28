"""Step 4: new releases of the software you use (GitHub releases API, free)."""
from __future__ import annotations

import datetime as dt
import os

from . import mock_data
from .common import (STATE, clip, http_json, llm_json, log, log_week, read_json, utc_today, write_json, MOCK)


def latest_release(repo: str):
    if MOCK:
        return dict(mock_data.RELEASE)
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return http_json(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)


def run(cfg: dict, prof: dict) -> dict:
    today = utc_today()
    known = read_json(STATE / "tool_versions.json", {})
    history = read_json(STATE / "tools_history.json", [])
    fresh = []
    for repo in cfg.get("tools", {}).get("github_repos", []) or []:
        try:
            rel = latest_release(repo)
        except Exception as e:
            log(f"tools: {repo} skipped: {e}")
            continue
        tag = rel.get("tag_name", "")
        pub = (rel.get("published_at") or "")[:10]
        is_new = known.get(repo) != tag
        known[repo] = tag
        recent = pub and (today - dt.date.fromisoformat(pub)).days <= 45
        if is_new and recent:
            fresh.append({"repo": repo, "version": tag, "date": pub, "url": rel.get("html_url", ""),
                          "notes": (rel.get("body") or "")[:2500]})
    if fresh:
        listing = "\n\n".join(f"### {f['repo']} {f['version']} ({f['date']})\n{f['notes']}" for f in fresh)
        r = llm_json(f"""A PhD student works on: "{prof.get('field_summary')}".
These are release notes of software they may use. For each, summarise using ONLY the notes given.

{listing}

Return JSON {{"items": [{{"repo": same as above, "summary": max 160 chars on what changed,
"matters": max 130 chars on whether this could matter for research in this field (say 'unclear' if the notes do not tell)}}]}}""",
                     mock={"items": [{"repo": fresh[0]["repo"], "summary": "[SAMPLE] Adds a model and fixes bugs.", "matters": "[SAMPLE] Might matter for valuation work."}]})
        by = {x.get("repo"): x for x in r.get("items", [])}
        for f in fresh:
            x = by.get(f["repo"], {})
            history.insert(0, {"name": f["repo"], "version": f["version"], "date": f["date"], "url": f["url"],
                               "summary": clip(x.get("summary", ""), 170), "matters": clip(x.get("matters", ""), 140)})
    history = history[:25]
    write_json(STATE / "tool_versions.json", known)
    write_json(STATE / "tools_history.json", history)
    log_week(today, "tools", [f"{h['name']} {h['version']}" for h in history[:3]])
    return {"date": today.isoformat(), "items": history}
