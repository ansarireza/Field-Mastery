"""Daily entry point:  python -m pipeline.build_digest   (add --mock to test offline)."""
from __future__ import annotations

import argparse
import os
import traceback

from . import briefing, debates, defense, learn, papers, people, radar, tools, weekly
from .common import DATA, load_config, log, read_json, utc_today, write_json
from .profile_gen import ensure_profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="offline test with sample data")
    ap.add_argument("--force-weekly", action="store_true")
    ap.add_argument("--only", help="comma-separated steps to run")
    args = ap.parse_args()
    if args.mock:
        os.environ["FM_MOCK"] = "1"
        import pipeline.common as c
        c.MOCK = True
        import pipeline.papers as p
        p.MOCK = True
        for mod in (radar, tools, people, debates, defense, learn):
            mod.MOCK = True

    # The repo ships with clearly-labelled SAMPLE data so the apps show something on day 0.
    # The first real run wipes it so sample items never mix with real ones.
    meta = read_json(DATA / "meta.json", {})
    if meta.get("sample") and not args.mock:
        for f in DATA.glob("*.json"):
            f.unlink()
        log("removed sample data")

    cfg = load_config()
    errors = {}
    prof = ensure_profile(cfg)

    steps = {
        "today": lambda: papers.run(cfg, prof),
        "radar": lambda: radar.run(cfg, prof),
        "tools": lambda: tools.run(cfg, prof),
        "learn": lambda: learn.run(cfg, prof),
        "people": lambda: people.run(cfg, prof),
        "debates": lambda: debates.run(cfg, prof),
        "defense": lambda: defense.run(cfg, prof),
        "weekly": lambda: weekly.run(cfg, prof, force=args.force_weekly),
        "briefing": lambda: briefing.run(cfg, prof),
    }
    only = set(args.only.split(",")) if args.only else None
    for name, fn in steps.items():
        if only and name not in only:
            continue
        try:
            out = fn()
            if out is not None:  # keep yesterday's file if a step produced nothing
                if args.mock and isinstance(out, dict):
                    out["sample"] = True
                write_json(DATA / f"{name}.json", out)
            log(f"ok: {name}")
        except Exception as e:  # one failing step must not stop the others
            # Detailed exceptions can contain authenticated request URLs. Keep
            # public feed diagnostics useful without copying those into JSON.
            errors[name] = f"{type(e).__name__}: section update failed; see the GitHub Actions log"
            log(f"FAILED: {name}: {e}")
            traceback.print_exc()

    # knowledge map: how many lessons per area so far (the apps add your recall scores)
    archive = read_json(DATA / "learn_archive.json", [])
    counts = {a: 0 for a in prof.get("areas", [])}
    for a in archive:
        counts[a.get("area", "")] = counts.get(a.get("area", ""), 0) + 1
    write_json(DATA / "map.json", {"date": utc_today().isoformat(), "areas": [{"name": k, "lessons": v} for k, v in counts.items() if k]})

    status = {}
    for section in [*steps, "map"]:
        content = read_json(DATA / f"{section}.json")
        status[section] = {"state": "error" if section in errors else "ready" if content else "waiting",
                           "date": (content.get("date") or content.get("week")) if isinstance(content, dict) else None,
                           "error": errors.get(section)}
    radar_health = (read_json(DATA / "radar.json", {}) or {}).get("sources", {})
    if radar_health.get("failed") and status["radar"]["state"] == "ready":
        status["radar"]["state"] = "partial"
    write_json(DATA / "meta.json", {
        "generated_at": utc_today().isoformat(), "field": prof.get("field_summary"),
        "sample": bool(args.mock), "errors": errors, "version": 2, "status": status,
        "sections": ["today", "radar", "learn", "recall", "people", "tools", "debates", "defense", "weekly", "map", "briefing"],
    })
    if errors:
        log("finished with errors:", errors)


if __name__ == "__main__":
    main()
