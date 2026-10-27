# daily-greeting-mail

搭建每日定时问候邮件系统：从用户配置的发件邮箱（163/126/QQ/Gmail/阿里企业邮等），在设定的早/午/晚时间自动向收件人发送包含当天实时天气的英文（或自定语言）问候邮件，三种风格差异化，带可视化网页后台、密码保护、局域网分享、开机自启与发送失败自动换邮箱回退。当用户想要"每天定时发问候邮件 / 天气问候邮件 / 早安午安晚安邮件系统"或要求安装、配置、修改本系统时使用。本 skill 不含任何预置凭据，所有邮箱、授权码由用户安装时填写。

## 这是什么

这是一个 WorkBuddy Skill（位于 `~/.workbuddy/skills/daily-greeting-mail/`），本仓库为它的发布副本。核心定义为 [SKILL.md](SKILL.md)。

## 文件结构

```
scripts/auto_daemon.py
scripts/config.template.json
scripts/daily_greeting.py
scripts/setup.py
scripts/webui.html
scripts/webui.py
SKILL.md
```

## 安装

把本仓库内容复制到 `~/.workbuddy/skills/daily-greeting-mail/` 即可。

---

*由 Skill 发布台自动生成 · 2026-10-27*