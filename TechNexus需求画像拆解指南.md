# TechNexus 技术需求画像拆解指南

平台会把需求正文预先拆成“技术标的、核心问题、所需功能、技术路线、量化指标、限制条件、应用对象、交付物、成熟度和原文证据”，并存入 `demand_analyses` 表。匹配时优先读取这些画像，再召回候选需求并交给 DeepSeek 复核。

## 自动运行

`.github/workflows/sync-jstec-demands.yml` 每天同步新需求后，会继续拆解尚未分析、正文发生变化或解析版本已经过期的需求。

需要在 GitHub 仓库中配置以下 Actions Secret：

- `DATABASE_URL`：Render PostgreSQL 数据库连接地址。
- `TECHNEXUS_AI_API_KEY`：DeepSeek API Key。Render 环境变量不会自动同步到 GitHub。

未配置 DeepSeek Key 时，每日需求同步仍会继续，只跳过 AI 画像拆解。

## 首次回填

进入 GitHub 仓库的 Actions，手动运行 `Sync JSTEC Demands`。`analysis_limit` 建议先填写 `100` 进行抽检；确认结果后可分批填写 `300` 至 `500`，直到线上统计中的 `demand_ai_profile_count` 接近需求总数。

## 本地命令

只查看待处理数量，不写数据库、也不调用 API：

```powershell
python analyze_demands.py --dry-run --mode local --limit 100
```

先用本地规则生成画像：

```powershell
python analyze_demands.py --mode local --limit 100
```

使用 DeepSeek 增强并持久化：

```powershell
python analyze_demands.py --mode ai --require-ai --limit 100 --batch-size 4
```

脚本通过需求正文指纹和解析版本判断是否需要重复处理，任务中断后可以直接重新运行。
