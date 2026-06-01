# TechNexus 部署包清单

## 必须文件

```text
technexus_app/
requirements.txt
render.yaml
.env.example
.gitignore
jstec_demands.checkpoint.jsonl
ai_config.example.json
admin_config.example.json
TechNexus免费线上部署指南.md
TechNexus部署版说明.md
```

## 推荐一并带上

```text
deploy/
scrape_jstec_demands.py
TechNexus网页试用版操作指南.md
操作指南.md
```

## 免费线上部署推荐

```text
Render Free Web Service + Supabase Free PostgreSQL
```

部署时把这些配置放到 Render 的环境变量，不要写进代码：

```text
DATABASE_URL
TECHNEXUS_AI_API_KEY
TECHNEXUS_ADMIN_PASSWORD
```

## 服务器上需要单独创建

```text
ai_config.json
admin_config.json
technexus_data/
```

说明：

- `ai_config.json` 从 `ai_config.example.json` 复制后填写 DeepSeek API Key。
- `admin_config.json` 通过 `python technexus_app/set_admin_password.py` 生成。
- `technexus_data/` 会由程序自动创建。
- 免费线上部署时通常不需要创建 `ai_config.json` 和 `admin_config.json`，直接使用环境变量即可。

## 不建议放入部署包

```text
ai_config.json
admin_config.json
technexus_data/technexus.db
technexus_data/initial_admin_password.txt
technexus_data/*.log
technexus_data/server.pid
*.xlsx
*_预览.png
sample_*
test_*
```

如果需要迁移本地后台线索，再单独复制：

```text
technexus_data/technexus.db
```

并且复制前先停止本地服务，避免数据库正在写入。
