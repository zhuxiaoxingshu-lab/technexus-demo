# TechNexus 技术经理人部署版说明

> 历史说明：本文保留 Render / PostgreSQL 旧方案供参考，不再代表生产架构。当前唯一生产环境为阿里云，唯一线上数据库为 `/opt/technexus/technexus_data/technexus.db`，以 `PROJECT_MEMORY.md` 为准。

## 1. 部署版目标

这份目录已经整理为可部署版本：本地继续能运行，后续也可以复制到云服务器，作为网页内测版使用。

当前服务入口：

```text
technexus_app/app.py
```

如果要部署到免费线上环境，优先阅读：

```text
TechNexus免费线上部署指南.md
```

推荐组合：

```text
Render Free Web Service + Supabase Free PostgreSQL
```

程序已支持两种数据库模式：

```text
本地：未设置 DATABASE_URL 时，使用 technexus_data/technexus.db
线上：设置 DATABASE_URL 后，使用 PostgreSQL 云数据库
```

本地访问：

```text
http://127.0.0.1:8010/
```

服务器部署后建议通过 Nginx 反向代理成正式域名，例如：

```text
https://technexus.example.com/
```

## 2. 建议复制到服务器的文件

部署时建议复制这些文件和目录：

```text
technexus_app/
deploy/
requirements.txt
render.yaml
.env.example
.gitignore
scrape_jstec_demands.py
jstec_demands.checkpoint.jsonl
ai_config.example.json
admin_config.example.json
TechNexus免费线上部署指南.md
TechNexus网页试用版操作指南.md
TechNexus部署版说明.md
```

如果服务器上也要直接使用当前已抓取的需求库，需要复制：

```text
jstec_demands.checkpoint.jsonl
```

如果你希望把当前本地后台线索一起迁移到服务器，需要复制：

```text
technexus_data/technexus.db
```

如果只是新开一个线上内测库，可以不复制 `technexus_data/technexus.db`，程序会自动创建新数据库。

## 3. 不要提交或公开的文件

这些文件包含密钥、密码、运行数据或本地输出，不要提交到代码仓库，也不要发给外部人员：

```text
ai_config.json
admin_config.json
technexus_data/technexus.db
technexus_data/*.log
technexus_data/server.pid
*.xlsx
*.skipped.log
```

`.gitignore` 已经把这些常见文件排除。

## 4. 服务器首次部署步骤

以下以 Linux 服务器路径 `/opt/technexus` 为例。

### 4.1 安装 Python

建议 Python 版本：

```text
Python 3.11 或以上
```

### 4.2 复制项目

把部署文件复制到：

```text
/opt/technexus
```

### 4.3 创建 DeepSeek 配置

复制模板：

```bash
cp ai_config.example.json ai_config.json
```

编辑 `ai_config.json`，填入服务器使用的 DeepSeek API Key。

### 4.4 创建管理员密码

推荐直接运行：

```bash
python3 technexus_app/set_admin_password.py
```

按提示设置管理员账号和密码。

如果没有提前设置，服务首次启动时会自动生成随机管理员密码，并写入：

```text
technexus_data/initial_admin_password.txt
```

登录后请尽快运行 `set_admin_password.py` 修改密码。

### 4.5 启动服务

首次启动可执行：

```bash
chmod +x deploy/start_linux.sh
./deploy/start_linux.sh
```

默认监听：

```text
127.0.0.1:8010
```

如果需要临时改端口：

```bash
TECHNEXUS_PORT=8020 ./deploy/start_linux.sh
```

## 5. systemd 服务示例

模板文件：

```text
deploy/technexus.service.example
```

复制到：

```bash
sudo cp deploy/technexus.service.example /etc/systemd/system/technexus.service
```

按服务器实际路径和用户修改后，执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable technexus
sudo systemctl start technexus
sudo systemctl status technexus
```

## 6. Nginx 反向代理示例

模板文件：

```text
deploy/nginx_technexus.conf.example
```

复制到 Nginx 站点配置目录后，把：

```text
technexus.example.com
```

替换成你的真实域名。

完成后检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS 证书建议后续用 Let's Encrypt / certbot 配置。

## 7. 部署后检查

访问：

```text
http://服务器IP/
```

或你的正式域名。

检查项目：

1. 首页能打开
2. 技术成果能提交并匹配
3. 合作意向能提交
4. 后台需要登录才能进入
5. 后台能查看线索详情
6. 状态流转能保存
7. Excel 能导出

## 8. 当前阶段建议

这一版适合做小范围网页内测。等 3-5 个真实用户试填后，再决定是否继续做：

- 数据备份
- 线上 HTTPS
- 小程序端
- 需求方入驻
- 更强的 AI 匹配解释和人工复核流程
