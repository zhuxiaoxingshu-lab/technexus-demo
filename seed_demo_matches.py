from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from technexus_app import app


DEMO_PREFIX = "nantong-ai-demo-v1"
DEMO_SOURCE = "AI演示数据-南通高校科研院所"

DEMO_SPECS = [
    ("南通大学", "面向纺织面料的低样本视觉瑕疵识别与在线分级"),
    ("江苏工程职业技术学院", "活性染料低盐染色与废水回用协同工艺"),
    ("江苏航运职业技术学院", "内河船舶机舱多源传感故障预警系统"),
    ("南通职业大学", "焊接机器人视觉引导与轨迹自适应控制"),
    ("南通科技职业学院", "设施农业病虫害智能监测与精准施药装备"),
    ("南通理工学院", "新能源汽车动力电池热失控早期诊断装置"),
    ("江苏商贸职业学院", "冷链仓储需求预测与智能调度平台"),
    ("南通师范高等专科学校", "面向职业教育的多模态实训评价系统"),
    ("南通卫生健康职业学院", "基层康复训练动作识别与风险提示系统"),
    ("南京邮电大学南通研究院", "先进封装芯片缺陷的太赫兹无损检测方法"),
    ("南京信息工程大学南通研究院", "海上风电齿轮箱复合故障智能诊断"),
    ("南京大学南通研究院", "高性能纤维增强复合材料界面改性技术"),
    ("南通大学", "海洋工程结构腐蚀状态在线监测传感网络"),
    ("江苏工程职业技术学院", "纺织印染碳排放数字化核算与工艺优化"),
    ("江苏航运职业技术学院", "港口散货装卸设备预测性维护系统"),
    ("南通职业大学", "精密零部件微小尺寸机器视觉测量技术"),
    ("南通科技职业学院", "水产养殖水质多参数监测与智能增氧控制"),
    ("南通理工学院", "面向工业园区的分布式储能能量管理系统"),
    ("南京邮电大学南通研究院", "工业物联网边缘侧异常流量检测网关"),
    ("南京信息工程大学南通研究院", "长江口近岸生态环境遥感智能解译平台"),
]

FOLLOWUP_STATUSES = [
    "待联系成果方",
    "已联系成果方",
    "待联系需求方",
    "已联系需求方",
    "双方沟通中",
    "已安排会议",
    "已发送材料",
    "已签约",
    "已成交",
    "暂停跟进",
    "不再跟进",
]


def demo_id(index: int, kind: str) -> str:
    return f"{DEMO_PREFIX}-{kind}-{index:02d}"


def load_existing_records() -> list[dict]:
    expected_ids = [demo_id(index, "submission") for index in range(1, len(DEMO_SPECS) + 1)]
    placeholders = ",".join("?" for _ in expected_ids)
    with app.db_connect() as conn:
        rows = app.db_execute(
            conn,
            f"SELECT submission_id, submission_json FROM submissions WHERE submission_id IN ({placeholders})",
            expected_ids,
        ).fetchall()
    found = {app.clean_text(dict(row).get("submission_id")): dict(row) for row in rows}
    if len(found) != len(expected_ids):
        return []
    records: list[dict] = []
    for submission_id in expected_ids:
        payload = app.decode_json_field(found[submission_id].get("submission_json"), {})
        if not isinstance(payload, dict) or payload.get("client_source") != DEMO_SOURCE:
            return []
        records.append(payload)
    return records


def generation_messages() -> list[dict]:
    specs = [
        {"序号": index, "单位": institution, "主题": topic}
        for index, (institution, topic) in enumerate(DEMO_SPECS, start=1)
    ]
    return [
        {
            "role": "system",
            "content": (
                "你是技术转移平台的科研成果材料编辑。只输出合法 JSON 对象，不使用 Markdown。"
                "内容必须专业、具体、适合技术供需匹配，但不得声称真实专利号、真实获奖、真实临床批件或真实成交。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请严格依据下面固定的20组单位与主题，生成用于后台联调的虚构科研成果。"
                "不得修改单位名称、序号或主题。每组返回字段：序号、单位、成果名称、技术成果内容。"
                "技术成果内容为一个160至260个中文字符的完整段落，依次自然说明产业痛点、适用对象、"
                "核心技术路线、3项可量化的演示指标、当前成熟度或验证条件、可交付物和合作方式。"
                "所有指标均为演示设定，不得编造可核验的真实项目事实。"
                "返回格式必须是 {\"成果列表\":[...]}，数组严格20项。固定清单："
                + json.dumps(specs, ensure_ascii=False)
            ),
        },
    ]


