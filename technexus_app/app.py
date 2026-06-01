from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
import math
import mimetypes
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections import Counter
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = BASE_DIR / "technexus_data"
DEMANDS_FILE = BASE_DIR / "jstec_demands.checkpoint.jsonl"
AI_CONFIG_FILE = BASE_DIR / "ai_config.json"
ADMIN_CONFIG_FILE = BASE_DIR / "admin_config.json"
DB_FILE = DATA_DIR / "technexus.db"
DATABASE_URL = os.getenv("TECHNEXUS_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
SESSION_COOKIE = "technexus_admin_session"
SESSION_SECONDS = 8 * 60 * 60
AGREEMENT_VERSION = "TechNexus-2026-06-01-v2"
INTENT_STATUSES = [
    "待审核",
    "已联系成果方",
    "已联系需求方",
    "撮合中",
    "已签中介协议",
    "合作成功",
    "合作失败",
]

CONTACT_FIELDS = {"联系方式", "详情页链接"}
STOPWORDS = {
    "技术",
    "需求",
    "成果",
    "项目",
    "研发",
    "开发",
    "应用",
    "合作",
    "解决",
    "相关",
    "研究",
    "产业",
    "材料",
    "产品",
    "进行",
    "实现",
    "提高",
    "具有",
    "通过",
    "基于",
    "以及",
    "一种",
    "方向",
    "领域",
}


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_ai_config() -> dict:
    config = {
        "enabled": False,
        "provider": "openai-compatible",
        "base_url": "",
        "api_key": "",
        "model": "",
        "temperature": 0.2,
        "timeout": 45,
    }
    if AI_CONFIG_FILE.exists():
        try:
            file_config = json.loads(AI_CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(file_config, dict):
                config.update(file_config)
        except (OSError, json.JSONDecodeError):
            pass

    env_map = {
        "TECHNEXUS_AI_BASE_URL": "base_url",
        "TECHNEXUS_AI_API_KEY": "api_key",
        "TECHNEXUS_AI_MODEL": "model",
        "TECHNEXUS_AI_PROVIDER": "provider",
    }
    for env_name, key in env_map.items():
        if os.getenv(env_name):
            config[key] = os.getenv(env_name, "")
    if os.getenv("TECHNEXUS_AI_ENABLED"):
        config["enabled"] = os.getenv("TECHNEXUS_AI_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    return config


def ai_is_configured(config: dict) -> bool:
    return bool(config.get("enabled") and config.get("base_url") and config.get("api_key") and config.get("model"))


def ai_status(config: dict) -> dict:
    configured = ai_is_configured(config)
    return {
        "ai_configured": configured,
        "ai_provider": clean_text(config.get("provider", "")) if configured else "",
        "ai_model": clean_text(config.get("model", "")) if configured else "",
        "ai_mode": "AI精排" if configured else "本地规则",
    }


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clip(text: str, limit: int = 220) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def format_money(value: object) -> str:
    text = clean_text(value)
    if not text or text in {"0", "0.0", "面议"}:
        return "面议"
    number_text = re.sub(r"[^\d.]", "", text)
    if not number_text:
        return text
    try:
        number = float(number_text)
    except ValueError:
        return text
    if number <= 0:
        return "面议"
    if number >= 10000:
        amount = number / 10000
        if amount.is_integer():
            return f"{int(amount)}万"
        return f"{amount:.1f}万"
    if number.is_integer():
        return f"{int(number)}元"
    return f"{number:.0f}元"


def extract_ascii_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9.+#/-]{1,}", text.lower())


def extract_cjk_ngrams(text: str) -> list[str]:
    grams: list[str] = []
    for seq in re.findall(r"[\u4e00-\u9fff]+", text):
        if 2 <= len(seq) <= 6 and seq not in STOPWORDS:
            grams.append(seq)
        for size in (2, 3):
            if len(seq) >= size:
                grams.extend(seq[i : i + size] for i in range(len(seq) - size + 1))
    return grams


def tokenize(text: str) -> Counter:
    text = clean_text(text)
    tokens = extract_ascii_tokens(text) + extract_cjk_ngrams(text)
    return Counter(t for t in tokens if t and t not in STOPWORDS and len(t) >= 2)


def cosine(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    dot = sum(count * right.get(token, 0) for token, count in left.items())
    if dot <= 0:
        return 0.0
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def score_from_similarity(user_text: str, demand_text: str, *, baseline: int = 38, scale: float = 185.0) -> int:
    user_tokens = tokenize(user_text)
    if not user_tokens:
        return baseline
    demand_tokens = tokenize(demand_text)
    raw = cosine(user_tokens, demand_tokens)
    return max(0, min(100, round(raw * scale)))


def maturity_level(text: str) -> int | None:
    text = clean_text(text)
    if not text:
        return None
    mapping = [
        (5, ["量产", "产业化", "规模化", "已有客户", "批量"]),
        (4, ["中试", "示范线", "试生产", "工程化"]),
        (3, ["小试", "样品", "样机", "试制", "验证"]),
        (2, ["实验室", "原理样机", "概念验证", "TRL 3", "TRL3", "TRL 4", "TRL4"]),
        (1, ["概念", "方案", "论文"]),
    ]
    for level, words in mapping:
        if any(word in text for word in words):
            return level
    trl = re.search(r"TRL\s*([1-9])", text, re.IGNORECASE)
    if trl:
        value = int(trl.group(1))
        if value >= 8:
            return 5
        if value >= 6:
            return 4
        if value >= 4:
            return 3
        return 2
    return 3


def maturity_score(user_maturity: str, demand_detail: str) -> int:
    user_level = maturity_level(user_maturity)
    demand_level = maturity_level(demand_detail)
    if user_level is None:
        return 70
    if demand_level is None:
        demand_level = 3
    return max(35, 100 - abs(user_level - demand_level) * 18)


def shared_keywords(user_text: str, demand_text: str, limit: int = 6) -> list[str]:
    user_tokens = tokenize(user_text)
    demand_tokens = tokenize(demand_text)
    overlap = []
    for token in user_tokens:
        if token in demand_tokens and token not in STOPWORDS:
            overlap.append((len(token), user_tokens[token] + demand_tokens[token], token))
    overlap.sort(reverse=True)
    result: list[str] = []
    for _, _, token in overlap:
        if token not in result and len(token) <= 10:
            result.append(token)
        if len(result) >= limit:
            break
    return result


class DemandStore:
    def __init__(self, path: Path):
        self.path = path
        self.demands: list[dict] = []
        self.loaded_at = ""

    def load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"未找到需求库文件：{self.path}")
        demands: list[dict] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cleaned = {clean_text(k): clean_text(v) for k, v in item.items()}
                if not cleaned.get("需求ID") and not cleaned.get("需求名称"):
                    continue
                search_text = " ".join(
                    cleaned.get(field, "")
                    for field in ("需求名称", "技术领域", "需求类型", "所在地区", "需求详情", "合作方式")
                )
                cleaned["_search_text"] = search_text
                cleaned["_tokens"] = tokenize(search_text)
                demands.append(cleaned)
        self.demands = demands
        self.loaded_at = now_iso()

    def stats(self) -> dict:
        return {"demand_count": len(self.demands), "loaded_at": self.loaded_at}

    def by_id(self, demand_id: str) -> dict | None:
        demand_id = clean_text(demand_id)
        for demand in self.demands:
            if demand.get("需求ID") == demand_id:
                return demand
        return None

    def search(self, keyword: str = "", limit: int = 50) -> list[dict]:
        keyword = clean_text(keyword)
        if not keyword:
            rows = self.demands[:limit]
        else:
            keyword_tokens = tokenize(keyword)
            scored = []
            for demand in self.demands:
                score = cosine(keyword_tokens, demand.get("_tokens", Counter()))
                if keyword in demand.get("_search_text", ""):
                    score += 0.35
                if score > 0:
                    scored.append((score, demand))
            scored.sort(key=lambda item: item[0], reverse=True)
            rows = [demand for _, demand in scored[:limit]]
        return [sanitize_demand(row, include_detail=True) for row in rows]


def sanitize_demand(demand: dict, *, include_detail: bool = False) -> dict:
    item = {
        "demand_id": demand.get("需求ID", ""),
        "name": demand.get("需求名称", ""),
        "demand_no": demand.get("需求编号", ""),
        "cooperation_mode": demand.get("合作方式", ""),
        "intended_price": format_money(demand.get("意向投入", "")),
        "tech_field": demand.get("技术领域", ""),
        "demand_type": demand.get("需求类型", ""),
        "region": demand.get("所在地区", ""),
    }
    if include_detail:
        item["detail_summary"] = clip(demand.get("需求详情", ""), 260)
    return item


def build_user_text(data: dict, fields: tuple[str, ...]) -> str:
    return " ".join(clean_text(data.get(field, "")) for field in fields)


def score_demand(submission: dict, demand: dict) -> dict:
    user_all = build_user_text(
        submission,
        (
            "title",
            "tech_field",
            "application_scene",
            "summary",
            "advantages",
            "problem",
            "cooperation",
            "region",
            "extra_note",
            "attachment_note",
        ),
    )
    demand_all = demand.get("_search_text", "")
    demand_field = " ".join([demand.get("需求名称", ""), demand.get("技术领域", ""), demand.get("需求类型", "")])
    demand_scene = " ".join([demand.get("需求名称", ""), demand.get("需求详情", "")])
    demand_industry = " ".join(
        [demand.get("技术领域", ""), demand.get("需求类型", ""), demand.get("合作方式", ""), demand.get("需求详情", "")]
    )

    user_field = build_user_text(submission, ("tech_field", "title", "summary", "extra_note", "attachment_note"))
    user_scene = build_user_text(submission, ("application_scene", "summary", "problem", "extra_note", "attachment_note"))
    user_industry = build_user_text(submission, ("tech_field", "application_scene", "cooperation", "advantages", "extra_note", "attachment_note"))

    field_score = score_from_similarity(user_field, demand_field, baseline=45, scale=210)
    scene_score = score_from_similarity(user_scene, demand_scene, baseline=42, scale=190)
    industry_score = score_from_similarity(user_industry, demand_industry, baseline=42, scale=185)
    mature_score = maturity_score(clean_text(submission.get("maturity", "")), demand.get("需求详情", ""))

    tech_field = clean_text(submission.get("tech_field", ""))
    if tech_field and tech_field in demand.get("技术领域", ""):
        field_score = max(field_score, 86)
        industry_score = max(industry_score, 78)
    if tech_field and tech_field in demand_all:
        field_score = max(field_score, 76)
    region = clean_text(submission.get("region", ""))
    if region and region in demand.get("所在地区", ""):
        industry_score = min(100, industry_score + 8)

    total = round(field_score * 0.25 + scene_score * 0.30 + industry_score * 0.25 + mature_score * 0.20)
    total = max(0, min(100, total))
    keywords = shared_keywords(user_all, demand_all)
    reason = build_reason(submission, demand, keywords, total)
    suggestion = build_suggestion(demand, keywords)
    return {
        **sanitize_demand(demand, include_detail=True),
        "score": total,
        "dimensions": {
            "技术领域": field_score,
            "应用场景": scene_score,
            "产业方向": industry_score,
            "成熟度": mature_score,
        },
        "reason": reason,
        "suggestion": suggestion,
    }


def build_reason(submission: dict, demand: dict, keywords: list[str], score: int) -> str:
    tech = clean_text(demand.get("技术领域", "")).split(",")[0] or "相关技术领域"
    demand_type = clean_text(demand.get("需求类型", "")) or "技术需求"
    if keywords:
        keyword_text = "、".join(keywords[:5])
        lead = f"双方在{tech}方向存在关键词重合：{keyword_text}。"
    else:
        lead = f"系统根据需求名称、技术领域和需求详情综合判断，该需求与提交成果存在一定关联。"
    if score >= 85:
        level = "匹配度较高"
    elif score >= 70:
        level = "具备进一步沟通价值"
    else:
        level = "可作为备选需求继续核验"
    scene = clean_text(submission.get("application_scene", ""))
    scene_part = f"您描述的应用场景“{clip(scene, 38)}”与需求侧关注点接近。" if scene else ""
    return f"{lead}需求类型为{demand_type}，{scene_part}综合判断{level}。"


def build_suggestion(demand: dict, keywords: list[str]) -> str:
    demand_type = clean_text(demand.get("需求类型", "")) or "该需求"
    focus = "、".join(keywords[:3]) if keywords else "样品、指标和应用场景"
    return f"建议先围绕{focus}准备一页技术说明，明确可验证指标、已有样品或案例，再由平台人工审核后撮合双方沟通。"


def match_demands(store: DemandStore, submission: dict, limit: int = 8) -> list[dict]:
    user_text = build_user_text(
        submission,
        (
            "title",
            "tech_field",
            "application_scene",
            "summary",
            "advantages",
            "problem",
            "cooperation",
            "region",
            "extra_note",
            "attachment_note",
        ),
    )
    user_tokens = tokenize(user_text)
    scored_candidates: list[tuple[float, dict]] = []
    for demand in store.demands:
        base = cosine(user_tokens, demand.get("_tokens", Counter())) if user_tokens else 0.0
        tech_field = clean_text(submission.get("tech_field", ""))
        if tech_field and tech_field in demand.get("技术领域", ""):
            base += 0.45
        title = clean_text(submission.get("title", ""))
        if title and title in demand.get("_search_text", ""):
            base += 0.25
        if base > 0 or not user_tokens:
            scored_candidates.append((base, demand))

    if user_tokens:
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        candidates = [demand for _, demand in scored_candidates[:80]]
    else:
        candidates = store.demands[:80]

    results = [score_demand(submission, demand) for demand in candidates]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def chat_completions_url(base_url: str) -> str:
    base = clean_text(base_url).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def deepseek_chat(config: dict, messages: list[dict], *, max_tokens: int = 2600) -> str:
    body = {
        "model": config.get("model"),
        "messages": messages,
        "temperature": float(config.get("temperature", 0.2)),
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": config.get("thinking") or {"type": "disabled"},
    }
    if config.get("reasoning_effort"):
        body["reasoning_effort"] = config.get("reasoning_effort")

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        chat_completions_url(str(config.get("base_url", ""))),
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.get('api_key')}",
        },
    )
    timeout = int(config.get("timeout", 45) or 45)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"DeepSeek API 请求失败：{exc}") from exc
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek API 未返回 choices")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("DeepSeek API 返回内容为空")
    return content


