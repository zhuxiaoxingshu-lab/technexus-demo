from __future__ import annotations

import sys
import tempfile
import unittest
import gc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from technexus_app import app  # noqa: E402


class ManagerP0WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_file = app.DB_FILE
        self.original_database_url = app.DATABASE_URL
        app.DB_FILE = Path(self.temp_dir.name) / "manager-p0-test.db"
        app.DATABASE_URL = ""
        app.init_database()
        self.manager = app.register_manager(
            {
                "real_name": "张经理",
                "phone": "13800001234",
                "organization": "南通技术转移中心",
                "credential_no": "JS-TM-2026-001",
                "password": "LocalTest!2026",
            }
        )

    def tearDown(self) -> None:
        app.DB_FILE = self.original_db_file
        app.DATABASE_URL = self.original_database_url
        gc.collect()
        self.temp_dir.cleanup()

    def approve_manager(self) -> None:
        approved = app.verify_technical_manager(
            self.manager["manager_id"],
            "已认证",
            "本地 P0 自动化测试通过",
            "admin",
        )
        self.assertEqual(approved["verification_status"], "已认证")

    def test_pending_manager_cannot_submit_project(self) -> None:
        with self.assertRaises(PermissionError):
            app.create_manager_project(
                self.manager["manager_id"],
                {
                    "service_mode": "entrusted",
                    "enterprise_demand_text": "企业需要开发一套用于锂电池产线的在线缺陷检测系统，要求支持高速图像采集、边缘推理和缺陷追溯。",
                },
            )

    def test_self_service_contact_is_hidden_until_fee_and_unlock(self) -> None:
        self.approve_manager()
        project = app.create_manager_project(
            self.manager["manager_id"],
            {
                "service_mode": "self_service",
                "enterprise_demand_text": "企业需要开发一套用于锂电池产线的在线缺陷检测系统，要求支持高速图像采集、边缘推理和缺陷追溯。",
            },
        )
        self.assertFalse(project["counterpart_contact"]["unlocked"])
        self.assertEqual(project["service_fee_status"], "免费阶段")
        self.assertNotIn("13811112222", str(project))

        with self.assertRaises(ValueError):
            app.update_manager_project(
                project["project_id"],
                {
                    "status": "已建立技术对接",
                    "service_fee_status": "待支付",
                    "contact_unlock_status": "已解锁",
                    "counterpart_contact": {
                        "name": "李老师",
                        "phone": "13811112222",
                        "organization": "南通大学技术团队",
                        "email": "li@example.cn",
                    },
                },
                "admin",
            )

        updated = app.update_manager_project(
            project["project_id"],
            {
                "status": "已建立技术对接",
                "service_fee_status": "已支付",
                "contact_unlock_status": "已解锁",
                "match_summary": "已确认一项机器视觉检测成果，可进入技术参数沟通。",
                "counterpart_contact": {
                    "name": "李老师",
                    "phone": "13811112222",
                    "organization": "南通大学技术团队",
                    "email": "li@example.cn",
                },
            },
            "admin",
        )
        self.assertTrue(updated["counterpart_contact"]["unlocked"])

        workbench = app.get_manager_workbench(self.manager["manager_id"])
        visible = workbench["projects"][0]["counterpart_contact"]
        self.assertTrue(visible["unlocked"])
        self.assertEqual(visible["phone"], "13811112222")

    def test_manager_can_report_owned_self_service_progress_after_review(self) -> None:
        self.approve_manager()
        project = app.create_manager_project(
            self.manager["manager_id"],
            {
                "service_mode": "self_service",
                "enterprise_demand_text": "企业计划升级高温合金精密铸造工艺，需要高校团队协助优化缺陷控制、热处理参数并完成小试验证。",
            },
        )
        app.update_manager_project(
            project["project_id"],
            {
                "status": "已受理",
                "audit_note": "需求描述完整，允许经理人自主联系技术资源。",
            },
            "admin",
        )
        updated = app.save_manager_self_service_progress(
            self.manager["manager_id"],
            project["project_id"],
            {
                "status": "对接中",
                "progress_summary": "已与高校材料团队完成首次沟通，双方约定交换缺陷样本和现有工艺参数。",
                "counterpart_contact": {
                    "name": "周老师",
                    "phone": "13900008882",
                    "organization": "南通材料工程研究中心（测试）",
                    "email": "qa-self-service@example.test",
                },
            },
        )
        self.assertEqual(updated["counterpart_contact_source"], "manager_self_reported")
        self.assertEqual(updated["counterpart_contact_source_label"], "经理人自主登记")
        self.assertEqual(updated["service_fee_status"], "待确认")
        self.assertEqual(updated["status"], "对接中")
        self.assertTrue(updated["counterpart_contact"]["unlocked"])
        self.assertEqual(updated["counterpart_contact"]["phone"], "13900008882")

        admin_saved = app.update_manager_project(
            project["project_id"],
            {
                "status": "对接中",
                "service_fee_status": "待支付",
                "contact_unlock_status": "已解锁",
                "match_summary": "经理人已自主建立联系，平台完成过程记录并确认服务费。",
            },
            "admin",
        )
        self.assertEqual(admin_saved["service_fee_status"], "待支付")

        other = app.register_manager(
            {
                "real_name": "其他经理",
                "phone": "13800005678",
                "organization": "其他技术服务机构",
                "credential_no": "JS-TM-2026-099",
                "password": "LocalTest!2026",
            }
        )
        app.verify_technical_manager(other["manager_id"], "已认证", "测试账号", "admin")
        with self.assertRaises(KeyError):
            app.save_manager_self_service_progress(
                other["manager_id"],
                project["project_id"],
                {
                    "status": "对接中",
                    "progress_summary": "尝试越权登记其他经理人的自主对接项目进展。",
                    "counterpart_contact": {
                        "name": "无关联系人",
                        "phone": "13900009999",
                        "organization": "无关测试机构",
                    },
                },
            )

    def test_entrusted_project_and_manual_settlement(self) -> None:
        self.approve_manager()
        project = app.create_manager_project(
            self.manager["manager_id"],
            {
                "service_mode": "entrusted",
                "enterprise_demand_text": "企业拟寻找耐海洋腐蚀的高性能复合涂层技术，用于海工结构长期防护，要求提供样品、测试报告和联合验证方案。",
            },
        )
        settlement = app.save_manager_settlement(
            project["project_id"],
            {
                "settlement_type": "平台撮合分成",
                "deal_amount": "500000",
                "platform_fee": "25000",
                "manager_share": "10000",
                "status": "已结算",
                "note": "按项目合作约定人工登记",
            },
            "admin",
        )
        self.assertEqual(settlement["manager_share"], "10000.00")
        workbench = app.get_manager_workbench(self.manager["manager_id"])
        self.assertEqual(workbench["stats"]["settled_share"], "10000.00")


class ProxyHeaderSecurityTests(unittest.TestCase):
    def test_forwarded_ip_is_ignored_unless_proxy_trust_is_enabled(self) -> None:
        dummy = type(
            "DummyHandler",
            (),
            {
                "headers": {"X-Forwarded-For": "198.18.0.7, 127.0.0.1"},
                "client_address": ("127.0.0.1", 12345),
            },
        )()
        original = app.TRUST_PROXY_HEADERS
        try:
            app.TRUST_PROXY_HEADERS = False
            self.assertEqual(app.TechNexusHandler.client_ip(dummy), "127.0.0.1")
            app.TRUST_PROXY_HEADERS = True
            self.assertEqual(app.TechNexusHandler.client_ip(dummy), "198.18.0.7")
        finally:
            app.TRUST_PROXY_HEADERS = original


if __name__ == "__main__":
    unittest.main()
