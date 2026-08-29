from __future__ import annotations

import argparse
import hashlib
import re

from technexus_app import app


MANAGER_ID = "local-manager-p0-nantong-v1"
MANAGER_PHONE = "13900005678"
PROJECT_IDS = ["local-manager-p0-self-v1", "local-manager-p0-entrusted-v1"]
SETTLEMENT_ID = "local-manager-p0-settlement-v1"


def delete_seed() -> None:
    app.init_database()
    with app.db_connect() as conn:
        placeholders = ", ".join("?" for _ in PROJECT_IDS)
        app.db_execute(conn, "DELETE FROM manager_settlements WHERE settlement_id = ?", (SETTLEMENT_ID,))
        app.db_execute(conn, f"DELETE FROM manager_project_logs WHERE project_id IN ({placeholders})", PROJECT_IDS)
        app.db_execute(conn, f"DELETE FROM manager_projects WHERE project_id IN ({placeholders})", PROJECT_IDS)
        app.db_execute(conn, "DELETE FROM technical_managers WHERE manager_id = ?", (MANAGER_ID,))
    print("已删除技术经理人 P0 本地测试数据。")


def seed(password: str) -> None:
    if len(password) < 8:
        raise SystemExit("测试密码至少需要 8 位。")
    app.init_database()
    timestamp = app.now_iso()
    with app.db_connect() as conn:
        phone_owner = app.db_execute(
            conn,
            "SELECT manager_id FROM technical_managers WHERE phone = ?",
            (MANAGER_PHONE,),
        ).fetchone()
        if phone_owner and app.clean_text(dict(phone_owner).get("manager_id")) != MANAGER_ID:
            raise SystemExit(f"测试手机号 {MANAGER_PHONE} 已被其他账号使用，请先更换脚本中的测试手机号。")
        app.db_execute(
            conn,
            """
            INSERT INTO technical_managers
                (manager_id, created_at, updated_at, real_name, phone, organization,
                 credential_no, password_hash, verification_status, verification_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (manager_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                real_name = excluded.real_name,
                phone = excluded.phone,
                organization = excluded.organization,
                credential_no = excluded.credential_no,
                password_hash = excluded.password_hash,
                verification_status = excluded.verification_status,
                verification_note = excluded.verification_note
            """,
            (
                MANAGER_ID,
                timestamp,
                timestamp,
                "周经理",
                MANAGER_PHONE,
                "南通技术转移服务中心",
                "NT-TM-P0-001",
                app.hash_password(password),
                "已认证",
                "P0 本地功能测试账号",
            ),
        )
        app.db_execute(conn, "DELETE FROM manager_settlements WHERE settlement_id = ?", (SETTLEMENT_ID,))
        placeholders = ", ".join("?" for _ in PROJECT_IDS)
        app.db_execute(conn, f"DELETE FROM manager_project_logs WHERE project_id IN ({placeholders})", PROJECT_IDS)
        app.db_execute(conn, f"DELETE FROM manager_projects WHERE project_id IN ({placeholders})", PROJECT_IDS)

        self_demand = (
            "南通某精密制造企业希望寻找面向高速产线的机器视觉缺陷检测技术，要求实现微小划痕与尺寸偏差在线识别，"
            "支持边缘计算部署、质量数据追溯和现场联合验证。"
        )
        entrusted_demand = (
            "南通某海工装备企业拟寻找耐盐雾、耐磨损的复合防护涂层技术，用于海上结构件长期防腐，"
            "希望提供样品、第三方测试报告、中试放大条件及联合验证方案。"
        )
        project_rows = [
            (
                PROJECT_IDS[0],
                "TM-LOCAL-P0-001",
                self_demand,
                "self_service",
                "已受理",
                "企业需求已完成建档，可由技术经理人自主寻找技术资源并推进联系。",
                "等待技术经理人补充自主联系和项目对接进展。",
                "{}",
                "未解锁",
                "免费阶段",
            ),
            (
                PROJECT_IDS[1],
                "TM-LOCAL-P0-002",
                entrusted_demand,
                "entrusted",
                "匹配中",
                "平台已受理，正在核验成果成熟度与海工应用数据。",
                "平台正在通过线下渠道寻找适合的技术资源并进行人工核验。",
                "{}",
                "未解锁",
                "不适用",
            ),
        ]
        for project_id, project_no, demand_text, mode, status, audit_note, match_summary, contact_json, unlock, fee_status in project_rows:
            demand_hash = hashlib.sha256(re.sub(r"\s+", "", demand_text).lower().encode("utf-8")).hexdigest()
            app.db_execute(
                conn,
                """
                INSERT INTO manager_projects
                    (project_id, project_no, manager_id, created_at, updated_at,
                     enterprise_demand_text, demand_hash, service_mode, status,
                     audit_note, match_summary, counterpart_contact_json,
                     contact_unlock_status, contact_unlocked_at, service_fee_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    project_no,
                    MANAGER_ID,
                    timestamp,
                    timestamp,
                    demand_text,
                    demand_hash,
                    mode,
                    status,
                    audit_note,
                    match_summary,
                    contact_json,
                    unlock,
                    "",
                    fee_status,
                ),
            )
            app.save_manager_project_log(project_id, "载入 P0 本地测试项目", status, "local-seed", conn)

    print(f"已生成技术经理人 P0 本地测试数据，登录手机号：{MANAGER_PHONE}")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成或删除技术经理人 P0 本地测试数据")
    parser.add_argument("--password", help="本地测试账号密码；生成数据时必填")
    parser.add_argument("--delete", action="store_true", help="只删除固定 ID 的 P0 本地测试数据")
    args = parser.parse_args()
    if args.delete:
        delete_seed()
        return 0
    if not args.password:
        parser.error("生成数据时必须提供 --password")
    seed(args.password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
