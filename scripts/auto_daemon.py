#!/usr/bin/env python3
"""Greeting-mail daemon: checks every 10 minutes whether any slot is due
and sends it. Designed to run hidden (pythonw) from the Windows Startup
folder, so email sending survives reboots without WorkBuddy being open.

All logic (schedule, dedup, fallback) lives in daily_greeting.py and
config.json - this file is only a loop.

Usage:
  pythonw auto_daemon.py          # run forever, check every 10 min
  python  auto_daemon.py --once   # single check, then exit (for testing)
"""
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

import daily_greeting as dg  # noqa: E402

CHECK_INTERVAL_SEC = 600  # 10 minutes


def cycle():
    cfg = dg.load_config()
    sent = dg.slots_sent_today()
    for slot in dg.SLOTS:
        if slot in sent:
            continue
        if dg.slot_due(cfg, slot) is None:
            continue
        try:
            dg.run_slot(cfg, slot)
            dg.log(f"DAEMON handled slot [{slot}]")
        except Exception as e:
            dg.log(f"DAEMON ERROR {slot}: {type(e).__name__}: {e}")


def main():
    if "--once" in sys.argv:
        cycle()
        print("single check done")
        return
    dg.log("DAEMON started")
    while True:
        try:
            cycle()
        except Exception as e:
            try:
                dg.log(f"DAEMON CYCLE ERROR: {type(e).__name__}: {e}")
            except Exception:
                pass
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
