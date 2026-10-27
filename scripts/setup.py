#!/usr/bin/env python3
"""One-shot installer for the daily-greeting-mail system.

Copies config.template.json -> config.json in the target directory, fills in
user-provided accounts, registers Windows autostart entries, and prints the
next steps. Collect credentials ONLY from the user - never hardcode any.

Usage (all flags optional; missing values fall back to interactive prompts):

  python setup.py --dir "C:/path/to/install" \
      --city-cn 北京 --lat 39.9042 --lon 116.4074 \
      --recipient someone@gmail.com \
      --sender "whxxx@163.com|PESxxxxxxxx|smtp.163.com|465|ssl|Morning" \
      --sender "someone@corp.example|pass123|smtp.qiye.aliyun.com|465|ssl|Evening" \
      --times "07:30,12:30,22:00" \
      --admin-password mySecret123 \
      --no-autostart          # skip writing Startup entries (for testing)
"""
import argparse
import getpass
import json
import os
import secrets
import shutil
import socket
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SLOTS = ["morning", "midday", "evening"]

SMTP_PRESETS = {
    "163": ("smtp.163.com", 465, True),
    "126": ("smtp.126.com", 465, True),
    "qq": ("smtp.qq.com", 465, True),
    "gmail": ("smtp.gmail.com", 465, True),
    "aliyun-enterprise": ("smtp.qiye.aliyun.com", 465, True),
    "outlook": ("smtp-mail.outlook.com", 587, False),  # may be blocked by MS
}

DEFAULT_CITIES = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551), "成都": (30.5728, 104.0668),
    "武汉": (30.5928, 114.3055), "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969), "重庆": (29.5630, 106.5516),
}

DEFAULT_TIMES = {"morning": "07:30", "midday": "12:30", "evening": "22:00"}


def ask(prompt, default=""):
    val = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return val or default


