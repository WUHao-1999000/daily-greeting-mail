# Daily Greeting Mail

每天自动给指定的人发一封带着当天实时天气的问候邮件 —— 早安 / 午安 / 晚安三档，各自独立的时间、发件邮箱和文风，配一个可视化网页后台来管理。

## 特性

- **三档独立**：早安 / 午安 / 晚安各有独立发送时间、独立发件邮箱、独立文风
- **真实天气**：抓取 Open-Meteo 实时数据，把温度、体感、湿度、日出日落、明日温差写进邮件正文
- **句子轮换**：句子池按日期轮换组合，同一天不重复，多天不千篇一律
- **网页后台**：默认 `http://127.0.0.1:8765`，可改收件人、发件邮箱、发送时间、文案，支持预览、手动发送、查看日志，带密码保护，可局域网分享
- **失败回退**：某个邮箱发信失败自动换备用邮箱重试；日志去重保证每档每天只发一次
- **开机自启**：可注册 Windows 开机自启，重启不失效

## 快速开始

### 1. 准备凭据

发件邮箱需要 SMTP 授权码（**不是登录密码**）：

| 邮箱 | 获取方式 |
|---|---|
| 163 / 126 / QQ | 网页版「设置 → POP3/SMTP/IMAP」开启 SMTP 服务并生成授权码 |
| Gmail | Google 账号 → 安全性 → 应用专用密码（App Password） |
| 阿里企业邮 | 直接用登录密码 |
| Outlook 个人邮箱 | SMTP 基础认证已被微软禁用，建议换邮箱 |

### 2. 一键安装

把 `scripts/` 复制到你的安装目录（例如 `<workspace>/greeting-mail/`），在该目录下运行：

```bash
python setup.py --dir "C:/path/to/greeting-mail" \
  --city-cn 北京 --lat 39.9042 --lon 116.4074 \
  --recipient user@example.com \
  --sender "a@163.com|授权码|smtp.163.com|465|ssl|Morning" \
  --sender "b@163.com|授权码|smtp.163.com|465|ssl|Midday" \
  --times "07:30,12:30,22:00" \
  --admin-password 你的后台密码
```

`--sender` 格式为 `邮箱|授权码或密码|SMTP服务器|端口|ssl或tls|显示昵称`，最多可重复 3 次。
测试时可加 `--no-autostart --non-interactive` 跳过交互与自启注册。

### 3. 验证

```bash
python daily_greeting.py --slot morning --dry-run   # 只渲染预览，不登录不发信
python daily_greeting.py --slot morning             # 真实发送一封
```

### 4. 让它每天自动跑

二选一，或都用：

- **守护进程**：`setup.py` 已注册 `auto_daemon.py` 开机自启，每 10 分钟检查一次是否到发送时间，不依赖其他工具运行
- **定时任务**：每小时执行一次 `python daily_greeting.py --auto`，脚本自行判断是否到达发送时间

两者并存是安全的 —— 日志去重保证同一档位同一天只发一次。

### 5. 打开网页后台

```bash
python webui.py    # 端口 8765 被占用会自动退出
```

访问 `http://127.0.0.1:8765`，用 `--admin-password` 设的密码登录。保存即生效，自动备份为 `config.backup.json`。

## 目录结构

```
scripts/
├── daily_greeting.py       # 核心流水线：取天气 → 渲染 → 发送
├── webui.py                # 网页后台后端（含密码登录、局域网分享）
├── webui.html              # 网页后台前端
├── auto_daemon.py          # 开机守护进程
├── setup.py                # 一键安装：生成 config.json + 注册自启
└── config.template.json    # 配置模板（所有凭据为空）
```

## 运维备忘

- 改授权码 / 密码：直接在网页后台改，或改 `config.json`，无需重启进程
- 发信失败（如 535 认证失败）：多为授权码失效，重新生成后更新即可，脚本会自动用备用邮箱顶上
- 排查问题看 `logs/greeting.log`
- 换城市：改 `config.json` 里 settings 的 `city` / `city_cn` / `latitude` / `longitude`
- 换语言：把 slots 内句子池整体替换为目标语言，占位符照用

## 安全

本仓库不包含任何真实邮箱地址、授权码、密码或 IP。所有凭据只写入你自己安装目录下的 `config.json`，且必须由你本人填写 —— 该文件已被 `.gitignore` 排除，不会被提交。

## 许可

MIT
