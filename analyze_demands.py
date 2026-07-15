#!/usr/bin/env python3
"""Build and persist structured technical profiles for JSTEC demands.

The job is incremental: a demand is analyzed again only when its source content
or the analysis schema version changes. Local extraction is always available;
DeepSeek enrichment is optional and can be run in small, restartable batches.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from technexus_app.app import (
    DEMAND_ANALYSIS_VERSION,
    DEMAND_COOP_FIELD,
    DEMAND_DETAIL_FIELD,
    DEMAND_ID_FIELD,
    DEMAND_NAME_FIELD,
    DEMAND_PRICE_FIELD,
    DEMAND_REGION_FIELD,
    DEMAND_TECH_FIELD,
    DEMAND_TYPE_FIELD,
    ai_is_configured,
    build_demand_technical_profile,
    clean_text,
    clip,
    deepseek_chat,
    demand_analysis_stats,
    demand_content_hash,
    init_database,
    load_ai_config,
    load_demand_analysis_map,
    load_demands_from_database,
    merge_technical_profiles,
    normalize_technical_profile,
    now_iso,
    parse_json_object,
    upsert_demand_analysis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="增量拆解技术需求并将技术任务画像写入数据库")
    parser.add_argument("--limit", type=int, default=100, help="本次最多处理多少条；0 表示全部")
    parser.add_argument("--batch-size", type=int, default=4, help="每次 DeepSeek 请求包含的需求数，建议 2-6")
    parser.add_argument(
        "--mode",
        choices=("local", "ai", "hybrid"),
        default="hybrid",
        help="local 仅本地拆解；ai 必须使用 AI；hybrid 有 AI 时增强、无 AI 时使用本地画像",
    )
    parser.add_argument("--force", action="store_true", help="忽略正文指纹和版本，重新处理")
    parser.add_argument("--dry-run", action="store_true", help="只统计待处理需求，不调用 API、不写数据库")
    parser.add_argument("--delay", type=float, default=0.4, help="相邻 DeepSeek 请求之间的间隔秒数")
    parser.add_argument("--max-detail-chars", type=int, default=2200, help="单条需求正文送入 AI 的最大字符数")
    parser.add_argument("--require-ai", action="store_true", help="AI 未配置时直接报错，适合定时任务检查")
    return parser.parse_args()


def profile_quality(profile: dict) -> int:
    profile = normalize_technical_profile(profile)
    score = 0
    score += 15 if profile.get("target") else 0
    score += 20 if profile.get("core_problem") else 0
    score += 10 if profile.get("required_functions") else 0
    score += 15 if profile.get("technical_route") else 0
    score += 10 if profile.get("application_object") else 0
    score += 8 if profile.get("indicators") else 0
    score += 5 if profile.get("constraints") else 0
    score += 5 if profile.get("deliverables") else 0
    score += 4 if profile.get("evidence") else 0
    score += 4 if profile.get("target_terms") else 0
    score += 4 if profile.get("problem_terms") else 0
    return min(100, score)


def compact_demand(demand: dict, max_detail_chars: int) -> dict:
    local_profile = build_demand_technical_profile(demand)
    return {
        "需求ID": clean_text(demand.get(DEMAND_ID_FIELD)),
        "需求名称": clean_text(demand.get(DEMAND_NAME_FIELD)),
        "技术领域": clean_text(demand.get(DEMAND_TECH_FIELD)),
        "需求类型": clean_text(demand.get(DEMAND_TYPE_FIELD)),
        "合作方式": clean_text(demand.get(DEMAND_COOP_FIELD)),
        "意向投入": clean_text(demand.get(DEMAND_PRICE_FIELD)),
        "所在地区": clean_text(demand.get(DEMAND_REGION_FIELD)),
        "需求正文": clip(demand.get(DEMAND_DETAIL_FIELD, ""), max_detail_chars),
        "本地初步画像": local_profile,
    }


def build_analysis_messages(batch: list[dict], max_detail_chars: int) -> list[dict]:
    system_prompt = (
        "你是技术转移平台的技术需求分析员。请逐条阅读需求正文，将其拆成可用于技术可行性匹配的技术任务画像。"
        "重点是正文中的具体技术标的、当前问题、所需功能、技术路线、量化指标和边界条件；"
        "行业、地区和宽泛领域不能代替技术分析。只能依据原文，不得补写原文未说明的工艺、指标、成熟度或结论。"
        "无法确定的字段使用空字符串或空数组。证据必须是需求正文中的简短原句。"
        "每个输入需求必须原样返回需求ID。只输出合法 JSON 对象，不要输出 Markdown。"
    )
    schema = {
        "需求画像列表": [
            {
                "需求ID": "与输入一致",
                "技术任务画像": {
                    "技术标的": "需要研发、改造、验证或交付的具体对象",
                    "核心问题": "当前具体技术障碍或待解决问题",
                    "所需功能": ["最多6项"],
                    "技术路线": "原文明示或允许采用的机理、材料、工艺、算法或装备路线",
                    "量化指标": ["原文明示的数值、单位和阈值，最多8项"],
                    "限制条件": ["材料、工况、尺寸、成本、兼容、认证等限制，最多6项"],
                    "应用对象": "面向的产品、设备、材料、生产环节或使用环境",
                    "可交付物": ["样机、配方、软件、设备、工艺包、报告等，最多6项"],
                    "原文证据": ["直接摘自需求正文的短句，最多6项"],
                    "成熟度要求": "概念验证、实验室、小试、中试或产业化；原文未说明则留空",
                    "技术标的词": ["具体材料、设备、部件、系统或工艺词，最多12个"],
                    "问题词": ["失效、缺陷、瓶颈或目标问题词，最多12个"],
                    "路线词": ["机理、材料、工艺、算法和装备路线词，最多12个"],
                    "指标词": ["含单位或性能属性的词，最多12个"],
                },
                "解析备注": "信息不足或存在歧义时简要说明",
            }
        ]
    }
    payload = {
        "任务": "批量生成技术需求任务画像",
        "需求列表": [compact_demand(item, max_detail_chars) for item in batch],
        "必须返回的JSON结构": schema,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def normalize_ai_demand_profile(item: dict, demand: dict) -> dict:
    raw = item.get("技术任务画像") if isinstance(item.get("技术任务画像"), dict) else {}
    detail = clean_text(demand.get(DEMAND_DETAIL_FIELD))
    evidence = []
    raw_evidence = raw.get("原文证据") or []
    if not isinstance(raw_evidence, list):
        raw_evidence = [raw_evidence]
    for value in raw_evidence:
        sentence = clean_text(value)
        if sentence and sentence in detail:
            evidence.append(sentence)
    return normalize_technical_profile(
        {
            "target": raw.get("技术标的"),
            "core_problem": raw.get("核心问题"),
            "required_functions": raw.get("所需功能"),
            "technical_route": raw.get("技术路线"),
            "indicators": raw.get("量化指标"),
            "constraints": raw.get("限制条件"),
            "application_object": raw.get("应用对象"),
            "deliverables": raw.get("可交付物"),
            "evidence": evidence,
            "maturity": raw.get("成熟度要求"),
            "target_terms": raw.get("技术标的词"),
            "problem_terms": raw.get("问题词"),
            "route_terms": raw.get("路线词"),
            "indicator_terms": raw.get("指标词"),
        }
    )


def analyze_batch(config: dict, batch: list[dict], max_detail_chars: int) -> dict[str, dict]:
    max_tokens = min(8000, max(2800, 1250 * len(batch)))
    content = deepseek_chat(config, build_analysis_messages(batch, max_detail_chars), max_tokens=max_tokens)
    payload = parse_json_object(content)
    raw_items = payload.get("需求画像列表") or []
    if not isinstance(raw_items, list):
        raise ValueError("AI 输出缺少需求画像列表")
    by_id = {clean_text(item.get(DEMAND_ID_FIELD)): item for item in batch}
    results: dict[str, dict] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        demand_id = clean_text(raw_item.get("需求ID"))
        demand = by_id.get(demand_id)
        if not demand:
            continue
        results[demand_id] = normalize_ai_demand_profile(raw_item, demand)
    return results


def needs_analysis(demand: dict, existing: dict | None, mode: str, force: bool) -> bool:
    if force or not existing:
        return True
    if clean_text(existing.get("content_hash")) != demand_content_hash(demand):
        return True
    if clean_text(existing.get("analysis_version")) != DEMAND_ANALYSIS_VERSION:
        return True
    if mode in {"ai", "hybrid"} and clean_text(existing.get("source")) != "local+ai":
        return True
    return False


def save_profile(
    demand: dict,
    local_profile: dict,
    profile: dict,
    *,
    status: str,
    source: str,
    model: str = "",
    error: str = "",
) -> None:
    timestamp = now_iso()
    upsert_demand_analysis(
        {
            "demand_id": clean_text(demand.get(DEMAND_ID_FIELD)),
            "content_hash": demand_content_hash(demand),
            "analysis_version": DEMAND_ANALYSIS_VERSION,
            "status": status,
            "source": source,
            "model": model,
            "profile": profile,
            "local_profile": local_profile,
            "quality_score": profile_quality(profile),
            "error": error,
            "analyzed_at": timestamp,
            "updated_at": timestamp,
        }
    )


def chunks(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def main() -> int:
    args = parse_args()
    args.batch_size = max(1, min(8, args.batch_size))
    args.max_detail_chars = max(800, min(5000, args.max_detail_chars))
    init_database()
    demands = load_demands_from_database()
    existing = load_demand_analysis_map()
    pending = [
        demand
        for demand in demands
        if clean_text(demand.get(DEMAND_ID_FIELD))
        and needs_analysis(
            demand,
            existing.get(clean_text(demand.get(DEMAND_ID_FIELD))),
            args.mode,
            args.force,
        )
    ]
    if args.limit > 0:
        pending = pending[: args.limit]

    config = load_ai_config()
    use_ai = args.mode in {"ai", "hybrid"} and ai_is_configured(config)
    if (args.mode == "ai" or args.require_ai) and not use_ai:
        print("未配置可用的 DeepSeek API；请设置 TECHNEXUS_AI_API_KEY 等环境变量。", file=sys.stderr)
        return 2

    preview = {
        "analysis_version": DEMAND_ANALYSIS_VERSION,
        "database_demand_count": len(demands),
        "pending_count": len(pending),
        "mode": args.mode,
        "use_ai": use_ai,
        "dry_run": args.dry_run,
        "before": demand_analysis_stats(),
    }
    if args.dry_run or not pending:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    success = 0
    failed = 0
    model = clean_text(config.get("model")) if use_ai else ""
    for batch in chunks(pending, args.batch_size if use_ai else max(1, len(pending))):
        local_profiles = {
            clean_text(demand.get(DEMAND_ID_FIELD)): build_demand_technical_profile(demand) for demand in batch
        }
        if not use_ai:
            for demand in batch:
                demand_id = clean_text(demand.get(DEMAND_ID_FIELD))
                local_profile = local_profiles[demand_id]
                save_profile(demand, local_profile, local_profile, status="ready", source="local")
                success += 1
            continue

        try:
            ai_profiles = analyze_batch(config, batch, args.max_detail_chars)
            for demand in batch:
                demand_id = clean_text(demand.get(DEMAND_ID_FIELD))
                local_profile = local_profiles[demand_id]
                ai_profile = ai_profiles.get(demand_id)
                if ai_profile:
                    profile = merge_technical_profiles(local_profile, ai_profile)
                    save_profile(
                        demand,
                        local_profile,
                        profile,
                        status="ready",
                        source="local+ai",
                        model=model,
                    )
                    success += 1
                else:
                    save_profile(
                        demand,
                        local_profile,
                        local_profile,
                        status="failed",
                        source="local",
                        model=model,
                        error="AI 未返回该需求的画像",
                    )
                    failed += 1
        except Exception as exc:  # noqa: BLE001 - persist fallback and keep the incremental job moving.
            error = str(exc)
            print(f"批次解析失败，已保存本地画像并等待重试：{error}", file=sys.stderr)
            for demand in batch:
                demand_id = clean_text(demand.get(DEMAND_ID_FIELD))
                local_profile = local_profiles[demand_id]
                save_profile(
                    demand,
                    local_profile,
                    local_profile,
                    status="failed",
                    source="local",
                    model=model,
                    error=error,
                )
                failed += 1
        if use_ai and args.delay > 0:
            time.sleep(args.delay)

    result: dict[str, Any] = {
        **preview,
        "success": success,
        "failed": failed,
        "after": demand_analysis_stats(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