def parse_sender(spec, idx):
    """Format: email|secret|host|port|ssl|role   (secret = auth code or password)"""
    parts = [p.strip() for p in spec.split("|")]
    email, secret = parts[0], parts[1]
    host, port, ssl = parts[2], int(parts[3]), parts[4].lower() == "ssl"
    role = parts[5] if len(parts) > 5 else f"Sender {idx}"
    sender = {
        "id": f"sender-{idx}", "email": email,
        "smtp_host": host, "smtp_port": port, "ssl": ssl,
        "role": role, "enabled": True,
    }
    if "@163.com" in email or "@126.com" in email or "@qq.com" in email:
        sender["auth_code"] = secret
    else:
        sender["password"] = secret
    return sender


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="install directory (default: current dir)")
    ap.add_argument("--city-cn", default="")
    ap.add_argument("--lat", type=float, default=0)
    ap.add_argument("--lon", type=float, default=0)
    ap.add_argument("--recipient", action="append", default=[],
                    help="recipient email, repeatable")
    ap.add_argument("--sender", action="append", default=[],
                    help="email|secret|smtp_host|port|ssl|role, repeatable")
    ap.add_argument("--times", default="",
                    help="comma separated: 07:30,12:30,22:00 (morning,midday,evening)")
    ap.add_argument("--admin-password", default="")
    ap.add_argument("--no-autostart", action="store_true")
    ap.add_argument("--non-interactive", action="store_true")
    args = ap.parse_args()

    target = os.path.abspath(args.dir or ".")
    os.makedirs(target, exist_ok=True)
    config_path = os.path.join(target, "config.json")
    if os.path.exists(config_path) and not args.non_interactive:
        if ask(f"{config_path} 已存在，覆盖吗? (y/N)", "n").lower() != "y":
            sys.exit("aborted")

    cfg = json.load(open(os.path.join(BASE, "config.template.json"),
                         encoding="utf-8"))

    # ---- city ----
    city = args.city_cn
    if not city and not args.non_interactive:
        city = ask("收件人所在城市（如 北京）", "北京")
    city = city or "北京"
    if args.lat and args.lon:
        lat, lon = args.lat, args.lon
    elif city in DEFAULT_CITIES:
        lat, lon = DEFAULT_CITIES[city]
    elif args.non_interactive:
        lat, lon = DEFAULT_CITIES["北京"]
    else:
        lat = float(ask(f"{city} 的纬度（可用 {city} 的坐标）"))
        lon = float(ask(f"{city} 的经度"))
    cfg["settings"].update({"city": city, "city_cn": city,
                            "latitude": lat, "longitude": lon})

    # ---- recipients ----
    recips = args.recipient
    if not recips and not args.non_interactive:
        recips = [ask("收件人邮箱（Gmail 等）")]
    recips = [r for r in recips if r]
    if not recips:
        sys.exit("ERROR: at least one recipient is required")
    cfg["recipients"] = [{"email": r, "name": "", "enabled": True}
                         for r in recips]

    # ---- senders ----
    sender_specs = list(args.sender)
    if not sender_specs and not args.non_interactive:
        n = int(ask("发件邮箱数量（1-3）", "1"))
        for i in range(1, n + 1):
            print(f"-- 第 {i} 个发件邮箱 --")
            email = ask("邮箱地址")
            preset = ask("邮箱类型（163/126/qq/gmail/aliyun-enterprise/自定义=直接回车）", "163").lower()
            host, port, ssl = SMTP_PRESETS.get(preset, ("smtp.163.com", 465, True))
            if preset == "自定义":
                host = ask("SMTP 服务器")
                port = int(ask("端口", "465"))
                ssl = ask("SSL? (y/n)", "y").lower() == "y"
            secret = getpass.getpass("授权码或密码（输入不回显）: ")
            role = ask("显示昵称（如 Morning）", f"Sender {i}")
            sender_specs.append(f"{email}|{secret}|{host}|{port}|{ssl}|{role}")
    sender_specs = [s for s in sender_specs if s]
    if not sender_specs:
        sys.exit("ERROR: at least one sender is required")
    cfg["senders"] = [parse_sender(s, i + 1)
                      for i, s in enumerate(sender_specs)]
    cfg["fallback_sender_id"] = cfg["senders"][0]["id"]

    # ---- send times ----
    times = [t.strip() for t in args.times.split(",")] if args.times else []
    if not times and not args.non_interactive:
        raw = ask("三个发送时间，逗号分隔", "07:30,12:30,22:00")
        times = [t.strip() for t in raw.split(",")]
    times = (times + ["07:30", "12:30", "22:00"])[:3]
    for slot, t in zip(SLOTS, times):
        cfg["slots"][slot]["send_time"] = t
        cfg["slots"][slot]["sender_id"] = cfg["senders"][
            min(SLOTS.index(slot), len(cfg["senders"]) - 1)]["id"]

    # ---- admin password ----
    pw = args.admin_password
    if not pw and not args.non_interactive:
        pw = ask("后台访问密码（回车=随机生成）")
    cfg["admin_password"] = pw or ("greet-" + secrets.token_hex(3))

    # ---- write ----
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # ---- autostart (Windows only) ----
    autostart_note = ""
    if not args.no_autostart and sys.platform == "win32":
        try:
            startup = os.path.join(os.environ["APPDATA"],
                                   "Microsoft", "Windows",
                                   "Start Menu", "Programs", "Startup")
            pythonw = os.path.join(os.path.dirname(sys.executable),
                                   "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = sys.executable
            entries = [
                ("greeting_mail_webui.vbs", "webui.py"),
                ("greeting_mail_daemon.vbs", "auto_daemon.py"),
            ]
            for fname, script in entries:
                vbs = os.path.join(startup, fname)
                with open(vbs, "w", encoding="gbk") as f:
                    f.write(
                        "' auto-generated by daily-greeting-mail setup\n"
                        "Set sh = CreateObject(\"WScript.Shell\")\n"
                        f"sh.CurrentDirectory = \"{target}\"\n"
                        f"sh.Run \"\"\"{pythonw}\"\" \"{os.path.join(target, script)}\"\"\", 0, False\n")
            autostart_note = f"开机自启已注册到: {startup}"
        except Exception as e:
            autostart_note = f"开机自启注册失败（可稍后手动配置）: {e}"
    elif args.no_autostart:
        autostart_note = "按参数要求跳过开机自启注册"

    # ---- done ----
    lan_ip = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("\n===== 安装完成 =====")
    print(f"安装目录    : {target}")
    print(f"配置文件    : {config_path}")
    print(f"后台密码    : {cfg['admin_password']}")
    print(f"收件人      : {', '.join(recips)}")
    print(f"发件邮箱    : {', '.join(s['email'] for s in cfg['senders'])}")
    print(f"发送时间    : {times[0]} / {times[1]} / {times[2]}")
    print(f"本机分享地址: http://{lan_ip}:8765 （局域网内可用）" if lan_ip
          else "分享地址    : 启动 webui.py 后在界面查看")
    print(f"自启动      : {autostart_note}")
    print("\n下一步：")
    print("  1. 立即启动后台:  python webui.py   （然后打开 http://127.0.0.1:8765）")
    print("  2. 测试发送:      python daily_greeting.py --slot morning")
    print("  3. 定时自动发信:  注册每小时巡检（WorkBuddy 自动化）或常驻 auto_daemon.py")


if __name__ == "__main__":
    main()
