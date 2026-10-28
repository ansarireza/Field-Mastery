"""Shared helpers: config, JSON files, HTTP, and the free LLM (Gemini)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FM_DATA", ROOT / "docs" / "data"))
STATE = Path(os.environ.get("FM_STATE", ROOT / "state"))
MOCK = os.environ.get("FM_MOCK") == "1"
UA = "field-mastery/1.0 (personal research digest)"

SYSTEM = (
    "You are a careful research assistant for a PhD student. Rules: "
    "(1) use ONLY the material given in the prompt; never invent facts, numbers, names, "
    "places, citations or results; (2) if something is not stated, say 'not stated'; "
    "(3) write in plain, simple English and explain jargon; (4) obey the length limits; "
    "(5) output valid JSON only, no commentary."
)


# --------------------------------------------------------------------------- basics
def log(*a):
    print(*a, file=sys.stderr, flush=True)


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def short_hash(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:10]


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return (cut or s[: n - 1]) + "…"


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def iso_week(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


# --------------------------------------------------------------------------- HTTP
def http_get(url, params=None, headers=None, retries=4):
    h = {"User-Agent": UA, **(headers or {})}
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=h, timeout=40)
            if r.status_code in (429, 500, 502, 503, 504):
                last = RuntimeError(f"HTTP {r.status_code} from {url}")
                time.sleep(2 ** i * 3)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** i * 2)
    raise RuntimeError(f"gave up on {url}: {last}")


def http_json(url, params=None, headers=None):
    return http_get(url, params, headers).json()


def http_text(url, params=None, headers=None):
    return http_get(url, params, headers).text


# --------------------------------------------------------------------------- LLM
_last_call = [0.0]


def _parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", t, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _gemini(model: str, prompt: str, system: str, temperature: float):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    cfg = load_config().get("llm", {})
    gap = float(cfg.get("min_interval_seconds", 13))
    last_err = None
    for attempt in range(5):
        wait = gap - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            r = requests.post(
                url,
                json=body,
                headers={"x-goog-api-key": key, "Content-Type": "application/json", "User-Agent": UA},
                timeout=120,
            )
        except requests.RequestException as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 503):
            last_err = RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini returned no text: {str(data)[:300]}")
        return _parse_json(text)
    raise RuntimeError(f"Gemini failed after retries: {last_err}")


def llm_json(prompt: str, mock=None, temperature: float = 0.3, system: str = SYSTEM):
    """Ask the free LLM for JSON. In mock mode returns `mock` (value or callable)."""
    if MOCK:
        return mock() if callable(mock) else mock
    cfg = load_config().get("llm", {})
    models = [os.environ.get("GEMINI_MODEL") or cfg.get("model", "gemini-2.5-flash")]
    if cfg.get("fallback_model"):
        models.append(cfg["fallback_model"])
    err = None
    for m in models:
        for _ in range(2):  # second try covers malformed JSON
            try:
                return _gemini(m, prompt, system, temperature)
            except json.JSONDecodeError as e:
                err = e
            except RuntimeError as e:
                err = e
                break
    raise RuntimeError(f"LLM call failed: {err}")


# --------------------------------------------------------------------------- weekly log
def log_week(day: dt.date, key: str, value):
    path = STATE / "week_log.json"
    data = read_json(path, {})
    cutoff = (day - dt.timedelta(days=14)).isoformat()
    data = {k: v for k, v in data.items() if k >= cutoff}
    data.setdefault(day.isoformat(), {})[key] = value
    write_json(path, data)
