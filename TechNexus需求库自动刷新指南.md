# TechNexus 需求库自动刷新指南

> 历史说明：GitHub Actions + `DATABASE_URL` 的写入链路已停用。生产同步由阿里云 `technexus-sync.timer` 直接写入唯一线上 SQLite，并在同一服务中完成本地需求拆解；当前规则见 `PROJECT_MEMORY.md`。

## 已实现的刷新方式

系统现在支持把 JSTEC 最新技术需求增量同步到数据库。

同步脚本：

`sync_jstec_demands.py`

它会从 JSTEC 技术需求列表第一页开始扫描，发现新需求后写入数据库；当连续遇到一批已存在需求时自动停止，不会每天全量重爬。

## 推荐频率

建议每天自动刷新 1 次。

当前 GitHub Actions 定时设置为：

北京时间每天上午 9:10 左右。

## 手动测试刷新

在本地项目目录执行：

```powershell
cd "C:\Users\xdh\Desktop\工作流\技术需求爬取"
python sync_jstec_demands.py --dry-run --max-pages 2
```

`--dry-run` 表示只扫描，不写入数据库。

如果要写入当前环境数据库：

```powershell
python sync_jstec_demands.py
```

注意：本地没有配置 `DATABASE_URL` 时，会写入本地 SQLite；线上定时任务需要写入 Supabase，因此要配置 GitHub Secret。

## GitHub 自动刷新设置

仓库里已经加入：

`.github/workflows/sync-jstec-demands.yml`

你需要在 GitHub 仓库里添加一个 Secret：

1. 打开 GitHub 仓库：`technexus-demo`
2. 进入 `Settings`
3. 进入 `Secrets and variables`
4. 进入 `Actions`
5. 点击 `New repository secret`
6. 名称填写：

   `DATABASE_URL`

7. 内容填写 Supabase 数据库连接字符串。

添加后，GitHub Actions 会每天自动运行同步脚本。

## 手动触发 GitHub 刷新

1. 打开 GitHub 仓库
2. 点击 `Actions`
3. 选择 `Sync JSTEC Demands`
4. 点击 `Run workflow`

运行完成后，新的需求会进入数据库。

## 平台如何读取新需求

网页和小程序仍使用原来的匹配接口。

后台现在会优先读取数据库中的需求库；如果数据库更新了需求，网页服务会在下一次匹配或查看统计时自动检测并重新加载，通常不需要重新部署。

## 当前注意事项

1. 自动同步不登录 JSTEC，因此不会抓取更完整的隐藏联系方式。
2. 前台本来就不展示需求方联系方式，所以这不影响用户匹配和合作意向提交。
3. 如果 JSTEC 某条需求详情接口报错，脚本会用列表页信息占位并继续，不会因为单条异常中断整个刷新。
4. 如果未来 JSTEC 接口规则变化，脚本日志会显示失败原因，再针对接口调整即可。
