# TechNexus 免费线上部署指南

## 1. 推荐方案

试用版建议使用：

```text
GitHub：存放部署代码
Render Free Web Service：运行网页和后台
Supabase Free PostgreSQL：保存合作意向、匹配记录、后台状态
DeepSeek API：负责 AI 精排
```

不建议只把当前本地版直接放到免费网页服务器上，因为很多免费网页服务的本地文件并不适合保存长期数据。合作意向、手机号、后台跟进记录都应该放到云数据库里。

## 2. 我已经准备好的内容

当前目录已支持线上部署：

```text
render.yaml
.env.example
requirements.txt
.gitignore
technexus_app/app.py
jstec_demands.checkpoint.jsonl
```

程序会自动判断：

```text
本地运行：继续使用 technexus_data/technexus.db
线上运行：如果设置了 DATABASE_URL，就使用 PostgreSQL 云数据库
```

## 3. 你需要提前准备的账号

1. GitHub 账号
2. Render 账号
3. Supabase 账号
4. DeepSeek API Key

DeepSeek API Key 不要写进代码，也不要上传到 GitHub。只在 Render 的环境变量里填写。

## 4. 第一步：把项目放到 GitHub

推荐创建一个私有仓库，例如：

```text
technexus-demo
```

仓库里需要上传这些文件和目录：

```text
technexus_app/
deploy/
requirements.txt
render.yaml
.env.example
.gitignore
scrape_jstec_demands.py
jstec_demands.checkpoint.jsonl
TechNexus免费线上部署指南.md
TechNexus部署版说明.md
TechNexus网页试用版操作指南.md
操作指南.md
```

不要上传：

```text
ai_config.json
admin_config.json
technexus_data/
*.xlsx
*.log
```

如果你愿意，我可以继续帮你把本地目录整理成 Git 提交；但推送到 GitHub 通常需要你登录或授权。

## 5. 第二步：创建 Supabase 免费数据库

进入 Supabase 后：

1. New project
2. 设置项目名称，例如 `technexus`
3. 选择地区。国内访问一般可先选离国内较近的区域，例如新加坡、日本等，具体以账号页面可选区域为准。
4. 等项目创建完成
5. 打开 Project Settings
6. 找到 Database / Connection string
7. 复制 PostgreSQL URI 连接串

连接串大致长这样：

```text
postgresql://postgres.xxxxx:数据库密码@xxxxx.pooler.supabase.com:6543/postgres?sslmode=require
```

注意：如果复制出来的连接串里没有 `sslmode=require`，建议补上：

```text
?sslmode=require
```

这条连接串后面要填到 Render 的：

```text
DATABASE_URL
```

## 6. 第三步：用 Render 发布网页

进入 Render 后：

1. New
2. Blueprint
3. 连接你的 GitHub 仓库
4. Render 会读取仓库里的 `render.yaml`
5. 选择创建服务

创建过程中或创建后，进入 Environment，填写这几个变量：

```text
DATABASE_URL=Supabase 的 PostgreSQL 连接串
TECHNEXUS_AI_API_KEY=你的 DeepSeek API Key
TECHNEXUS_ADMIN_PASSWORD=你自己设置的后台登录密码
```

这些变量已经有默认值，不需要改：

```text
TECHNEXUS_AI_ENABLED=true
TECHNEXUS_AI_BASE_URL=https://api.deepseek.com
TECHNEXUS_AI_MODEL=deepseek-v4-pro
TECHNEXUS_ADMIN_USERNAME=admin
```

保存后点击 Deploy。

## 7. 第四步：上线后检查

Render 部署成功后，会给你一个网址，例如：

```text
https://technexus.onrender.com
```

检查顺序：

1. 打开首页，确认能看到 TechNexus 页面
2. 随便输入一个技术成果摘要，测试是否能返回匹配结果
3. 点“我想合作”，提交一条测试线索
4. 打开后台登录区，使用：

```text
账号：admin
密码：你在 TECHNEXUS_ADMIN_PASSWORD 设置的密码
```

5. 后台能看到测试线索，说明数据库、AI 和后台都跑通了

## 8. 免费方案的限制

免费部署适合一周试用版和小范围内测，但有几个限制：

1. Render 免费服务可能会休眠，第一次打开可能慢几十秒。
2. 免费数据库有容量和用量限制。
3. 免费域名通常是平台二级域名，正式对外建议后续绑定自己的域名。
4. 正式运营前，建议再做短信验证码、隐私政策、协议弹窗、数据备份和访问日志。

## 9. 遇到问题时看哪里

Render 部署失败：

```text
Render Dashboard -> 服务 -> Logs
```

数据库连接失败：

```text
检查 DATABASE_URL 是否复制完整
检查数据库密码是否替换正确
检查连接串是否带 sslmode=require
```

AI 不工作：

```text
检查 TECHNEXUS_AI_API_KEY
检查 DeepSeek 账户余额或额度
检查 TECHNEXUS_AI_MODEL 是否为 deepseek-v4-pro
```

后台登录失败：

```text
检查 TECHNEXUS_ADMIN_USERNAME
检查 TECHNEXUS_ADMIN_PASSWORD
修改环境变量后重新 Deploy
```
