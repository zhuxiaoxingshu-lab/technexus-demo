# Production Online Audit Test Plan

## Application Overview

`https://yuanshuzhuan.cn` 是“元数智转”技术成果与产业需求匹配平台。审计覆盖匿名成果提交与 AI 匹配、合作意向、进度查询、技术经理人注册认证、两种对接模式、后台审核结算，以及生产环境的 HTTPS、安全头、会话、限流配置、响应式和可访问性风险。

## Test Scenarios

### 1. Public visitor journey

**Seed:** `https://yuanshuzhuan.cn/`

#### 1.1. browse-public-surfaces

**Steps:**
1. 打开工作台、需求大厅、成果提交、匹配结果、申请对接和进度查询。
   - expect: 每个入口可达，页面没有加载中断、空白或控制台错误。
   - expect: 首次成果提交只有一个技术内容大文本框，不提前索取联系方式。
2. 检查桌面与手机宽度。
   - expect: 导航、表单、卡片和表格不出现不可用的横向截断。

#### 1.2. submit-match-intent-and-query

**Steps:**
1. 提交带线上审计标识的技术成果描述。
   - expect: 返回最多 5 条候选并显示评分与匹配依据。
2. 选择一条结果进入申请对接。
   - expect: 仅在此阶段采集姓名、手机号和单位，并要求确认协议。
3. 提交测试合作意向并保存查询码。
   - expect: 进度查询可用该查询码返回当前状态。

### 2. Technical manager journey

**Seed:** `https://yuanshuzhuan.cn/manager`

#### 2.1. register-and-submit-both-modes

**Steps:**
1. 使用两个唯一测试手机号注册两名技术经理人。
   - expect: 注册免费，初始状态为待认证。
2. 后台分别认证两个账号。
   - expect: 认证后可免费提交企业需求。
3. 分别选择委托平台和自主对接提交需求。
   - expect: 项目服务方式、状态和费用状态正确；不展示不存在的成果候选。

#### 2.2. close-entrusted-and-self-service

**Steps:**
1. 后台推进委托平台项目并登记平台对接方、成交与分成。
   - expect: 对接方来源显示平台登记，成交后才结算分成。
2. 经理人自主登记技术对接方，后台推进服务费与成交。
   - expect: 来源显示经理人自主登记，实质对接后才确认少量平台服务费。

### 3. Administration and operations

**Seed:** `https://yuanshuzhuan.cn/admin`

#### 3.1. admin-review-and-data-consistency

**Steps:**
1. 管理员登录并检查需求、匹配、合作意向、经理人和项目。
   - expect: 桌面与窄屏均能读取表格；敏感联系方式只在已授权后台出现。
2. 对照线上 SQLite 核验测试记录、日志、结算与最终状态。
   - expect: 前台、经理人端、后台与数据库一致。

### 4. Security, reliability and observability

**Seed:** `https://yuanshuzhuan.cn/`

#### 4.1. production-baseline

**Steps:**
1. 检查 HTTP 跳转、TLS 证书、安全响应头和 Cookie 属性。
   - expect: HTTP 强制跳转 HTTPS；HSTS、CSP、X-Frame-Options、X-Content-Type-Options、Referrer-Policy 和 Permissions-Policy 存在。
2. 检查未登录后台 API 和缺失 CSRF 的写请求。
   - expect: 分别返回 401 和 403。
3. 检查备份、数据库完整性、systemd 服务、同步与备份定时器。
   - expect: 服务正常、备份可验证、数据库 `integrity_check=ok`。
4. 检查限流配置与请求体上限的配置生效路径。
   - expect: Nginx 与应用层均有约束；不对生产环境做破坏性压力测试。

## Demo Video Plan

1. `01-public-overview-and-demand-hall.webm`：工作台与需求大厅。
2. `02-achievement-match-and-intent.webm`：成果提交、AI 匹配、申请对接。
3. `03-progress-query.webm`：查询码与进度查询。
4. `04-manager-registration-and-submission.webm`：经理人注册、认证后提交两种需求。
5. `05-entrusted-platform-workflow.webm`：委托平台审核、对接、成交与分成。
6. `06-self-service-workflow.webm`：自主登记对接方、服务费确认与结算。
7. `07-admin-operations.webm`：后台认证、项目维护、合作意向与结算总览。

所有生产测试数据使用唯一 QA 标识；截图和视频验收完成后，按精确 ID 清理本轮测试数据，不触碰已有业务记录。
