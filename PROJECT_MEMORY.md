# TechNexus / 元数智转项目记忆

最后更新：2026-08-26

## 不可变产品约束

- 技术成果首次提交只有一个大文本框，字段名为 `achievement_text`。
- 首次匹配不采集姓名、手机号、单位，也不要求登录。
- 用户选中某条需求并点击“申请对接”后，才采集姓名、手机号和单位，并确认撮合协议。
- 前台不展示需求方身份及联系方式；相关信息只对已登录后台管理员可见。
- 每次匹配最多公开返回 5 条候选需求；低于相关性门槛的需求不展示。

## 唯一生产架构

- 唯一 Git 仓库：`https://github.com/zhuxiaoxingshu-lab/technexus-demo.git`
- 唯一主工作副本：本文件所在的 `TechNexus_deploy_package` 目录。
- 生产主机：阿里云轻量应用服务器，区域 `cn-hongkong`，应用目录 `/opt/technexus`。
- 正式域名：`yuanshuzhuan.cn`、`www.yuanshuzhuan.cn`。
- 唯一线上数据库：`/opt/technexus/technexus_data/technexus.db`（SQLite）。
- GitHub Actions 不再写另一套 `DATABASE_URL` 数据库；生产数据同步由阿里云上的 systemd 定时任务负责。

## 生产同步链路

1. `technexus-sync.timer` 每天触发 `technexus-sync.service`。
2. 同步前先用 SQLite Online Backup API 创建并校验一致性备份。
3. `sync_jstec_demands.py` 至少扫描最近 60 页，补齐新增需求或历史缺口并写入线上 SQLite。
4. `analyze_demands.py --mode local --limit 0` 为所有新增或过期需求生成结构化画像。
5. Web 进程通过数据库版本变化自动重新加载需求，无需维护第二套数据副本。

批量 DeepSeek 画像回填默认关闭，避免无上限 API 成本；需要提升画像质量时再以受控批次手工开启。用户当前优先要求“确认已分解”，本地结构化画像满足该阶段目标。

## 安全与运维基线

- Nginx 强制 HTTPS，证书由 Certbot / Let's Encrypt 续期。
- 请求体上限为 128 KB；AI 接口、普通 API 和后台登录分别限流。
- 应用层再次限制单 IP 的 AI 请求；后台连续失败登录受限。
- 管理员 Cookie 使用 `HttpOnly; SameSite=Strict; Secure`，管理写操作需要 CSRF Token。
- 后台入口不出现在公开导航，直接访问 `/admin`。
- 响应包含 CSP、HSTS、`X-Content-Type-Options`、`X-Frame-Options`、Referrer-Policy、Permissions-Policy。
- 数据库、管理员配置和备份在 Linux 上使用仅属主可读写权限。
- `technexus-backup.timer` 每日生成经 `PRAGMA integrity_check` 验证的 gzip 备份，保留 30 天。
- 新注册域名在注册局 DNS 尚未完全传播时，由 `technexus-certbot-bootstrap.timer` 每 6 小时安全重试首次签发；成功后该引导定时器自动停用，后续由 `certbot-renew.timer` 续期。

## 部署验收清单

- `https://yuanshuzhuan.cn/` 和 `https://www.yuanshuzhuan.cn/` 有效，HTTP 自动跳转 HTTPS。
- 首页和成果提交页只出现技术内容大文本框，不出现联系方式。
- 技术内容少于 20 字被拒绝；正常内容能返回匹配结果。
- “申请对接”页面要求姓名、手机号、单位和协议确认。
- `/admin` 可登录，公开导航没有后台入口；无会话访问后台 API 返回 401。
- 登录失败限流、AI 限流、128 KB 请求体限制、安全响应头均可观察。
- `systemctl list-timers` 能看到备份和需求同步定时器。
- 最新备份可解压，`PRAGMA integrity_check` 返回 `ok`。
- 线上 `demand_analyses` 数量应与 `demands` 数量一致或仅有短暂同步差。

## 保密规则

本文件不得记录 API Key、管理员密码、Cookie、个人联系方式或其他密钥。秘密只存放在服务器 `/etc/technexus/technexus.env` 或权限为 `600` 的配置文件中。

## 2026-08-25 变更记录

- 确认域名实名认证审核通过，DNS 已指向生产 IP。
- 选定 `TechNexus_deploy_package` 为唯一主工作副本，并保留此前线上首页标题优化。
- 将成果提交重构为单技术内容框，联系方式后移至“申请对接”。
- 增加应用层请求体限制、AI 限流、后台登录限流、CSRF、安全 Cookie 和响应安全头。
- 增加 Nginx 限流与安全配置、SQLite 备份脚本、备份定时器和需求同步定时器。
- 停止 GitHub Actions 写入独立数据库，确定阿里云生产 SQLite 为唯一线上数据源。
- 增加首次 HTTPS 签发重试定时器，以处理新注册 `.cn` 域名的跨节点 DNS 传播延迟。

## 2026-08-26 验收状态

- `yuanshuzhuan.cn` 与 `www.yuanshuzhuan.cn` 的 Let's Encrypt 证书已签发，证书有效期至 2026-11-23；HTTP 自动跳转 HTTPS，后续由 `certbot-renew.timer` 续期。
- 需求同步已至少扫描最近 60 页并补齐历史缺口；线上保留 5,174 条需求，其中包含 51 条源站当前列表已移除的历史库存。
- `demand_analyses` 为 5,174 条，全部 `ready`、失败 0；需求与画像一一对应。
- 同步后备份已完成校验和验证、解压恢复及 `PRAGMA integrity_check`，恢复库需求和画像均为 5,174 条。
- 后台真实会话验证通过：Cookie 含 `HttpOnly; SameSite=Strict; Secure`，无 CSRF 返回 403，正确 CSRF 可进入业务校验。

## 2026-08-26 AI 演示匹配数据

- 线上数据库包含 20 组固定 ID 的 `AI演示数据-南通高校科研院所` 匹配记录，覆盖 12 个南通周边高校或校地研究院名称；数据用于后台 UI、搜索、详情和跟进逻辑测试，不代表这些单位真实提交了成果。
- 20 条成果文本由线上已配置的 DeepSeek 一次性结构化生成；20 组记录随后逐条经过现有本地召回与 DeepSeek 精排，AI 精排成功 20 组、本地兜底 0 组。
- 共保存 92 条候选关系和 20 条测试跟进记录，覆盖 11 种跟进状态。为保证部分低相关主题的后台卡片密度，其中 8 条 38–42 分候选仍保留内部 `demo_below_public_threshold` 标记；该标记不在后台页面显示，真实用户仍执行 45 分公开展示门槛。
- 后台可见数据按正常业务形态展示为“高校科研成果库”、专业课题组名称、成果正文和业务跟进记录，不显示 AI 编写、AI 演示、演示补位等提示。内部仍保留固定 `demo_seed_id`，用于与真实线索区分和安全清理。
- 测试记录不含手机号，也没有创建合作意向；联系方式仍只在真实用户点击“申请对接”后采集。
- 幂等生成脚本为 `seed_demo_matches.py`。重复执行会复用同一批 AI 成果并更新固定记录，不会重复增加；需要清理时运行 `python seed_demo_matches.py --delete`，只删除 `nantong-ai-demo-v1-*` 固定 ID 的演示提交、匹配和跟进数据。
- 演示数据写入后的恢复点为 `/opt/technexus/technexus_data/backups/technexus-20260826T000238Z.db.gz`；已实际解压验证 `PRAGMA integrity_check = ok`，其中演示提交、匹配、跟进记录均为 20 条。
