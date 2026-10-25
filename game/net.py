"""Leaderboard + nickname glue (non-blocking). Logic moved unchanged from the original main.py."""
import json

import leaderboard

SHORT = {"classic": "Classic", "arcade": "Arcade", "zen": "Zen", "sudden": "Sudden"}

NAME_JS = """
(function(){
var old=document.getElementById('nm_ov'); if(old) old.remove();
window.__nm=undefined;
var first=__FIRST__==1, cur=__CUR__;
var ov=document.createElement('div'); ov.id='nm_ov';
ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.65);display:flex;align-items:center;justify-content:center;z-index:99999;font-family:sans-serif';
ov.innerHTML='<div style="background:#2b1d12;border:3px solid #ffb347;border-radius:18px;padding:22px 26px;width:min(86vw,360px);text-align:center;color:#fff">'
+'<div style="font-size:22px;font-weight:bold;color:#ffb347">Enter your nickname</div>'
+'<div style="font-size:14px;margin:8px 0 14px;opacity:.85">Do NOT use your real name.<br>It shows on the public leaderboard.</div>'
+'<input id="nm_in" maxlength="12" autocomplete="off" placeholder="Nickname" style="width:100%;box-sizing:border-box;font-size:20px;padding:10px;border-radius:10px;border:2px solid #ffb347;text-align:center">'
+'<button id="nm_ok" style="margin-top:14px;font-size:20px;padding:10px 28px;border:0;border-radius:12px;background:#ff7a1a;color:#fff;font-weight:bold">Play!</button>'
+(first?'':'<button id="nm_x" style="margin:14px 0 0 10px;font-size:16px;padding:10px 16px;border:0;border-radius:12px;background:#555;color:#fff">Cancel</button>')
+'</div>';
document.body.appendChild(ov);
var inp=document.getElementById('nm_in'); inp.value=cur;
['keydown','keyup','keypress'].forEach(function(e){inp.addEventListener(e,function(ev){ev.stopPropagation();if(e=='keydown'&&ev.key=='Enter')ok();});});
function done(v){ov.remove();window.__nm=v;}
function ok(){var v=inp.value.trim(); if(!v){inp.style.borderColor='red';return;} done(v);}
document.getElementById('nm_ok').onclick=ok;
var x=document.getElementById('nm_x'); if(x) x.onclick=function(){done('\\x00');};
setTimeout(function(){inp.focus();},50);
})();
"""


def clean_name(s):
    s = "".join(ch for ch in (s or "") if ch.isprintable()).strip()[:12]
    return s or "Player"


class Board:
    def __init__(self, save):
        self.save = save
        self.rows = []
        self.status = "Loading..."
        self.req = None
        self.next_at = 0
        self.submit_req = None
        self.submit_msg = ""
        self.web_name_pending = False

    def refresh(self, now_ms, force=False):
        if self.req is not None or (now_ms < self.next_at and not force):
            return
        self.next_at = now_ms + 30000
        if not leaderboard.enabled():
            self.status = "Not set up yet"
            return
        self.req = leaderboard.fetch(None)

    def submit(self, score, mode):
        if score > 0 and leaderboard.enabled():
            self.submit_msg = "Saving score..."
            self.submit_req = leaderboard.submit(self.save["name"], score, mode)

    def poll(self):
        """Returns a finished web nickname (str) when the JS dialog completes, else None."""
        name = None
        if self.web_name_pending:
            try:
                import platform
                v = platform.window.eval("window.__nm===undefined?null:window.__nm")
            except Exception:
                v = None
            if v is not None:
                self.web_name_pending = False
                platform.window.eval("window.__nm=undefined")
                name = str(v)
        if self.req is not None:
            res = leaderboard.result(self.req)
            if res is not None:
                self.req = None
                rows = leaderboard.parse_scores(res)
                if rows is None:
                    self.status = "Offline"
                else:
                    self.rows = rows[:3]
                    self.status = "" if rows else "Be the first!"
        if self.submit_req is not None:
            res = leaderboard.result(self.submit_req)
            if res is not None:
                self.submit_req = None
                ok = res != "ERR" and not res.startswith("{")
                self.submit_msg = "Score saved to leaderboard!" if ok else "Couldn't save score"
                if ok:
                    self.next_at = 0
        return name

    def open_web_name(self, first):
        import platform
        self.web_name_pending = True
        platform.window.eval(NAME_JS.replace("__FIRST__", "1" if first else "0")
                             .replace("__CUR__", json.dumps(self.save.get("name", ""))))
