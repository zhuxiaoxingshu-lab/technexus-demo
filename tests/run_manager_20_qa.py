from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


NAMES = [f"测试经理人{i:02d}" for i in range(1, 21)]
ORGANIZATIONS = [
    "南通大学技术转移中心（测试）",
    "南通理工学院科技合作处（测试）",
    "江苏航运职业技术学院产学研办公室（测试）",
    "南通职业大学技术服务中心（测试）",
    "南通科技职业学院科技处（测试）",
    "江苏工程职业技术学院校企合作处（测试）",
    "南通先进通信技术研究院（测试）",
    "南通智能感知研究院（测试）",
    "南通新材料产业技术研究院（测试）",
    "如皋科技成果转化服务中心（测试）",
]
DEMAND_TOPICS = [
    "高速纺织产线机器视觉瑕疵检测与边缘部署",
    "船舶钢结构耐腐蚀涂层与盐雾寿命提升",
    "锂电池极片缺陷在线检测及质量数据追溯",
    "化工园区挥发性有机物低成本在线监测",
    "数控加工刀具磨损预测与设备健康管理",
    "水产养殖水质多参数传感和智能预警",
    "家纺面料小批量柔性排产与能耗优化",
    "港口散货堆场无人巡检及安全风险识别",
    "工业废水难降解有机物深度处理工艺",
    "新能源汽车连接器可靠性自动测试装备",
    "食品包装密封缺陷无损检测技术",
    "风电叶片表面损伤无人机巡检算法",
    "精密零部件尺寸偏差在线测量系统",
    "建筑保温材料阻燃性能与低烟配方优化",
    "冷链仓储温湿度异常预测和节能控制",
    "生物发酵过程关键参数软测量技术",
    "光伏组件隐裂快速检测与分级方案",
    "农业废弃物资源化制备功能材料工艺",
    "工业机器人末端力控与精密装配方案",
    "电子器件导热灌封材料配方及验证方案",
]


