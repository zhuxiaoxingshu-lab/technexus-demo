$ErrorActionPreference = "Stop"

$runId = [Guid]::NewGuid().ToString("N")
$tempRoot = (Resolve-Path "../.codex_tmp").Path
$testDb = Join-Path $tempRoot "manager-p0-$runId.db"
$testAdmin = Join-Path $tempRoot "manager-p0-admin-$runId.json"
$stdout = Join-Path $tempRoot "manager-p0-$runId.out.log"
$stderr = Join-Path $tempRoot "manager-p0-$runId.err.log"
$testAdminPassword = "P0-Admin-Local-2026"
$testManagerPassword = "P0-Manager-Local-2026"

$oldDb = $env:TECHNEXUS_DB_FILE
$oldConfig = $env:TECHNEXUS_ADMIN_CONFIG_FILE
$oldUser = $env:TECHNEXUS_ADMIN_USERNAME
$oldPassword = $env:TECHNEXUS_ADMIN_PASSWORD
$env:TECHNEXUS_DB_FILE = $testDb
$env:TECHNEXUS_ADMIN_CONFIG_FILE = $testAdmin
$env:TECHNEXUS_ADMIN_USERNAME = "p0-admin"
$env:TECHNEXUS_ADMIN_PASSWORD = $testAdminPassword

$process = Start-Process python `
    -ArgumentList @("technexus_app/app.py", "--host", "127.0.0.1", "--port", "8022", "--no-browser") `
    -WorkingDirectory (Get-Location).Path `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

$env:TECHNEXUS_DB_FILE = $oldDb
$env:TECHNEXUS_ADMIN_CONFIG_FILE = $oldConfig
$env:TECHNEXUS_ADMIN_USERNAME = $oldUser
$env:TECHNEXUS_ADMIN_PASSWORD = $oldPassword

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod "http://127.0.0.1:8022/api/stats" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    if (-not $ready) {
        throw "Local server did not become ready."
    }

    $registerBody = @{
        real_name = "周经理"
        phone = "13900005678"
        organization = "南通技术转移服务中心"
        credential_no = "NT-TM-P0-001"
        password = $testManagerPassword
    } | ConvertTo-Json
    $registered = Invoke-RestMethod "http://127.0.0.1:8022/api/manager/register" `
        -Method Post -ContentType "application/json" -Body $registerBody -SessionVariable managerSession

    $adminBody = @{ username = "p0-admin"; password = $testAdminPassword } | ConvertTo-Json
    $adminLogin = Invoke-RestMethod "http://127.0.0.1:8022/api/admin/login" `
        -Method Post -ContentType "application/json" -Body $adminBody -SessionVariable adminSession
    $adminHeaders = @{ "X-CSRF-Token" = $adminLogin.csrf_token }

    $verifyBody = @{
        manager_id = $registered.manager.manager_id
        verification_status = "已认证"
        verification_note = "P0 端到端测试认证"
    } | ConvertTo-Json
    Invoke-RestMethod "http://127.0.0.1:8022/api/admin/managers/verify" `
        -Method Post -ContentType "application/json" -Headers $adminHeaders `
        -Body $verifyBody -WebSession $adminSession | Out-Null

    $managerSessionInfo = Invoke-RestMethod "http://127.0.0.1:8022/api/manager/session" -WebSession $managerSession
    $managerHeaders = @{ "X-CSRF-Token" = $managerSessionInfo.csrf_token }
    $projectBody = @{
        service_mode = "self_service"
        enterprise_demand_text = "南通某精密制造企业希望寻找面向高速产线的机器视觉缺陷检测技术，要求实现微小划痕与尺寸偏差在线识别，支持边缘计算部署、质量数据追溯和现场联合验证。"
    } | ConvertTo-Json
    $created = Invoke-RestMethod "http://127.0.0.1:8022/api/manager/projects" `
        -Method Post -ContentType "application/json" -Headers $managerHeaders `
        -Body $projectBody -WebSession $managerSession
    $projectId = $created.project.project_id

    $lockedUpdate = @{
        project_id = $projectId
        status = "已建立技术对接"
        service_fee_status = "待支付"
        contact_unlock_status = "未解锁"
        audit_note = "需求完整，已受理"
        match_summary = "已筛选到一项机器视觉检测成果"
        counterpart_contact = @{
            name = "李老师"
            phone = "13811112222"
            organization = "南通高校智能制造团队"
            email = "li@example.cn"
        }
    } | ConvertTo-Json -Depth 4
    Invoke-RestMethod "http://127.0.0.1:8022/api/admin/manager-projects/update" `
        -Method Post -ContentType "application/json" -Headers $adminHeaders `
        -Body $lockedUpdate -WebSession $adminSession | Out-Null

    $lockedWorkbench = Invoke-RestMethod "http://127.0.0.1:8022/api/manager/workbench" -WebSession $managerSession
    $maskedBeforeUnlock = $lockedWorkbench.projects[0].counterpart_contact.phone -ne "13811112222"

    $unlockUpdate = @{
        project_id = $projectId
        status = "对接中"
        service_fee_status = "已支付"
        contact_unlock_status = "已解锁"
        audit_note = "服务费已确认"
        match_summary = "技术对接资源已确认，可以进入联系阶段"
        counterpart_contact = @{
            name = "李老师"
            phone = "13811112222"
            organization = "南通高校智能制造团队"
            email = "li@example.cn"
        }
    } | ConvertTo-Json -Depth 4
    Invoke-RestMethod "http://127.0.0.1:8022/api/admin/manager-projects/update" `
        -Method Post -ContentType "application/json" -Headers $adminHeaders `
        -Body $unlockUpdate -WebSession $adminSession | Out-Null

    $settlementBody = @{
        project_id = $projectId
        settlement_type = "自主对接服务费"
        deal_amount = "0"
        platform_fee = "399"
        manager_share = "0"
        status = "已结算"
        note = "P0 本地测试"
    } | ConvertTo-Json
    $settlement = Invoke-RestMethod "http://127.0.0.1:8022/api/admin/manager-settlements/save" `
        -Method Post -ContentType "application/json" -Headers $adminHeaders `
        -Body $settlementBody -WebSession $adminSession
    $unlockedWorkbench = Invoke-RestMethod "http://127.0.0.1:8022/api/manager/workbench" -WebSession $managerSession

    [pscustomobject]@{
        registered = $registered.ok
        verified = $managerSessionInfo.manager.verification_status
        project_no = $created.project.project_no
        masked_before_unlock = $maskedBeforeUnlock
        phone_after_unlock = $unlockedWorkbench.projects[0].counterpart_contact.phone
        service_fee = $settlement.settlement.platform_fee
        settlement_status = $settlement.settlement.status
        test_database = $testDb
    } | ConvertTo-Json
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
