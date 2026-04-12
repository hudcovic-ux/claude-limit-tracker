#!/usr/local/bin/python3.14
# -*- coding: utf-8 -*-
# <xbar.title>Claude Limit Tracker</xbar.title>
# <xbar.version>v5.0</xbar.version>
# <xbar.author>Robin Hudcovic</xbar.author>
# <xbar.desc>Sleduje Claude.ai limity – bez otevírání oken Chrome</xbar.desc>
# <xbar.refreshOnWake>true</xbar.refreshOnWake>

"""
Strategie (bez jakéhokoli otevírání Chrome oken):

1. CHROME TAB (tichý): Pokud je claude.ai záložka již otevřená v Chrome,
   zavolá API přes JavaScript – Cloudflare nás nepropustí (nemá co blokovat).

2. PŘÍMÉ HTTP: Extrahuje cookies z Chrome DB + volá API přes curl.
   Funguje dokud je cf_clearance platný (až 30 dní, stejné IP).

3. CACHE: Pokud obě metody selžou, zobrazí poslední úspěšná data
   s informací o stáří.

Nikdy samo neotevírá Chrome okno.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone

import tls_client
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

SCRIPT_DIR  = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CACHE_FILE  = os.path.join(SCRIPT_DIR, "cache.json")
COOKIES_DB  = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies")


# ─────────────────────────────────────────────
# Config a cache
# ─────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(data):
    data["cached_at"] = datetime.now(timezone.utc).isoformat()
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────
# Metoda A: Chrome tab přes AppleScript + XHR
# ─────────────────────────────────────────────
def run_applescript(script):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".applescript", delete=False) as f:
        f.write(script)
        tmp = f.name
    try:
        r = subprocess.run(["osascript", tmp], capture_output=True, text=True, timeout=15)
    finally:
        try: os.unlink(tmp)
        except OSError: pass
    if r.returncode != 0:
        err = r.stderr.strip()
        if "JavaScript through AppleScript is turned off" in err:
            raise RuntimeError("JS_DISABLED")
        raise RuntimeError(err)
    return r.stdout.strip()


def api_via_chrome_tab(path):
    """Zavolá API přes XHR v existující claude.ai záložce Chrome."""
    js = (
        "var x=new XMLHttpRequest();"
        f"x.open('GET','{path}',false);"
        "x.withCredentials=true;"
        "x.send();"
        "x.status+'|'+x.responseText"
    )
    script = f'''tell application "Google Chrome"
    set windowList to every window
    repeat with w in windowList
        repeat with t in every tab of w
            if URL of t contains "claude.ai" then
                return execute t javascript "{js}"
            end if
        end repeat
    end repeat
    return "NO_CLAUDE_TAB"
end tell'''
    out = run_applescript(script)
    if out == "NO_CLAUDE_TAB":
        raise RuntimeError("NO_CLAUDE_TAB")
    status, _, body = out.partition("|")
    if status.strip() != "200":
        raise RuntimeError(f"HTTP_{status.strip()}")
    return json.loads(body)


# ─────────────────────────────────────────────
# Metoda B: Přímé HTTP přes curl + Chrome cookies
# ─────────────────────────────────────────────
def get_chrome_aes_key():
    r = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError("KEYCHAIN_DENIED")
    password = r.stdout.strip().encode("utf-8")
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def decrypt_chrome_cookie(enc, key):
    if bytes(enc)[:3] != b"v10":
        return bytes(enc).decode("utf-8", errors="replace")
    payload = bytes(enc)[3:]
    iv = b" " * 16
    dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
    raw = dec.update(payload) + dec.finalize()
    pad = raw[-1]
    raw = raw[:-pad]
    # Chrome 101+: 32-bajtový prefix před skutečnou hodnotou
    return raw[32:].decode("utf-8", errors="replace")


def read_chrome_cookies():
    if not os.path.exists(COOKIES_DB):
        raise RuntimeError("CHROME_COOKIES_NOT_FOUND")
    key = get_chrome_aes_key()
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(COOKIES_DB, tmp)
    try:
        conn = sqlite3.connect(tmp)
        c = conn.cursor()
        c.execute("""
            SELECT name, encrypted_value
            FROM cookies
            WHERE host_key LIKE '%claude.ai%'
            GROUP BY name
            HAVING last_access_utc = MAX(last_access_utc)
        """)
        cookies = {}
        for name, enc_val in c.fetchall():
            try:
                cookies[name] = decrypt_chrome_cookie(enc_val, key)
            except Exception:
                pass
        conn.close()
    finally:
        try: os.remove(tmp)
        except OSError: pass
    return cookies


def api_via_http(path, cookies):
    """
    Zavolá API přes tls-client (napodobuje Chrome TLS fingerprint).
    Obchází Cloudflare bez potřeby otevřeného Chrome okna.
    """
    session = tls_client.Session(
        client_identifier="chrome_120",
        random_tls_extension_order=True,
    )
    session.cookies.update({
        k: v for k, v in cookies.items()
        if k in ("sessionKey", "cf_clearance", "__ssid")
    })
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://claude.ai/",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    })
    resp = session.get(f"https://claude.ai{path}", timeout_seconds=10)
    if resp.status_code == 403 or (resp.status_code == 200 and "Just a moment" in resp.text):
        raise RuntimeError("CLOUDFLARE_BLOCK")
    if resp.status_code == 401:
        raise RuntimeError("SESSION_EXPIRED")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP_{resp.status_code}")
    return resp.json()


# ─────────────────────────────────────────────
# Orchestrace API volání
# ─────────────────────────────────────────────
_chrome_cookies_cache = None


def call_api(path):
    global _chrome_cookies_cache
    # Metoda A: existující Claude.ai tab v Chrome
    try:
        return api_via_chrome_tab(path)
    except RuntimeError:
        pass  # tab neexistuje nebo Chrome neběží → zkusit metodu B

    # Metoda B: přímé HTTP s Chrome cookies
    try:
        if _chrome_cookies_cache is None:
            _chrome_cookies_cache = read_chrome_cookies()
        return api_via_http(path, _chrome_cookies_cache)
    except RuntimeError:
        raise  # propagovat (CLOUDFLARE_BLOCK, SESSION_EXPIRED, KEYCHAIN_DENIED…)


# ─────────────────────────────────────────────
# Formátování
# ─────────────────────────────────────────────
def format_bar(pct, width=8):
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def format_reset(iso_str):
    if not iso_str:
        return "?"
    try:
        dt  = datetime.fromisoformat(iso_str).astimezone()
        now = datetime.now(timezone.utc).astimezone()
        secs = (dt - now).total_seconds()
        h, m = int(secs // 3600), int((secs % 3600) // 60)
        t = dt.strftime("%H:%M")
        if h > 0:   return f"{t} (za {h}h {m}m)"
        elif m > 0: return f"{t} (za {m}m)"
        else:       return f"{t} (brzy)"
    except Exception:
        return iso_str[:16]


def cache_age_str(cached_at):
    try:
        dt   = datetime.fromisoformat(cached_at).astimezone()
        now  = datetime.now(timezone.utc).astimezone()
        secs = (now - dt).total_seconds()
        h, m = int(secs // 3600), int((secs % 3600) // 60)
        if h > 0:   return f"stará {h}h {m}m"
        elif m > 0: return f"stará {m}m"
        else:       return "čerstvá"
    except Exception:
        return "?"


def pick_best_org_and_usage(orgs, preferred_uuid=None):
    best_org, best_usage, best_score = None, None, -1
    for org in orgs:
        if "chat" not in org.get("capabilities", []):
            continue
        if preferred_uuid and org["uuid"] != preferred_uuid:
            continue
        try:
            usage = call_api(f"/api/organizations/{org['uuid']}/usage")
        except Exception:
            continue
        five_pct  = (usage.get("five_hour") or {}).get("utilization") or 0.0
        seven_pct = (usage.get("seven_day")  or {}).get("utilization") or 0.0
        score = five_pct + seven_pct
        if org.get("billing_type", "none") not in ("none", ""):
            score += 0.001
        if best_org is None or score > best_score:
            best_score, best_org, best_usage = score, org, usage
    return best_org, best_usage


# ─────────────────────────────────────────────
# Výstup xbar
# ─────────────────────────────────────────────

def icon_for_pct(pct):
    if pct >= 90: return "🔴"
    if pct >= 75: return "⚠️"
    if pct >= 50: return "🟠"
    return "🤖"


def print_data(five_pct, seven_pct, five_reset, seven_reset, org_name, note=None):
    d_icon = icon_for_pct(five_pct)
    w_icon = icon_for_pct(seven_pct)
    print(f"D:{d_icon}{int(five_pct)}% · W:{w_icon}{int(seven_pct)}%")
    print("---")
    print(f"{org_name} | color=gray size=11")
    if note:
        print(f"{note} | color=gray size=10")
    print("---")

    bar5 = format_bar(five_pct)
    print(f"5h:    {bar5}  {int(five_pct)}% | color=#00FF41 font=Menlo")
    if five_reset:
        print(f"       Reset: {format_reset(five_reset)} | size=11 color=gray")
    print("")
    bar7 = format_bar(seven_pct)
    print(f"7 dní: {bar7}  {int(seven_pct)}% | color=#00FF41 font=Menlo")
    if seven_reset:
        print(f"       Reset: {format_reset(seven_reset)} | size=11 color=gray")

    print("---")
    print(f"Updated: {datetime.now().strftime('%H:%M')} | size=11 color=gray")
    print("Refresh | refresh=true")
    print("Quit xbar | bash=/usr/bin/pkill param1=-x param2=xbar terminal=false")


def print_from_cache(reason_line):
    cache = load_cache()
    if not cache.get("five_pct"):
        # Žádná cache
        print("D:🤖— · W:🤖—")
        print("---")
        print(reason_line)
        print("---")
        print("Refresh | refresh=true")
        print("Quit xbar | bash=/usr/bin/pkill param1=-x param2=xbar terminal=false")
        return
    age = cache_age_str(cache.get("cached_at", ""))
    print_data(
        five_pct   = cache.get("five_pct", 0),
        seven_pct  = cache.get("seven_pct", 0),
        five_reset = cache.get("five_reset"),
        seven_reset= cache.get("seven_reset"),
        org_name   = cache.get("org_name", ""),
        note       = f"⏳ Cache {age} – {reason_line}",
    )


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    config         = load_config()
    preferred_uuid = config.get("org_uuid")

    try:
        orgs = call_api("/api/organizations")
        if not isinstance(orgs, list) or not orgs:
            raise RuntimeError("Žádné organizace")

        best_org, usage = pick_best_org_and_usage(orgs, preferred_uuid)
        if not usage:
            raise RuntimeError("Nepodařilo se načíst usage data")

        five_h    = usage.get("five_hour") or {}
        seven_d   = usage.get("seven_day")  or {}
        five_pct  = float(five_h.get("utilization") or 0)
        seven_pct = float(seven_d.get("utilization") or 0)
        five_reset  = five_h.get("resets_at")
        seven_reset = seven_d.get("resets_at")
        org_name    = best_org.get("name", "").replace("'s Organization", "")

        # Uložit do cache
        save_cache(dict(
            five_pct=five_pct, seven_pct=seven_pct,
            five_reset=five_reset, seven_reset=seven_reset,
            org_name=org_name,
        ))

        print_data(five_pct, seven_pct, five_reset, seven_reset, org_name)

    except RuntimeError as e:
        err = str(e)
        if err == "CLOUDFLARE_BLOCK":
            print_from_cache("otevři claude.ai v Chrome pro obnovu")
        elif err == "SESSION_EXPIRED":
            print_from_cache("přihlas se na claude.ai")
        elif err == "KEYCHAIN_DENIED":
            print_from_cache("povol Keychain (Always Allow)")
        elif err == "CHROME_COOKIES_NOT_FOUND":
            print_from_cache("Chrome nenalezen")
        elif err == "JS_DISABLED":
            print("⚠️ Setup")
            print("---")
            print("V Chrome povol: View → Developer")
            print("→ Allow JavaScript from Apple Events")
            print("---")
            print("Refresh | refresh=true")
        else:
            print_from_cache(err[:60])
    except Exception as e:
        print_from_cache(str(e)[:60])


if __name__ == "__main__":
    main()