def parse_json_object(text: str) -> dict:
    text = clean_text(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("AI 输出不是 JSON 对象")
    return data


def compact_submission(submission: dict) -> dict:
    return {
        "成果名称": clean_text(submission.get("title")),
        "技术领域": clean_text(submission.get("tech_field")),
        "应用场景": clean_text(submission.get("application_scene")),
        "技术成果摘要": clip(submission.get("summary", ""), 500),
        "核心优势": clip(submission.get("advantages", ""), 300),
        "解决问题": clip(submission.get("problem", ""), 300),
        "成熟度": clean_text(submission.get("maturity")),
        "合作方式": clean_text(submission.get("cooperation")),
        "所在地区": clean_text(submission.get("region")),
        "补充说明或相关链接": clip(submission.get("extra_note") or submission.get("attachment_note", ""), 300),
    }


def compact_candidate(result: dict) -> dict:
    return {
        "需求ID": result.get("demand_id", ""),
        "需求名称": result.get("name", ""),
        "技术领域": result.get("tech_field", ""),
        "需求类型": result.get("demand_type", ""),
        "所在地区": result.get("region", ""),
        "合作方式": result.get("cooperation_mode", ""),
        "意向投入": result.get("intended_price", ""),
        "需求详情摘要": clip(result.get("detail_summary", ""), 420),
        "本地匹配分": result.get("score", 0),
        "本地匹配理由": clip(result.get("reason", ""), 180),
    }


def build_ai_messages(submission: dict, local_results: list[dict]) -> list[dict]:
    system_prompt = """
你是 TechNexus 技术经理人平台的 AI 精排助手。你的任务是根据技术成果信息和候选技术需求，判断哪些需求最适合撮合。

评分维度固定为：
1. 技术领域：成果与需求所属技术方向是否一致。
2. 应用场景：成果能否解决需求中描述的场景或问题。
3. 产业方向：产业链、产品方向、合作方式是否接近。
4. 成熟度：成果成熟度是否满足需求侧研发、小试、中试、量产等阶段。

规则：
- 只能使用候选需求中的信息，不要编造不存在的需求。
- 不要输出需求方联系方式、手机号、联系人或外部详情页链接。
- 总分和四个维度分数均为 0 到 100 的整数。
- reason 要像技术经理人写给用户看的中文说明，具体但简洁。
- suggestion 要给出下一步撮合建议。
- 必须输出合法 json，格式如下：
{
  "results": [
    {
      "demand_id": "候选需求ID",
      "score": 88,
      "dimensions": {"技术领域": 90, "应用场景": 86, "产业方向": 88, "成熟度": 82},
      "reason": "中文匹配理由",
      "suggestion": "中文合作建议"
    }
  ]
}
"""
    payload = {
        "submission": compact_submission(submission),
        "candidates": [compact_candidate(item) for item in local_results],
    }
    user_prompt = "请对以下候选需求做 AI 精排，并只输出 json：\n" + json.dumps(payload, ensure_ascii=False)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def to_int_score(value: object, default: int = 0) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = default
    return max(0, min(100, number))


def merge_ai_results(local_results: list[dict], ai_payload: dict, config: dict) -> list[dict]:
    by_id = {item.get("demand_id"): item for item in local_results}
    merged: list[dict] = []
    seen: set[str] = set()
    for ai_item in ai_payload.get("results", []):
        if not isinstance(ai_item, dict):
            continue
        demand_id = clean_text(ai_item.get("demand_id"))
        if demand_id not in by_id or demand_id in seen:
            continue
        base = dict(by_id[demand_id])
        dimensions = ai_item.get("dimensions") if isinstance(ai_item.get("dimensions"), dict) else {}
        base["score"] = to_int_score(ai_item.get("score"), base.get("score", 0))
        base["dimensions"] = {
            "技术领域": to_int_score(dimensions.get("技术领域"), base.get("dimensions", {}).get("技术领域", 0)),
            "应用场景": to_int_score(dimensions.get("应用场景"), base.get("dimensions", {}).get("应用场景", 0)),
            "产业方向": to_int_score(dimensions.get("产业方向"), base.get("dimensions", {}).get("产业方向", 0)),
            "成熟度": to_int_score(dimensions.get("成熟度"), base.get("dimensions", {}).get("成熟度", 0)),
        }
        base["reason"] = clip(ai_item.get("reason") or base.get("reason", ""), 380)
        base["suggestion"] = clip(ai_item.get("suggestion") or base.get("suggestion", ""), 260)
        base["scoring_source"] = "DeepSeek AI"
        base["ai_model"] = clean_text(config.get("model", ""))
        merged.append(base)
        seen.add(demand_id)

    for item in local_results:
        if item.get("demand_id") not in seen:
            fallback = dict(item)
            fallback["scoring_source"] = "本地规则"
            merged.append(fallback)
    merged.sort(key=lambda item: item.get("score", 0), reverse=True)
    return merged


def refine_matches_with_ai(config: dict, submission: dict, local_results: list[dict]) -> tuple[list[dict], dict]:
    if not ai_is_configured(config):
        for item in local_results:
            item["scoring_source"] = "本地规则"
        return local_results, {"used_ai": False, "match_mode": "ai", "message": "未配置 DeepSeek API，已使用本地规则匹配。"}

    try:
        messages = build_ai_messages(submission, local_results)
        content = deepseek_chat(config, messages)
        ai_payload = parse_json_object(content)
        refined = merge_ai_results(local_results, ai_payload, config)
        return refined, {
            "used_ai": True,
            "match_mode": "ai",
            "message": "已使用 DeepSeek API 进行 AI 精排。",
            "model": clean_text(config.get("model", "")),
        }
    except Exception as exc:
        for item in local_results:
            item["scoring_source"] = "本地规则"
        return local_results, {
            "used_ai": False,
            "match_mode": "ai",
            "message": f"DeepSeek AI 精排失败，已自动退回本地规则：{exc}",
        }


def use_quick_match(local_results: list[dict]) -> tuple[list[dict], dict]:
    for item in local_results:
        item["scoring_source"] = "快速匹配"
    return local_results, {
        "used_ai": False,
        "match_mode": "quick",
        "message": "已使用快速匹配，仅通过本地需求库关键词和规则计算，未调用 DeepSeek API。",
    }


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_jsonl(name: str, payload: dict) -> None:
    ensure_data_dir()
    path = DATA_DIR / name
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(name: str, limit: int = 100) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.reverse()
    return rows[:limit]


def json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def using_postgres() -> bool:
    return DATABASE_URL.lower().startswith(("postgres://", "postgresql://"))


def db_prepare(sql: str) -> str:
    if using_postgres():
        return sql.replace("?", "%s")
    return sql


def db_execute(conn: object, sql: str, params: tuple | list = ()) -> object:
    return conn.execute(db_prepare(sql), tuple(params))


def first_value(row: object) -> object:
    if row is None:
        return 0
    if isinstance(row, dict):
        return next(iter(row.values()), 0)
    return row[0]


def db_connect() -> object:
    ensure_data_dir()
    if using_postgres():
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("线上数据库需要安装 psycopg：请先执行 pip install -r requirements.txt") from exc
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    ensure_data_dir()
    schema_sql = """
    CREATE TABLE IF NOT EXISTS submissions (
        submission_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        submission_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        submission_id TEXT,
        created_at TEXT NOT NULL,
        ai_meta_json TEXT NOT NULL,
        results_json TEXT NOT NULL,
        submission_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS intents (
        intent_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        status TEXT NOT NULL,
        agreement_version TEXT,
        submission_id TEXT,
        contact_json TEXT NOT NULL,
        message TEXT,
        attachment_note TEXT,
        selected_result_json TEXT NOT NULL,
        followup_note TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS intent_status_logs (
        log_id TEXT PRIMARY KEY,
        intent_id TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        note TEXT,
        operator TEXT,
        created_at TEXT NOT NULL
    );
    """
    with db_connect() as conn:
        if using_postgres():
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    db_execute(conn, statement)
        else:
            conn.executescript(schema_sql)
    migrate_jsonl_to_database()


def migrate_jsonl_to_database() -> None:
    submissions = read_jsonl("submissions.jsonl", limit=100000)
    matches = read_jsonl("matches.jsonl", limit=100000)
    intents = read_jsonl("intents.jsonl", limit=100000)
    if not submissions and not matches and not intents:
        return

    with db_connect() as conn:
        for item in reversed(submissions):
            db_execute(
                conn,
                """
                INSERT INTO submissions (submission_id, created_at, submission_json)
                VALUES (?, ?, ?)
                ON CONFLICT (submission_id) DO NOTHING
                """,
                (
                    clean_text(item.get("submission_id")) or uuid.uuid4().hex,
                    clean_text(item.get("created_at")) or now_iso(),
                    json_dumps(item.get("submission") or {}),
                ),
            )
        for item in reversed(matches):
            db_execute(
                conn,
                """
                INSERT INTO matches
                    (match_id, submission_id, created_at, ai_meta_json, results_json, submission_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (match_id) DO NOTHING
                """,
                (
                    clean_text(item.get("match_id")) or uuid.uuid4().hex,
                    clean_text(item.get("submission_id")),
                    clean_text(item.get("created_at")) or now_iso(),
                    json_dumps(item.get("ai_meta") or {}),
                    json_dumps(item.get("results") or []),
                    json_dumps(item.get("submission") or {}),
                ),
            )
        for item in reversed(intents):
            db_execute(
                conn,
                """
                INSERT INTO intents
                    (intent_id, created_at, updated_at, status, agreement_version, submission_id,
                     contact_json, message, attachment_note, selected_result_json, followup_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (intent_id) DO NOTHING
                """,
                (
                    clean_text(item.get("intent_id")) or uuid.uuid4().hex,
                    clean_text(item.get("created_at")) or now_iso(),
                    clean_text(item.get("updated_at")) or clean_text(item.get("created_at")) or now_iso(),
                    clean_text(item.get("status")) or "待审核",
                    clean_text(item.get("agreement_version")),
                    clean_text(item.get("submission_id")),
                    json_dumps(item.get("contact") or {}),
                    clean_text(item.get("message")),
                    clean_text(item.get("attachment_note")),
                    json_dumps(item.get("selected_result") or {}),
                    clean_text(item.get("followup_note")),
                ),
            )


def db_count(table: str) -> int:
    if table not in {"submissions", "matches", "intents"}:
        return 0
    with db_connect() as conn:
        return int(first_value(db_execute(conn, f"SELECT COUNT(*) FROM {table}").fetchone()))


def save_submission(record: dict) -> None:
    with db_connect() as conn:
        db_execute(
            conn,
            """
            INSERT INTO submissions (submission_id, created_at, submission_json)
            VALUES (?, ?, ?)
            ON CONFLICT (submission_id) DO UPDATE SET
                created_at = excluded.created_at,
                submission_json = excluded.submission_json
            """,
            (
                clean_text(record.get("submission_id")),
                clean_text(record.get("created_at")) or now_iso(),
                json_dumps(record.get("submission") or {}),
            ),
        )


def save_match(record: dict) -> None:
    with db_connect() as conn:
        db_execute(
            conn,
            """
            INSERT INTO matches
                (match_id, submission_id, created_at, ai_meta_json, results_json, submission_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (match_id) DO UPDATE SET
                submission_id = excluded.submission_id,
                created_at = excluded.created_at,
                ai_meta_json = excluded.ai_meta_json,
                results_json = excluded.results_json,
                submission_json = excluded.submission_json
            """,
            (
                clean_text(record.get("match_id")),
                clean_text(record.get("submission_id")),
                clean_text(record.get("created_at")) or now_iso(),
                json_dumps(record.get("ai_meta") or {}),
                json_dumps(record.get("results") or []),
                json_dumps(record.get("submission") or {}),
            ),
        )


def save_intent(intent: dict) -> None:
    timestamp = clean_text(intent.get("created_at")) or now_iso()
    with db_connect() as conn:
        db_execute(
            conn,
            """
            INSERT INTO intents
                (intent_id, created_at, updated_at, status, agreement_version, submission_id,
                 contact_json, message, attachment_note, selected_result_json, followup_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (intent_id) DO UPDATE SET
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                status = excluded.status,
                agreement_version = excluded.agreement_version,
                submission_id = excluded.submission_id,
                contact_json = excluded.contact_json,
                message = excluded.message,
                attachment_note = excluded.attachment_note,
                selected_result_json = excluded.selected_result_json,
                followup_note = excluded.followup_note
            """,
            (
                clean_text(intent.get("intent_id")),
                timestamp,
                clean_text(intent.get("updated_at")) or timestamp,
                clean_text(intent.get("status")) or "待审核",
                clean_text(intent.get("agreement_version")),
                clean_text(intent.get("submission_id")),
                json_dumps(intent.get("contact") or {}),
                clean_text(intent.get("message")),
                clean_text(intent.get("attachment_note")),
                json_dumps(intent.get("selected_result") or {}),
                clean_text(intent.get("followup_note")),
            ),
        )


def decode_json_field(value: object, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def list_intents(limit: int = 200, status: str = "", keyword: str = "") -> list[dict]:
    status = clean_text(status)
    keyword = clean_text(keyword).lower()
    clauses: list[str] = []
    params: list[str] = []
    if status and status != "全部":
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connect() as conn:
        rows = db_execute(
            conn,
            f"""
            SELECT * FROM intents
            {where}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        item["contact"] = decode_json_field(item.pop("contact_json", ""), {})
        item["selected_result"] = decode_json_field(item.pop("selected_result_json", ""), {})
        if keyword and keyword not in intent_search_text(item):
            continue
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


def row_to_intent(row: object) -> dict:
    item = dict(row)
    item["contact"] = decode_json_field(item.pop("contact_json", ""), {})
    item["selected_result"] = decode_json_field(item.pop("selected_result_json", ""), {})
    return item


def get_intent_detail(intent_id: str) -> dict:
    intent_id = clean_text(intent_id)
    with db_connect() as conn:
        row = db_execute(conn, "SELECT * FROM intents WHERE intent_id = ?", (intent_id,)).fetchone()
        if row is None:
            raise KeyError("未找到合作意向")
        logs = db_execute(
            conn,
            """
            SELECT old_status, new_status, note, operator, created_at
            FROM intent_status_logs
            WHERE intent_id = ?
            ORDER BY created_at DESC
            """,
            (intent_id,),
        ).fetchall()
    item = row_to_intent(row)
    item["status_logs"] = [dict(log) for log in logs]
    return item


def intent_search_text(item: dict) -> str:
    contact = item.get("contact") or {}
    selected = item.get("selected_result") or {}
    values = [
        item.get("created_at", ""),
        item.get("status", ""),
        item.get("message", ""),
        item.get("attachment_note", ""),
        item.get("followup_note", ""),
        contact.get("name", ""),
        contact.get("phone", ""),
        contact.get("company", ""),
        contact.get("technology_summary", ""),
        selected.get("name", ""),
        selected.get("demand_id", ""),
        selected.get("score", ""),
        selected.get("reason", ""),
        selected.get("tech_field", ""),
        selected.get("demand_type", ""),
        selected.get("region", ""),
    ]
    return " ".join(clean_text(value) for value in values).lower()


def export_intents_xlsx(items: list[dict]) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("缺少 openpyxl，无法导出 Excel。请先执行 pip install -r requirements.txt") from exc

    headers = [
        "创建时间",
        "当前状态",
        "姓名",
        "手机号",
        "单位",
        "技术成果摘要",
        "匹配需求",
        "匹配分数",
        "技术领域",
        "需求类型",
        "所在地区",
        "意向投入",
        "AI匹配理由",
        "用户留言",
        "补充说明/相关链接",
        "跟进备注",
        "合作意向ID",
        "需求ID",
    ]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "合作意向"
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for item in items:
        contact = item.get("contact") or {}
        selected = item.get("selected_result") or {}
        sheet.append(
            [
                item.get("created_at", ""),
                item.get("status", ""),
                contact.get("name", ""),
                contact.get("phone", ""),
                contact.get("company", ""),
                contact.get("technology_summary", ""),
                selected.get("name", ""),
                selected.get("score", ""),
                selected.get("tech_field", ""),
                selected.get("demand_type", ""),
                selected.get("region", ""),
                selected.get("intended_price", ""),
                selected.get("reason", ""),
                item.get("message", ""),
                item.get("attachment_note", ""),
                item.get("followup_note", ""),
                item.get("intent_id", ""),
                selected.get("demand_id", ""),
            ]
        )

    widths = {
        "A": 20,
        "B": 16,
        "C": 14,
        "D": 18,
        "E": 22,
        "F": 34,
        "G": 36,
        "H": 12,
        "I": 26,
        "J": 18,
        "K": 24,
        "L": 14,
        "M": 48,
        "N": 28,
        "O": 30,
        "P": 30,
        "Q": 34,
        "R": 24,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        for index in (4, 17, 18):
            row[index - 1].number_format = "@"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def update_intent_status(intent_id: str, status: str, note: str, operator: str) -> dict:
    intent_id = clean_text(intent_id)
    status = clean_text(status)
    if status not in INTENT_STATUSES:
        raise ValueError("状态不在允许范围内")
    with db_connect() as conn:
        row = db_execute(conn, "SELECT * FROM intents WHERE intent_id = ?", (intent_id,)).fetchone()
        if row is None:
            raise KeyError("未找到合作意向")
        old_status = clean_text(row["status"])
        timestamp = now_iso()
        db_execute(
            conn,
            """
            UPDATE intents
            SET status = ?, followup_note = ?, updated_at = ?
            WHERE intent_id = ?
            """,
            (status, clean_text(note), timestamp, intent_id),
        )
        db_execute(
            conn,
            """
            INSERT INTO intent_status_logs
                (log_id, intent_id, old_status, new_status, note, operator, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, intent_id, old_status, status, clean_text(note), clean_text(operator), timestamp),
        )
    updated = [item for item in list_intents(limit=1_000_000) if item.get("intent_id") == intent_id]
    return updated[0] if updated else {"intent_id": intent_id, "status": status}


def hash_password(password: str, salt: str | None = None, iterations: int = 220000) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hash_password(password, salt=salt, iterations=int(iterations_text)).split("$", 3)[3]
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def ensure_admin_config() -> dict:
    env_username = clean_text(os.getenv("TECHNEXUS_ADMIN_USERNAME")) or "admin"
    env_password = clean_text(os.getenv("TECHNEXUS_ADMIN_PASSWORD"))
    if env_password:
        ensure_data_dir()
        config = {
            "username": env_username,
            "password_hash": hash_password(env_password),
            "created_at": now_iso(),
            "note": "由环境变量 TECHNEXUS_ADMIN_PASSWORD 生成管理员配置。",
        }
        ADMIN_CONFIG_FILE.write_text(json_dumps(config), encoding="utf-8")
        return config

    if not ADMIN_CONFIG_FILE.exists():
        ensure_data_dir()
        username = env_username
        password = secrets.token_urlsafe(12)
        config = {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": now_iso(),
            "note": "首次自动生成管理员配置。请尽快运行 set_admin_password.py 修改密码。",
        }
        ADMIN_CONFIG_FILE.write_text(json_dumps(config), encoding="utf-8")
        if not os.getenv("TECHNEXUS_ADMIN_PASSWORD"):
            (DATA_DIR / "initial_admin_password.txt").write_text(
                f"TechNexus 初始管理员账号：{username}\nTechNexus 初始管理员密码：{password}\n请登录后尽快修改密码。\n",
                encoding="utf-8",
            )
        return config
    try:
        config = json.loads(ADMIN_CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    if not config.get("username") or not config.get("password_hash"):
        ensure_data_dir()
        username = env_username
        password = secrets.token_urlsafe(12)
        config = {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": now_iso(),
            "note": "管理员配置被修复。请尽快运行 set_admin_password.py 修改密码。",
        }
        ADMIN_CONFIG_FILE.write_text(json_dumps(config), encoding="utf-8")
        if not os.getenv("TECHNEXUS_ADMIN_PASSWORD"):
            (DATA_DIR / "initial_admin_password.txt").write_text(
                f"TechNexus 初始管理员账号：{username}\nTechNexus 初始管理员密码：{password}\n请登录后尽快修改密码。\n",
                encoding="utf-8",
            )
    return config


def login_matches_admin(username: str, password: str, config: dict) -> tuple[bool, str]:
    env_username = clean_text(os.getenv("TECHNEXUS_ADMIN_USERNAME")) or "admin"
    env_password = clean_text(os.getenv("TECHNEXUS_ADMIN_PASSWORD"))
    username = clean_text(username)
    password = clean_text(password)
    if env_password:
        return (
            username == env_username and hmac.compare_digest(password, env_password),
            env_username,
        )

    expected_user = clean_text(config.get("username"))
    expected_hash = clean_text(config.get("password_hash"))
    return (
        username == expected_user and verify_password(password, expected_hash),
        expected_user,
    )


def parse_cookie(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in (header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


class TechNexusHandler(BaseHTTPRequestHandler):
    store: DemandStore
    ai_config: dict
    admin_config: dict
    admin_sessions: dict[str, dict] = {}

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"", "/"}:
            self.send_static(STATIC_DIR / "index.html")
            return
        if parsed.path.startswith("/static/"):
            relative = parsed.path.removeprefix("/static/")
            self.send_static(STATIC_DIR / relative)
            return
        if parsed.path == "/api/admin/session":
            username = self.current_admin()
            self.send_json({"authenticated": bool(username), "username": username})
            return
        if parsed.path == "/api/stats":
            self.send_json(
                {
                    **self.store.stats(),
                    **ai_status(self.ai_config),
                    "intent_count": db_count("intents"),
                    "match_count": db_count("matches"),
                }
            )
            return
        if parsed.path == "/api/intents":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            status = query.get("status", [""])[0]
            keyword = query.get("keyword", [""])[0]
            self.send_json({"items": list_intents(200, status=status, keyword=keyword), "statuses": INTENT_STATUSES})
            return
        if parsed.path == "/api/intents/detail":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            intent_id = query.get("intent_id", [""])[0]
            try:
                self.send_json({"intent": get_intent_detail(intent_id)})
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
            return
        if parsed.path == "/api/intents/export":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            status = query.get("status", [""])[0]
            keyword = query.get("keyword", [""])[0]
            items = list_intents(10000, status=status, keyword=keyword)
            try:
                content = export_intents_xlsx(items)
            except RuntimeError as exc:
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            filename = f"TechNexus合作意向_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
            self.send_binary(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                    "Cache-Control": "no-store",
                },
            )
            return
        if parsed.path == "/api/demands":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            keyword = query.get("keyword", [""])[0]
            self.send_json({"items": self.store.search(keyword=keyword, limit=60)})
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "未找到页面")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/login":
            payload = self.read_json()
            username = clean_text(payload.get("username"))
            password = clean_text(payload.get("password"))
            ok, admin_username = login_matches_admin(username, password, self.admin_config)
            if not ok:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "账号或密码不正确")
                return
            token = secrets.token_urlsafe(32)
            self.admin_sessions[token] = {"username": admin_username, "expires_at": time.time() + SESSION_SECONDS}
            cookie = f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_SECONDS}; HttpOnly; SameSite=Lax"
            self.send_json({"ok": True, "username": admin_username}, headers={"Set-Cookie": cookie})
            return

        if parsed.path == "/api/admin/logout":
            token = self.current_session_token()
            if token:
                self.admin_sessions.pop(token, None)
            cookie = f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            self.send_json({"ok": True}, headers={"Set-Cookie": cookie})
            return

        if parsed.path == "/api/match":
            payload = self.read_json()
            match_mode = clean_text(payload.get("match_mode") or payload.get("_match_mode") or "ai").lower()
            if match_mode not in {"quick", "ai"}:
                match_mode = "ai"
            submission = {
                clean_text(k): clean_text(v)
                for k, v in payload.items()
                if clean_text(k) not in {"match_mode", "_match_mode"}
            }
            submission_id = uuid.uuid4().hex
            record = {
                "submission_id": submission_id,
                "created_at": now_iso(),
                "submission": submission,
            }
            local_results = match_demands(self.store, submission, limit=12)
            if match_mode == "quick":
                refined_results, ai_meta = use_quick_match(local_results)
            else:
                refined_results, ai_meta = refine_matches_with_ai(self.ai_config, submission, local_results)
            results = refined_results[:8]
            save_submission(record)
            save_match(
                {
                    "match_id": uuid.uuid4().hex,
                    "submission_id": submission_id,
                    "created_at": now_iso(),
                    "ai_meta": ai_meta,
                    "submission": submission,
                    "results": results,
                }
            )
            self.send_json(
                {
                    "submission_id": submission_id,
                    "results": results,
                    "ai_meta": ai_meta,
                    "match_mode": match_mode,
                    **self.store.stats(),
                    **ai_status(self.ai_config),
                    "intent_count": db_count("intents"),
                    "match_count": db_count("matches"),
                }
            )
            return

        if parsed.path == "/api/intents":
            payload = self.read_json()
            if not payload.get("agreement"):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "请先确认中介服务协议")
                return
            contact = payload.get("contact") or {}
            if not clean_text(contact.get("name")) or not clean_text(contact.get("phone")):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "请填写姓名和手机号，便于后续人工撮合")
                return
            selected = payload.get("selected_result") or {}
            intent = {
                "intent_id": uuid.uuid4().hex,
                "created_at": now_iso(),
                "status": "待审核",
                "agreement_version": AGREEMENT_VERSION,
                "submission_id": clean_text(payload.get("submission_id", "")),
                "contact": {clean_text(k): clean_text(v) for k, v in contact.items()},
                "message": clean_text(payload.get("message", "")),
                "attachment_note": clean_text(payload.get("extra_note") or payload.get("attachment_note", "")),
                "selected_result": selected,
                "updated_at": now_iso(),
                "followup_note": "",
            }
            save_intent(intent)
            self.send_json({"ok": True, "intent": intent})
            return

        if parsed.path == "/api/intents/status":
            operator = self.require_admin()
            if not operator:
                return
            payload = self.read_json()
            try:
                intent = update_intent_status(
                    clean_text(payload.get("intent_id")),
                    clean_text(payload.get("status")),
                    clean_text(payload.get("note")),
                    operator,
                )
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                return
            except ValueError as exc:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self.send_json({"ok": True, "intent": intent, "items": list_intents(200)})
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "未找到接口")

    def current_session_token(self) -> str:
        cookies = parse_cookie(self.headers.get("Cookie", ""))
        return clean_text(cookies.get(SESSION_COOKIE))

    def current_admin(self) -> str:
        token = self.current_session_token()
        if not token:
            return ""
        session = self.admin_sessions.get(token)
        if not session:
            return ""
        if float(session.get("expires_at", 0)) < time.time():
            self.admin_sessions.pop(token, None)
            return ""
        return clean_text(session.get("username"))

    def require_admin(self) -> str:
        username = self.current_admin()
        if not username:
            self.send_error_json(HTTPStatus.UNAUTHORIZED, "请先登录后台")
            return ""
        return username

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def send_json(
        self,
        payload: dict,
        status: HTTPStatus = HTTPStatus.OK,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"ok": False, "message": message}, status=status)

    def send_binary(
        self,
        content: bytes,
        *,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def send_static(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if not str(resolved).startswith(str(STATIC_DIR.resolve())) or not resolved.exists() or not resolved.is_file():
                self.send_error_json(HTTPStatus.NOT_FOUND, "未找到静态文件")
                return
            content = resolved.read_bytes()
        except OSError:
            self.send_error_json(HTTPStatus.NOT_FOUND, "未找到静态文件")
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif resolved.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif resolved.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run(host: str, port: int, open_browser: bool) -> None:
    init_database()
    admin_config = ensure_admin_config()
    store = DemandStore(DEMANDS_FILE)
    store.load()
    ai_config = load_ai_config()
    TechNexusHandler.store = store
    TechNexusHandler.ai_config = ai_config
    TechNexusHandler.admin_config = admin_config
    server = ThreadingHTTPServer((host, port), TechNexusHandler)
    url = f"http://{host}:{port}/"
    print(f"TechNexus 技术经理人试用版已启动：{url}")
    print(f"已读取需求库：{len(store.demands)} 条")
    print(f"匹配模式：{ai_status(ai_config)['ai_mode']}")
    print(f"后台管理员账号：{admin_config.get('username')}")
    print("按 Ctrl+C 可停止服务。")
    if open_browser:
        time.sleep(0.4)
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="TechNexus 技术经理人本地网页试用版")
    default_port = int(os.getenv("PORT") or os.getenv("TECHNEXUS_PORT") or 8010)
    parser.add_argument("--host", default=os.getenv("TECHNEXUS_HOST") or "127.0.0.1")
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()
    run(args.host, args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