class HttpClient:
    def __init__(self, base_url: str, forwarded_ip: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.forwarded_ip = forwarded_ip

    def request(self, path: str, *, method: str = "GET", payload: dict | None = None, csrf: str = "") -> tuple[int, dict]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if self.forwarded_ip:
            headers["X-Forwarded-For"] = self.forwarded_ip
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                body = json.loads(raw or "{}")
            except json.JSONDecodeError:
                body = {"message": raw}
            return exc.code, body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(base_url: str, admin_username: str, admin_password: str, manager_password: str) -> dict:
    managers: list[dict] = []
    for index in range(20):
        client = HttpClient(base_url, f"198.18.0.{index + 1}")
        phone = f"1398601{index + 1:04d}"
        payload = {
            "real_name": NAMES[index],
            "phone": phone,
            "organization": ORGANIZATIONS[index % len(ORGANIZATIONS)],
            "credential_no": f"QA-NT-TM-{index + 1:03d}（仅用于本地功能测试）",
            "password": manager_password,
        }
        status, response = client.request("/api/manager/register", method="POST", payload=payload)
        require(status == 200 and response.get("ok"), f"第 {index + 1} 名经理人注册失败：{status} {response}")
        managers.append(
            {
                **payload,
                "manager_id": response["manager"]["manager_id"],
                "csrf": response["csrf_token"],
                "client": client,
            }
        )

    status, response = HttpClient(base_url, "198.18.1.1").request(
        "/api/manager/register",
        method="POST",
        payload={
            "real_name": "重复注册测试",
            "phone": managers[0]["phone"],
            "organization": "南通本地测试机构",
            "credential_no": "QA-DUPLICATE-001",
            "password": manager_password,
        },
    )
    require(status == 400 and "已经注册" in response.get("message", ""), "重复手机号未被正确拒绝")

    invalid_cases = [
        {
            "real_name": "号码异常测试",
            "phone": "12345",
            "organization": "南通本地测试机构",
            "credential_no": "QA-INVALID-PHONE",
            "password": manager_password,
        },
        {
            "real_name": "密码异常测试",
            "phone": "13986019999",
            "organization": "南通本地测试机构",
            "credential_no": "QA-INVALID-PASSWORD",
            "password": "1234567",
        },
    ]
    for offset, invalid in enumerate(invalid_cases, start=2):
        status, _ = HttpClient(base_url, f"198.18.1.{offset}").request(
            "/api/manager/register", method="POST", payload=invalid
        )
        require(status == 400, f"无效注册数据未被拒绝：{invalid['real_name']}")

    pre_status, pre_response = managers[0]["client"].request(
        "/api/manager/projects",
        method="POST",
        csrf=managers[0]["csrf"],
        payload={
            "service_mode": "entrusted",
            "enterprise_demand_text": "认证前提交测试：企业需要机器视觉检测技术用于高速生产线质量控制和现场联合验证。",
        },
    )
    require(pre_status == 403 and "认证" in pre_response.get("message", ""), "未认证账号不应允许提交需求")

    admin = HttpClient(base_url)
    status, admin_login = admin.request(
        "/api/admin/login",
        method="POST",
        payload={"username": admin_username, "password": admin_password},
    )
    require(status == 200 and admin_login.get("ok"), f"管理员登录失败：{status} {admin_login}")
    admin_csrf = admin_login["csrf_token"]

    status, before_review = admin.request("/api/admin/managers")
    require(status == 200 and len(before_review.get("items") or []) == 20, "后台待认证经理人数不是 20")
    require(all(item.get("verification_status") == "待认证" for item in before_review["items"]), "初始认证状态不一致")

    for manager in managers:
        status, response = admin.request(
            "/api/admin/managers/verify",
            method="POST",
            csrf=admin_csrf,
            payload={
                "manager_id": manager["manager_id"],
                "verification_status": "已认证",
                "verification_note": "20 人批量注册与全流程 QA：身份资料格式核验通过（虚拟测试数据）。",
            },
        )
        require(status == 200 and response.get("manager", {}).get("verification_status") == "已认证", "后台认证失败")

    project_numbers: list[str] = []
    for index, manager in enumerate(managers):
        service_mode = "entrusted" if index % 2 == 0 else "self_service"
        demand_text = (
            f"本地测试企业希望解决{DEMAND_TOPICS[index]}问题。"
            "要求方案能够提供清晰的技术指标、实施边界、样品或现场验证安排，并说明预计周期、部署条件及后续合作方式。"
        )
        status, response = manager["client"].request(
            "/api/manager/projects",
            method="POST",
            csrf=manager["csrf"],
            payload={"service_mode": service_mode, "enterprise_demand_text": demand_text},
        )
        require(status == 200 and response.get("ok"), f"第 {index + 1} 名经理人提交需求失败：{status} {response}")
        project = response["project"]
        require(not project.get("has_counterpart_contact"), "未登记对接方时不应出现联系人")
        require(project.get("counterpart_contact") == {"unlocked": False}, "空联系人载荷不符合隐私规则")
        expected_fee = "不适用" if service_mode == "entrusted" else "免费阶段"
        require(project.get("service_fee_status") == expected_fee, "免费阶段费用状态不正确")
        project_numbers.append(project["project_no"])
        manager["demand_text"] = demand_text

    duplicate_status, duplicate_response = managers[0]["client"].request(
        "/api/manager/projects",
        method="POST",
        csrf=managers[0]["csrf"],
        payload={"service_mode": "entrusted", "enterprise_demand_text": managers[0]["demand_text"]},
    )
    require(duplicate_status == 400 and "已经提交" in duplicate_response.get("message", ""), "重复需求未被正确拒绝")

    _, verified = admin.request("/api/admin/managers")
    _, projects = admin.request("/api/admin/manager-projects")
    manager_items = verified.get("items") or []
    project_items = projects.get("items") or []
    require(len(manager_items) == 20, "最终经理人总数不是 20")
    require(len(project_items) == 20, "最终经理人项目总数不是 20")
    require(all(item.get("verification_status") == "已认证" for item in manager_items), "存在未完成认证的测试经理人")
    require(all(not item.get("has_counterpart_contact") for item in project_items), "后台项目存在不应出现的技术对接方")
    require(len(set(project_numbers)) == 20, "项目编号发生重复")

    return {
        "ok": True,
        "base_url": base_url,
        "registered": len(manager_items),
        "verified": sum(item.get("verification_status") == "已认证" for item in manager_items),
        "projects": len(project_items),
        "entrusted_projects": sum(item.get("service_mode") == "entrusted" for item in project_items),
        "self_service_projects": sum(item.get("service_mode") == "self_service" for item in project_items),
        "projects_without_counterpart": sum(not item.get("has_counterpart_contact") for item in project_items),
        "duplicate_registration_rejected": True,
        "invalid_registration_rejected": len(invalid_cases),
        "unverified_submission_rejected": True,
        "duplicate_demand_rejected": True,
        "sample_manager_phone": managers[0]["phone"],
        "sample_manager_password": manager_password,
        "sample_project_no": project_numbers[0],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TechNexus 技术经理人 20 人本地全流程 QA")
    parser.add_argument("--base-url", default="http://127.0.0.1:8025")
    parser.add_argument("--admin-username", default="qa-admin")
    parser.add_argument("--admin-password", default="QA-Admin-2026")
    parser.add_argument("--manager-password", default="QA-Manager-2026")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run(args.base_url, args.admin_username, args.admin_password, args.manager_password)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    sys.stdout.buffer.write((output + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
