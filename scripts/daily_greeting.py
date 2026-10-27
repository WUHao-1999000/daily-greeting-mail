#!/usr/bin/env python3
"""Daily greeting email - fully config-driven.

All changes (recipients, senders, schedule, style, wording) go through
config.json (editable via webui.py at http://127.0.0.1:8765).
This script does NOT need to be edited.

Usage:
  python daily_greeting.py --slot morning    # or midday / evening
  python daily_greeting.py --slot evening --dry-run   # render only
  python daily_greeting.py --auto            # send every slot whose
                                             # send_time in config is due
                                             # now (skip already-sent today)

Placeholders usable in config.json sentence pools:
  {city} {temp_now} {feels} {tmin} {tmax} {humidity}
  {sunrise_short} {sunset_short} {cond} {cond_capital}
  {tmin_tomorrow} {tmax_tomorrow} {cond_tomorrow} {cond_tomorrow_capital}
  {precip_tomorrow} {diff} {date} {wind}
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import smtplib
import socket
import ssl
import urllib.request
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
LOG_PATH = os.path.join(BASE, "logs", "greeting.log")
SLOTS = ["morning", "midday", "evening"]

WMO = {
    0: ("clear", "clear sky"), 1: ("mainly clear", "mainly clear"),
    2: ("partly cloudy", "partly cloudy"), 3: ("overcast", "overcast"),
    45: ("foggy", "fog"), 48: ("foggy", "freezing fog"),
    51: ("drizzling", "light drizzle"), 53: ("drizzling", "drizzle"),
    55: ("drizzling", "heavy drizzle"),
    61: ("rainy", "light rain"), 63: ("rainy", "rain"), 65: ("rainy", "heavy rain"),
    66: ("icy", "freezing rain"), 67: ("icy", "heavy freezing rain"),
    71: ("snowy", "light snow"), 73: ("snowy", "snow"), 75: ("snowy", "heavy snow"),
    77: ("snowy", "snow grains"),
    80: ("showery", "light showers"), 81: ("showery", "showers"),
    82: ("showery", "violent showers"),
    85: ("snowy", "snow showers"), 86: ("snowy", "heavy snow showers"),
    95: ("stormy", "thunderstorm"), 96: ("stormy", "thunderstorm with hail"),
    99: ("stormy", "severe thunderstorm"),
}


def log(msg):
    os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}\n")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_weather(cfg):
    s = cfg["settings"]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={s['latitude']}&longitude={s['longitude']}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
        "weather_code,sunrise,sunset&timezone=Asia%2FShanghai&forecast_days=2"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode())
    cur, d = data["current"], data["daily"]
    code_today, code_tmr = d["weather_code"][0], d["weather_code"][1]
    cond_today = WMO.get(code_today, ("variable", "mixed skies"))[0]
    cond_tmr = WMO.get(code_tmr, ("variable", "mixed skies"))[0]
    tmin_today, tmin_tmr = d["temperature_2m_min"][0], d["temperature_2m_min"][1]
    prob = d.get("precipitation_probability_max", [0, 0])[1]
    return {
        "city": s["city"],
        "temp_now": round(cur["temperature_2m"], 1),
        "feels": round(cur["apparent_temperature"], 1),
        "humidity": round(cur["relative_humidity_2m"]),
        "wind": round(cur["wind_speed_10m"]),
        "tmin": round(tmin_today, 1), "tmax": round(d["temperature_2m_max"][0], 1),
        "cond": cond_today, "cond_capital": cond_today.capitalize(),
        "tmin_tomorrow": round(tmin_tmr, 1),
        "tmax_tomorrow": round(d["temperature_2m_max"][1], 1),
        "cond_tomorrow": cond_tmr,
        "cond_tomorrow_capital": cond_tmr.capitalize(),
        "precip_tomorrow": f"{prob}% chance of rain",
        "diff": round(abs(tmin_tmr - tmin_today), 1),
        "sunrise_short": d["sunrise"][0][11:16],
        "sunset_short": d["sunset"][0][11:16],
        "date": dt.date.today().strftime("%b %d"),
    }


def fmt(s, v):
    out = s
    for k, val in v.items():
        out = out.replace("{" + k + "}", str(val))
    return out


def render(cfg, slot, w):
    sc = cfg["slots"][slot]
    rng = random.Random(f"{dt.date.today()}-{slot}")
    parts = [fmt(rng.choice(sc["openers"]), w)]
    if "reminders_pool" in sc:
        n = min(sc.get("reminder_count", 3), len(sc["reminders_pool"]))
        lines = []
        for i, p in enumerate(rng.sample(sc["reminders_pool"], n), 1):
            lines.append(f"{i}. " + fmt(re.sub(r"^\s*\d+[.)]\s*", "", p), w))
        parts.append("\n" + "\n".join(lines) + "\n")
    if "tomorrow_lines" in sc:
        parts.append("\n" + fmt(rng.choice(sc["tomorrow_lines"]), w) + "\n")
    parts.append("\n" + fmt(rng.choice(sc["closers"]), w))
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    subject = sc["emoji"] + " " + fmt(sc["subject_template"], w)
    return subject, body


def get_sender(cfg, sender_id):
    for s in cfg["senders"]:
        if s["id"] == sender_id:
            return s
    raise KeyError(f"sender id not found: {sender_id}")


def smtp_login(sender):
    socket.setdefaulttimeout(30)
    if sender.get("ssl"):
        smtp = smtplib.SMTP_SSL(sender["smtp_host"], sender["smtp_port"], timeout=30)
    else:
        smtp = smtplib.SMTP(sender["smtp_host"], sender["smtp_port"], timeout=30)
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
    secret = sender.get("auth_code") or sender.get("password")
    smtp.login(sender["email"], secret)
    return smtp


def send(cfg, sender_id, to_addr, subject, body):
    sender = get_sender(cfg, sender_id)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((sender.get("role", ""), sender["email"]))
    msg["To"] = to_addr
    smtp = smtp_login(sender)
    try:
        refused = smtp.sendmail(sender["email"], [to_addr], msg.as_string())
        if refused:
            raise RuntimeError(f"refused: {refused}")
    finally:
        smtp.quit()
    return sender["email"]


def pick_fallback(cfg, primary_id):
    enabled = [s["id"] for s in cfg["senders"]
               if s.get("enabled", True) and s["id"] != primary_id]
    fb = cfg.get("fallback_sender_id")
    return fb if fb in enabled else (enabled[0] if enabled else None)


def dispatch_slot(cfg, slot, subject, body, dry_run=False):
    """Send one rendered letter to all enabled recipients. Returns result list."""
    results = []
    recipients = [r["email"] for r in cfg["recipients"] if r.get("enabled", True)]
    if not recipients:
        raise RuntimeError("No enabled recipients in config.json")
    for to_addr in recipients:
        if dry_run:
            results.append({"to": to_addr, "ok": True, "via": "dry-run"})
            continue
        try:
            sent_from = send(cfg, cfg["slots"][slot]["sender_id"], to_addr,
                             subject, body)
            tag = "SENT"
        except Exception as e:
            fb = pick_fallback(cfg, cfg["slots"][slot]["sender_id"])
            log(f"FAIL {slot} -> {to_addr} via "
                f"{cfg['slots'][slot]['sender_id']}: {e}")
            if not fb:
                results.append({"to": to_addr, "ok": False, "error": str(e)})
                continue
            sent_from = send(cfg, fb, to_addr, subject, body)
            tag = "SENT(fallback)"
        print(f"{tag} [{slot}] {sent_from} -> {to_addr} | {subject}")
        log(f"{tag} [{slot}] {sent_from} -> {to_addr} | {subject}")
        results.append({"to": to_addr, "ok": True, "via": sent_from})
    return results


def slots_sent_today():
    if not os.path.exists(LOG_PATH):
        return set()
    today = dt.date.today().isoformat()
    sent = set()
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"[{today}"):
                m = re.search(r"SENT(?:\(fallback\))? \[(\w+)\]", line)
                if m:
                    sent.add(m.group(1))
    return sent


def slot_due(cfg, slot, now=None):
    """Minutes since this slot's send_time; None if outside today's window."""
    now = now or dt.datetime.now()
    hh, mm = map(int, cfg["slots"][slot]["send_time"].split(":"))
    delta = (now - now.replace(hour=hh, minute=mm, second=0,
                               microsecond=0)).total_seconds() / 60
    return delta if 0 <= delta <= 55 else None


def run_slot(cfg, slot, dry_run=False):
    w = fetch_weather(cfg)
    subject, body = render(cfg, slot, w)
    if dry_run:
        return {"slot": slot, "subject": subject, "body": body}
    results = dispatch_slot(cfg, slot, subject, body)
    return {"slot": slot, "subject": subject, "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=SLOTS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--auto", action="store_true",
                    help="send every slot whose send_time is due now and "
                         "not sent today")
    args = ap.parse_args()

    cfg = load_config()

    if args.auto:
        sent = slots_sent_today()
        for slot in SLOTS:
            if slot in sent:
                print(f"SKIP [{slot}] already sent today")
                continue
            if slot_due(cfg, slot) is None:
                print(f"SKIP [{slot}] not in send window "
                      f"(send_time={cfg['slots'][slot]['send_time']})")
                continue
            run_slot(cfg, slot)
        return

    slot = args.slot or detect_slot(cfg)
    if args.dry_run:
        r = run_slot(cfg, slot, dry_run=True)
        print(f"[{slot}] subject: {r['subject']}\n---\n{r['body']}")
        return
    run_slot(cfg, slot)


def detect_slot(cfg):
    now = dt.datetime.now()
    best, best_gap = "morning", None
    for name in SLOTS:
        hh, mm = map(int, cfg["slots"][name]["send_time"].split(":"))
        gap = (now - now.replace(hour=hh, minute=mm, second=0,
                                 microsecond=0)).total_seconds()
        if gap >= 0 and (best_gap is None or gap < best_gap):
            best, best_gap = name, gap
    return best


if __name__ == "__main__":
    main()
