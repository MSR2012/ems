"""Demo-mode stand-in for Google's consent screen. Never asks for a Gmail password."""

from html import escape
from urllib.parse import urlencode

CONSENT_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in with Google (demo)</title>
<style>
 body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f1f5f9;color:#0f172a;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}}
 .card{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;max-width:440px;width:100%;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
 .logo{{font-weight:700;font-size:20px;letter-spacing:-.02em}} .logo span:nth-child(1){{color:#4285f4}} .logo span:nth-child(2){{color:#ea4335}} .logo span:nth-child(3){{color:#fbbc05}} .logo span:nth-child(4){{color:#34a853}}
 h1{{font-size:22px;margin:20px 0 6px}} p{{color:#475569;font-size:14px;line-height:1.5}}
 .acct{{display:flex;align-items:center;gap:10px;border:1px solid #e2e8f0;border-radius:999px;padding:6px 14px 6px 6px;width:fit-content;font-size:14px;margin:12px 0}}
 .av{{width:28px;height:28px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:600}}
 ul{{padding-left:18px;font-size:14px;color:#334155}} li{{margin:6px 0}}
 .demo{{background:#eef2ff;color:#3730a3;border-radius:8px;padding:10px 12px;font-size:13px;margin-top:16px}}
 .actions{{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}}
 a.btn{{text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;font-size:14px}}
 .deny{{color:#4338ca;border:1px solid #c7d2fe}} .allow{{background:#4f46e5;color:#fff}}
</style></head><body>
<main class="card" role="main">
 <div class="logo" aria-label="Google (demo)"><span>G</span><span>o</span><span>o</span><span>g</span>le <small style="color:#64748b;font-weight:500">demo</small></div>
 <h1>Inbox AI wants access to your Google Account</h1>
 <div class="acct"><div class="av">{initial}</div><span>{email}</span></div>
 <p>This will allow <strong>Inbox AI</strong> to:</p>
 <ul><li>View your email messages and settings (read-only)</li><li>See your primary Google Account email address</li></ul>
 <p>Inbox AI cannot send, delete, or modify your email.</p>
 <div class="demo">Demo mode: this simulates Google's OAuth consent screen. No password is requested or stored.</div>
 <div class="actions">
  <a class="btn deny" id="deny" href="{deny_url}">Cancel</a>
  <a class="btn allow" id="allow" href="{allow_url}">Allow</a>
 </div>
</main></body></html>"""


def render_consent(*, email: str, state: str, code: str, callback_url: str) -> str:
    allow = f"{callback_url}?{urlencode({'code': code, 'state': state})}"
    deny = f"{callback_url}?{urlencode({'error': 'access_denied', 'state': state})}"
    return CONSENT_HTML.format(initial=escape(email[:1].upper()), email=escape(email),
                               allow_url=escape(allow), deny_url=escape(deny))