def validate_generated(payload: dict) -> list[dict]:
    items = payload.get("成果列表")
    if not isinstance(items, list) or len(items) != len(DEMO_SPECS):
        raise ValueError("DeepSeek 未返回严格 20 条成果")
    validated: list[dict] = []
    for index, ((institution, topic), item) in enumerate(zip(DEMO_SPECS, items), start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条成果不是对象")
        returned_index = int(item.get("序号") or 0)
        returned_institution = app.clean_text(item.get("单位"))
        title = app.clean_text(item.get("成果名称"))
        achievement_text = app.clean_text(item.get("技术成果内容"))
        if returned_index != index or returned_institution != institution:
            raise ValueError(f"第 {index} 条单位或序号被模型改写")
        if len(title) < 8 or len(achievement_text) < 100:
            raise ValueError(f"第 {index} 条内容过短")
        validated.append(
            {
                "name": f"AI演示课题组 {index:02d}",
                "company": institution,
                "title": title,
                "achievement_text": f"【AI演示数据】{achievement_text}",
                "summary": achievement_text,
                "application_scene": topic,
                "region": "江苏省 / 南通市",
                "maturity": "演示设定：中试验证阶段",
                "cooperation": "技术许可、联合开发或场景验证",
                "client_source": DEMO_SOURCE,
                "demo_seed_id": demo_id(index, "record"),
            }
        )
    return validated


def generate_records(ai_config: dict) -> list[dict]:
    if not app.ai_is_configured(ai_config):
        raise RuntimeError("DeepSeek 未配置，拒绝生成非 AI 演示数据")
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            content = app.deepseek_chat(ai_config, generation_messages(), max_tokens=9000)
            return validate_generated(app.parse_json_object(content))
        except Exception as exc:  # retry once for an incomplete structured response
            last_error = exc
            print(f"AI generation attempt {attempt} failed: {exc}", flush=True)
    raise RuntimeError(f"DeepSeek 生成 20 条成果失败：{last_error}")


def select_results(refined: list[dict]) -> tuple[list[dict], int]:
    selected = [item for item in refined if int(item.get("score") or 0) >= 45][:5]
    fill_count = 0
    if len(selected) < 3:
        selected_ids = {app.clean_text(item.get("demand_id")) for item in selected}
        for item in refined:
            demand_id = app.clean_text(item.get("demand_id"))
            if not demand_id or demand_id in selected_ids:
                continue
            fallback = dict(item)
            fallback["demo_below_public_threshold"] = True
            selected.append(fallback)
            selected_ids.add(demand_id)
            fill_count += 1
            if len(selected) >= 3:
                break
    return selected[:5], fill_count


def seed(*, regenerate: bool = False, no_ai_rerank: bool = False) -> dict:
    app.init_database()
    store = app.DemandStore(app.DEMANDS_FILE)
    store.load()
    if not store.demands:
        raise RuntimeError("需求库为空，无法生成匹配记录")

    ai_config = app.load_ai_config()
    records = [] if regenerate else load_existing_records()
    if records:
        print("Reusing the existing 20 AI-generated demo achievements.", flush=True)
    else:
        print("Calling DeepSeek once to generate 20 demo achievements...", flush=True)
        records = generate_records(ai_config)

    base_time = datetime.now().replace(microsecond=0)
    ai_used_count = 0
    local_fallback_count = 0
    result_count = 0
    followup_count = 0
    low_score_fill_count = 0

    for index, submission in enumerate(records, start=1):
        submission_id = demo_id(index, "submission")
        match_id = demo_id(index, "match")
        created_at = (base_time - timedelta(minutes=(len(records) - index) * 17)).strftime("%Y-%m-%d %H:%M:%S")
        tag_profile = app.extract_submission_tags_local(submission)
        capability_profile = app.build_submission_technical_profile(submission)
        local_results = app.match_demands(
            store,
            submission,
            limit=20,
            candidate_limit=220,
            tags=tag_profile,
            capability_profile=capability_profile,
        )
        if no_ai_rerank:
            refined, ai_meta = app.use_quick_match(local_results)
        else:
            refined, ai_meta = app.refine_matches_with_ai(
                ai_config,
                submission,
                local_results,
                tag_profile=tag_profile,
                tag_meta={"used_ai": False, "source": "local-demo-seed"},
                capability_profile=capability_profile,
            )
        selected, fill_count = select_results(refined)
        low_score_fill_count += fill_count
        ai_meta.update(
            {
                "demo_data": True,
                "demo_seed_id": submission["demo_seed_id"],
                "demo_source": DEMO_SOURCE,
                "structured_tags": app.compact_tag_payload(tag_profile),
                "capability_profile": app.normalize_technical_profile(
                    ai_meta.get("capability_profile") or capability_profile
                ),
                "local_candidate_count": len(local_results),
                "demo_threshold_fill_count": fill_count,
            }
        )
        ai_meta["message"] = "AI演示数据；" + app.clean_text(ai_meta.get("message"))
        app.save_submission(
            {"submission_id": submission_id, "created_at": created_at, "submission": submission}
        )
        app.save_match(
            {
                "match_id": match_id,
                "submission_id": submission_id,
                "created_at": created_at,
                "ai_meta": ai_meta,
                "submission": submission,
                "results": selected,
            }
        )
        if selected:
            status = FOLLOWUP_STATUSES[(index - 1) % len(FOLLOWUP_STATUSES)]
            app.save_match_followup(
                store,
                match_id,
                app.clean_text(selected[0].get("demand_id")),
                status,
                "AI演示数据：用于验证后台跟进状态展示，不代表真实联系。",
                f"演示流程阶段：{status}；记录可在后台正常编辑。",
            )
            followup_count += 1
        if ai_meta.get("used_ai"):
            ai_used_count += 1
        else:
            local_fallback_count += 1
        result_count += len(selected)
        print(
            f"[{index:02d}/20] {submission['company']} | {len(selected)} matches | "
            f"AI={'yes' if ai_meta.get('used_ai') else 'fallback'}",
            flush=True,
        )

    return {
        "demo_records": len(records),
        "matched_candidates": result_count,
        "followups": followup_count,
        "ai_reranked_records": ai_used_count,
        "local_fallback_records": local_fallback_count,
        "below_threshold_demo_fills": low_score_fill_count,
    }


def delete_demo_data() -> dict:
    app.init_database()
    submission_ids = [demo_id(index, "submission") for index in range(1, len(DEMO_SPECS) + 1)]
    match_ids = [demo_id(index, "match") for index in range(1, len(DEMO_SPECS) + 1)]
    submission_placeholders = ",".join("?" for _ in submission_ids)
    match_placeholders = ",".join("?" for _ in match_ids)
    with app.db_connect() as conn:
        followups = app.db_execute(
            conn,
            f"DELETE FROM match_followups WHERE match_id IN ({match_placeholders})",
            match_ids,
        ).rowcount
        matches = app.db_execute(
            conn,
            f"DELETE FROM matches WHERE match_id IN ({match_placeholders})",
            match_ids,
        ).rowcount
        submissions = app.db_execute(
            conn,
            f"DELETE FROM submissions WHERE submission_id IN ({submission_placeholders})",
            submission_ids,
        ).rowcount
    return {"deleted_submissions": submissions, "deleted_matches": matches, "deleted_followups": followups}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成或安全删除 20 组南通高校科研院所 AI 演示匹配数据")
    parser.add_argument("--delete", action="store_true", help="仅删除本脚本固定 ID 创建的演示数据")
    parser.add_argument("--regenerate", action="store_true", help="重新调用 AI 生成成果文本")
    parser.add_argument("--no-ai-rerank", action="store_true", help="仅用于离线调试：跳过 AI 精排")
    args = parser.parse_args()
    result = delete_demo_data() if args.delete else seed(
        regenerate=args.regenerate,
        no_ai_rerank=args.no_ai_rerank,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
