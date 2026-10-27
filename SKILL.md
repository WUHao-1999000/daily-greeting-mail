---
name: daily-greeting-mail
description: 搭建每日定时问候邮件系统：从用户配置的发件邮箱（163/126/QQ/Gmail/阿里企业邮等），在设定的早/午/晚时间自动向收件人发送包含当天实时天气的英文（或自定语言）问候邮件，三种风格差异化，带可视化网页后台、密码保护、局域网分享、开机自启与发送失败自动换邮箱回退。当用户想要"每天定时发问候邮件 / 天气问候邮件 / 早安午安晚安邮件系统"或要求安装、配置、修改本系统时使用。本 skill 不含任何预置凭据，所有邮箱、授权码由用户安装时填写。
agent_created: true
---

# Daily Greeting Mail — 每日问候邮件系统

一套开箱即用的定时问候邮件系统：

- 每天最多三档（早安 / 午安 / 晚安），每档独立时间、独立发件邮箱、独立文风
- 自动抓取 Open-Meteo 实时天气，把温度、体感、湿度、日出日落、明日温差填入邮件
- 句子池按日期轮换组合，同一天不重复、多天不千篇一律
- 本地网页后台（默认 http://127.0.0.1:8765）：改收件人 / 发件邮箱 / 发送时间 / 文案，预览、手动发送、看日志，密码保护，可局域网分享
- 发送失败自动换备用邮箱重试；日志去重保证每档每天只发一次
- 可注册 Windows 开机自启，重启不失效

## 目录结构

```
scripts/
├── daily_greeting.py       # 核心流水线：取天气 → 渲染 → 发送（支持 --auto / --dry-run）
├── webui.py                # 网页后台后端（含密码登录、局域网分享）
├── webui.html              # 网页后台前端
├── auto_daemon.py          # 开机守护进程：每 10 分钟检查是否到发送时间
├── setup.py                # 一键安装：生成 config.json + 注册开机自启
└── config.template.json    # 配置模板（所有凭据为空）
```

安全约定：本 skill 的任何文件都不得包含真实邮箱地址、授权码、密码或 IP。所有凭据只写入用户安装目录下的 config.json，且必须由用户提供。绝不把用户的凭据写入 skill 目录、自动化记录或任何交付文件。

## 安装流程（按顺序执行）

### 1. 收集信息

向用户收集以下内容（一次问清，避免反复追问）：

- 收件人所在城市（用于天气与坐标）
- 收件人邮箱（可多个）
- 发件邮箱 1~3 个，每个需要：邮箱地址 + **授权码或密码**。注意：
  - 163 / 126 / QQ 邮箱：需要用户在邮箱网页版「设置 → POP3/SMTP/IMAP」开启 SMTP 服务并生成**授权码**（登录密码不可用）
  - Gmail：需要应用专用密码（App Password）
  - 阿里企业邮：直接用登录密码；Outlook 个人邮箱的 SMTP 基础认证已被微软禁用，一般不可用，建议换邮箱
- 三个发送时间（默认 07:30 / 12:30 / 22:00）
- 后台访问密码（可随机生成）

### 2. 一键安装

把 `scripts/` 整个目录复制到用户指定的安装目录（建议是用户工作区下的独立文件夹，例如 `<workspace>/greeting-mail/`），然后在**该副本目录**运行：

```bash
python setup.py --dir "C:/path/to/greeting-mail" \
  --city-cn 北京 --lat 39.9042 --lon 116.4074 \
  --recipient user@gmail.com \
  --sender "a@163.com|授权码|smtp.163.com|465|ssl|Morning" \
  --sender "b@163.com|授权码|smtp.163.com|465|ssl|Midday" \
  --times "07:30,12:30,22:00" \
  --admin-password 用户密码
```

`--sender` 格式为 `邮箱|授权码或密码|SMTP服务器|端口|ssl或tls|显示昵称`，可重复多次（最多 3 个）。测试时可加 `--no-autostart --non-interactive` 跳过交互与自启注册。setup.py 会自动：生成 config.json、按城市填坐标（内置主要城市）、把第一个发件箱设为备用、把开机自启写入 Windows 启动文件夹。

### 3. 验证

```bash
cd "C:/path/to/greeting-mail"
python daily_greeting.py --slot morning --dry-run   # 预览渲染，不登录不发信
python daily_greeting.py --slot morning             # 真实发送一封
```

真实发送成功后让用户去收件箱确认（163/126 → Gmail 邮件可能进垃圾箱，提醒用户标记"非垃圾邮件"）。

### 4. 定时自动发信（二选一或都用）

- **WorkBuddy 自动化（推荐）**：创建每小时巡检任务（rrule: `FREQ=HOURLY;BYMINUTE=5;INTERVAL=1`），prompt 为"运行 `python "C:/path/to/greeting-mail/daily_greeting.py" --auto` 并报告输出；脚本自行判断是否到达 config.json 中的发送时间，日志去重不会重复发送"。
- **Windows 守护进程**：setup.py 已注册 auto_daemon.py 开机自启（每 10 分钟检查一次），不依赖 WorkBuddy 运行。

两者并存安全：日志去重保证同一档位同一天只发一次。

### 5. 启动网页后台

```bash
python webui.py    # 后台运行；端口 8765 被占用会自动退出
```

打开 http://127.0.0.1:8765 ，用 admin_password 登录。界面可改一切配置（收件人、发件邮箱凭据、发送时间、句子池文案、密码、局域网分享开关），保存即生效（自动备份 config.backup.json）。局域网分享：config 的 listen 保持 `0.0.0.0`，界面"访问与分享"区会显示分享地址；首次访问如 Windows 防火墙弹窗需点允许。

## 日常运维要点

- 用户改授权码/密码：直接在网页后台改，或改 config.json；无需重启进程（每次发送都重新读配置和登录）
- 某邮箱发信失败（如 535 认证失败）：多为授权码被重置失效，引导用户重新生成并在后台更新；脚本会先用备用邮箱顶上
- 排查问题看 `logs/greeting.log`（含每次发送与回退记录）
- 城市变更：改 config.json settings 的 city/city_cn/latitude/longitude 四项
- 中英文切换：把 slots 内句子池整体替换为目标语言即可，占位符照用
