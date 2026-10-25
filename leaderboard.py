"""Online leaderboard using a Supabase (Postgres) REST table.

Works in the browser (pygbag, via JavaScript fetch) and on desktop (urllib in a thread).
All calls are non-blocking: start a request, then poll result(id).
"""
import itertools
import json
import sys
import threading

import config

WEB = sys.platform == "emscripten"
if WEB:
    import platform

_ids = itertools.count(1)
_results = {}
_js_ready = False

_JS = """
window.__fs = {};
window.__fsreq = function(id, url, method, key, body) {
  window.__fs[id] = 'pending';
  var opt = {method: method, headers: {apikey: key, Authorization: 'Bearer ' + key,
             'Content-Type': 'application/json'}};
  if (body) { opt.body = body; opt.headers['Prefer'] = 'return=minimal'; }
  fetch(url, opt).then(function(r) { return r.text().then(function(t) {
    window.__fs[id] = r.ok ? (t || 'OK') : ('{"error":' + r.status + '}'); }); })
  .catch(function(e) { window.__fs[id] = 'ERR'; });
};
"""

MODES = ("classic", "arcade", "zen", "sudden")


def enabled():
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY) and "YOUR-" not in config.SUPABASE_URL


def _request(method, path, body=None):
    global _js_ready
    rid = f"r{next(_ids)}"
    url = config.SUPABASE_URL.rstrip("/") + "/rest/v1/" + path
    data = json.dumps(body) if body is not None else ""
    if WEB:
        if not _js_ready:
            platform.window.eval(_JS)
            _js_ready = True
        platform.window.__fsreq(rid, url, method, config.SUPABASE_KEY, data)
        return rid
    _results[rid] = None

    def work():
        import urllib.request
        headers = {"apikey": config.SUPABASE_KEY, "Authorization": "Bearer " + config.SUPABASE_KEY,
                   "Content-Type": "application/json"}
        if data:
            headers["Prefer"] = "return=minimal"
        try:
            req = urllib.request.Request(url, data=data.encode() if data else None, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                _results[rid] = r.read().decode() or "OK"
        except Exception:
            _results[rid] = "ERR"

    threading.Thread(target=work, daemon=True).start()
    return rid


def result(rid):
    """None while pending, otherwise the response text ('ERR' or '{"error":..}' on failure)."""
    if WEB:
        try:
            v = platform.window.eval(f"window.__fs['{rid}'] || 'pending'")
        except Exception:
            return "ERR"
        return None if v == "pending" else str(v)
    return _results.get(rid)


def submit(name, score, mode):
    if mode not in MODES:
        raise ValueError("invalid mode")
    score = max(0, min(int(score), 100000))
    return _request("POST", "scores", {"name": name[:12], "score": score, "mode": mode})


def fetch(mode=None):
    q = "scores?select=name,score,mode&order=score.desc&limit=100"
    if mode:
        if mode not in MODES:
            raise ValueError("invalid mode")
        q += f"&mode=eq.{mode}"
    return _request("GET", q)


def parse_scores(text):
    """Best score per (player, mode), highest first, top 10. None on error."""
    try:
        rows = json.loads(text)
        if not isinstance(rows, list):
            return None
    except (ValueError, TypeError):
        return None
    seen, out = set(), []
    for r in rows:
        key = (str(r.get("name")).lower(), r.get("mode"))
        if key in seen or r.get("mode") not in MODES:
            continue
        seen.add(key)
        out.append({"name": str(r["name"])[:12], "score": int(r["score"]), "mode": r["mode"]})
    return out[:10]
