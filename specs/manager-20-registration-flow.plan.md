# 技术经理人 20 人注册与全流程测试计划

## Application Overview

技术经理人中心支持免费注册、后台人工认证、认证后免费提交企业技术需求，并由后台查看经理人、项目和对接进展。本轮测试使用独立本地数据库，不写入线上环境。

## Test Scenarios

### 1. 批量注册与约束

**Seed:** `tests/manager_20_seed.spec.ts`

#### 1.1. register-twenty-unique-managers

**File:** `tests/manager-20/register-twenty-unique-managers.spec.ts`

**Steps:**
  1. 打开技术经理人页面，以 20 组不同姓名、手机号、机构、认证说明和密码提交注册。
    - expect: 20 次注册均返回成功。
    - expect: 后台技术经理人总数为 20，且手机号不重复。
  2. 用已注册手机号再次提交。
    - expect: 系统拒绝重复注册并给出明确提示。
  3. 提交错误手机号和不足 8 位密码。
    - expect: 系统拒绝无效输入，不产生脏数据。

### 2. 后台认证

**Seed:** `tests/manager_20_seed.spec.ts`

#### 2.1. approve-all-manager-applications

**File:** `tests/manager-20/approve-all-manager-applications.spec.ts`

**Steps:**
  1. 管理员登录后台并查看技术经理人列表。
    - expect: 列表显示 20 条待认证申请及姓名、手机号、机构和申请时间。
  2. 逐一完成认证。
    - expect: 20 名经理人状态均更新为“已认证”。

### 3. 认证后需求提交

**Seed:** `tests/manager_20_seed.spec.ts`

#### 3.1. submit-one-demand-per-manager

**File:** `tests/manager-20/submit-one-demand-per-manager.spec.ts`

**Steps:**
  1. 20 名已认证经理人分别登录并提交一条企业技术需求，交替选择委托平台和自主对接。
    - expect: 共生成 20 个项目编号。
    - expect: 10 个委托项目服务费状态为“不适用”，10 个自主项目为“免费阶段”。
    - expect: 未登记技术对接方时不展示候选技术或虚假联系人。
  2. 重复提交同一经理人的同一需求。
    - expect: 系统拒绝重复需求。

### 4. 后台数据和浏览器可用性

**Seed:** `tests/manager_20_seed.spec.ts`

#### 4.1. review-admin-data-and-browser-health

**File:** `tests/manager-20/review-admin-data-and-browser-health.spec.ts`

**Steps:**
  1. 在浏览器中查看后台技术经理人和经理人项目页面。
    - expect: 20 名经理人和 20 个项目可见，表格不溢出或错位。
    - expect: 页面没有 JavaScript error 级控制台错误。
    - expect: 页面不出现“免费查看候选”“技术成果候选”等与当前能力不符的文案。
  2. 保存后台列表、项目列表和代表性经理人工作台截图。
    - expect: 截图状态完整、稳定且可用于人工复核。
