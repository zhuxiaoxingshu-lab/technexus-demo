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
PUBLIC_RESPONSE_PROMISE = "平台将在 3 个工作日内完成初步审核或联系。"
PROGRESS_STEPS = [
    ("submitted", "已提交合作意向", "已提交合作意向"),
    ("reviewing", "平台审核中", "平台审核中"),
    ("called_result_owner", "打电话核实成果", "已电话核实成果"),
    ("contacted_demander", "联系需求方", "已联系需求方"),
    ("wechat_contact", "发微信", "已微信沟通"),
    ("meeting_scheduled", "约线上会议", "已约线上会议"),
    ("agreement_sent", "发送协议", "已发送中介协议"),
    ("deal_recorded", "记录成交金额", "已记录合作结果"),
]
INTENT_STATUSES = [
    "待审核",
    "已联系成果方",
    "已联系需求方",
    "撮合中",
    "已签中介协议",
    "合作成功",
    "合作失败",
]
MATCH_FOLLOWUP_STATUSES = [
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

CONTACT_FIELDS = {"联系方式", "详情页链接"}
DEMAND_FIELDS = [
    "需求名称",
    "需求编号",
    "合作方式",
    "意向投入",
    "联系方式",
    "发布者",
    "需求详情",
    "技术领域",
    "需求类型",
    "所在地区",
    "需求ID",
    "详情页链接",
]
DEMAND_NAME_FIELD = DEMAND_FIELDS[0]
DEMAND_NO_FIELD = DEMAND_FIELDS[1]
DEMAND_COOP_FIELD = DEMAND_FIELDS[2]
DEMAND_PRICE_FIELD = DEMAND_FIELDS[3]
DEMAND_CONTACT_FIELD = DEMAND_FIELDS[4]
DEMAND_PUBLISHER_FIELD = DEMAND_FIELDS[5]
DEMAND_DETAIL_FIELD = DEMAND_FIELDS[6]
DEMAND_TECH_FIELD = DEMAND_FIELDS[7]
DEMAND_TYPE_FIELD = DEMAND_FIELDS[8]
DEMAND_REGION_FIELD = DEMAND_FIELDS[9]
DEMAND_ID_FIELD = DEMAND_FIELDS[10]
DEMAND_LINK_FIELD = DEMAND_FIELDS[11]

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


TECH_TAG_VOCAB = {
    "新材料": ["石墨烯", "陶瓷", "高分子", "复合材料", "膜材料", "碳材料", "金属材料", "纳米材料"],
    "半导体": ["半导体", "晶圆", "芯片", "封装", "先进封装", "光刻", "刻蚀", "沉积", "薄膜", "ALD", "CVD", "LPCVD", "SiC", "GaN"],
    "新能源": ["新能源", "锂电", "钠电", "储能", "光伏", "风电", "氢能", "燃料电池", "电解槽", "电池"],
    "生物医药": ["生物医药", "合成生物", "发酵", "酶法", "药物", "医疗器械", "诊断", "蛋白", "细胞"],
    "智能制造": ["智能制造", "工业自动化", "机器人", "机械臂", "传感器", "数控", "机床", "视觉检测", "工业软件"],
    "电子信息": ["电子信息", "射频", "光电子", "激光", "MEMS", "通信", "雷达"],
    "环保低碳": ["环保", "废水", "废气", "固废", "减排", "低碳", "节能", "循环利用", "光催化"],
    "高端装备": ["高端装备", "装备制造", "成套设备", "精密加工", "真空设备", "工艺装备"],
}

SCENE_TAG_VOCAB = {
    "半导体封装": ["半导体封装", "先进封装", "晶圆制造", "晶圆", "芯片封装", "热界面"],
    "储能器件": ["储能", "电池", "锂电", "钠电", "电极", "电芯", "电池包"],
    "能源装备": ["光伏", "风电", "氢能", "燃料电池", "能源器件", "逆变器"],
    "工业废水治理": ["废水", "污水", "染料废水", "工业废水", "吸附", "光催化"],
    "海工船舶": ["海洋工程", "船舶", "海工", "海上风电", "耐蚀"],
    "汽车零部件": ["汽车", "车规", "零部件", "新能源车", "汽车电子"],
    "医疗健康": ["医疗", "医药", "诊断", "临床", "健康"],
    "家居建材": ["家居", "建材", "定制家居", "涂层", "装饰材料"],
    "食品农业": ["农业", "育种", "食品", "菌菇", "种植", "饲料"],
    "工厂产线": ["产线", "工厂", "自动化", "包装机", "生产线", "制造现场"],
}

INDUSTRY_TAG_VOCAB = {
    "材料制备": ["材料制备", "合成", "复合材料", "配方", "改性", "制膜", "制粉"],
    "工艺开发": ["工艺开发", "工艺优化", "工艺定型", "工艺包", "小试", "中试", "放大"],
    "器件开发": ["器件", "组件", "模组", "单元", "电池组件", "封装器件"],
    "装备制造": ["装备", "设备", "机台", "反应器", "打包机", "产线设备"],
    "检测验证": ["检测", "测试", "表征", "验证", "可靠性", "评价"],
    "系统集成": ["系统集成", "控制系统", "管理系统", "算法集成", "软件平台"],
    "量产导入": ["量产", "产业化", "导入", "示范线", "工厂化", "批量"],
}

COOPERATION_TAG_VOCAB = {
    "技术转让": ["技术转让", "成果转让", "专利转让", "license"],
    "合作开发": ["合作开发", "联合开发", "协同开发", "共同开发"],
    "技术服务": ["技术服务", "委托开发", "技术咨询", "解决方案"],
    "委托研发": ["委托研发", "外包研发", "委托开发"],
}

MATURITY_LABELS = {
    1: "概念阶段",
    2: "实验室阶段",
    3: "小试阶段",
    4: "中试阶段",
    5: "量产阶段",
}


def dedupe_keep_order(values: list[str], limit: int = 0) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if limit and len(result) >= limit:
            break
    return result


def contains_alias(text: str, alias: str) -> bool:
    text = clean_text(text)
    alias = clean_text(alias)
    if not text or not alias:
        return False
    lowered = text.lower()
    alias_lower = alias.lower()
    if alias_lower.isascii():
        return alias_lower in lowered
    return alias in text


def extract_vocab_tags(text: str, vocab: dict[str, list[str]], *, limit: int = 6) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    scored: list[tuple[int, int, str]] = []
    for label, aliases in vocab.items():
        score = 0
        for alias in [label, *aliases]:
            if contains_alias(text, alias):
                score += 2 if alias == label else 1
        if score > 0:
            scored.append((score, len(label), label))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [label for _, _, label in scored[:limit]]


def maturity_label(text: str) -> str:
    level = maturity_level(text)
    if level is None:
        return ""
    return MATURITY_LABELS.get(level, "")


def extract_region_tokens(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts = re.split(r"[\/,，、\-\s]+", text)
    tokens = []
    for part in parts:
        token = clean_text(part)
        if len(token) >= 2:
            tokens.append(token)
    return dedupe_keep_order(tokens, 6)


def top_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = tokenize(text)
    ranked = sorted(tokens.items(), key=lambda item: (item[1], len(item[0]), item[0]), reverse=True)
    return [token for token, _ in ranked if len(token) <= 12][:limit]


def overlap_tags(left: list[str], right: list[str], *, limit: int = 6) -> list[str]:
    if not left or not right:
        return []
    right_set = set(right)
    shared = [item for item in left if item in right_set]
    return dedupe_keep_order(shared, limit)


def normalize_tag_payload(payload: dict | None) -> dict:
    payload = payload or {}
    return {
        "tech_tags": dedupe_keep_order(payload.get("tech_tags") or [], 6),
        "scene_tags": dedupe_keep_order(payload.get("scene_tags") or [], 6),
        "industry_tags": dedupe_keep_order(payload.get("industry_tags") or [], 6),
        "cooperation_tags": dedupe_keep_order(payload.get("cooperation_tags") or [], 4),
        "keywords": dedupe_keep_order(payload.get("keywords") or [], 10),
        "region_tokens": dedupe_keep_order(payload.get("region_tokens") or [], 6),
        "maturity_label": clean_text(payload.get("maturity_label", "")),
    }


def compact_tag_payload(payload: dict | None) -> dict:
    normalized = normalize_tag_payload(payload)
    return {
        "技术标签": normalized["tech_tags"],
        "应用标签": normalized["scene_tags"],
        "产业标签": normalized["industry_tags"],
        "合作标签": normalized["cooperation_tags"],
        "地区标签": normalized["region_tokens"],
        "成熟度标签": normalized["maturity_label"],
        "关键词": normalized["keywords"][:8],
    }


def tags_to_text(payload: dict | None) -> str:
    normalized = compact_tag_payload(payload)
    parts: list[str] = []
    for value in normalized.values():
        if isinstance(value, list):
            parts.extend(value)
        elif value:
            parts.append(value)
    return " ".join(parts)


def alias_lookup(vocab: dict[str, list[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for label, aliases in vocab.items():
        mapping[str(label).strip().lower()] = label
        for alias in aliases:
            mapping[str(alias).strip().lower()] = label
    return mapping


TECH_ALIAS_LOOKUP = alias_lookup(TECH_TAG_VOCAB)
SCENE_ALIAS_LOOKUP = alias_lookup(SCENE_TAG_VOCAB)
INDUSTRY_ALIAS_LOOKUP = alias_lookup(INDUSTRY_TAG_VOCAB)
COOP_ALIAS_LOOKUP = alias_lookup(COOPERATION_TAG_VOCAB)


def normalize_vocab_values(values: object, lookup: dict[str, str], vocab: dict[str, list[str]], *, limit: int) -> list[str]:
    result: list[str] = []
    items = values if isinstance(values, list) else [values]
    for raw in items:
        text = clean_text(raw)
        if not text:
            continue
        mapped = lookup.get(text.lower())
        if not mapped:
            guessed = extract_vocab_tags(text, vocab, limit=1)
            mapped = guessed[0] if guessed else text
        result.append(mapped)
    return dedupe_keep_order(result, limit)


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
        self.source_version = ""
        self._last_refresh_check = 0.0

    def load(self) -> None:
        database_version = database_demands_version()
        database_demands = load_demands_from_database()
        if database_demands:
            self.demands = database_demands
            self.loaded_at = now_iso()
            self.source_version = database_version
            return

        self.demands = load_demands_from_file(self.path)
        self.loaded_at = now_iso()
        try:
            stat = self.path.stat()
            self.source_version = f"file:{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            self.source_version = f"file:{self.loaded_at}"

    def reload(self) -> None:
        self.load()

    def refresh_if_changed(self, *, min_interval: float = 60.0) -> None:
        now = time.time()
        if now - self._last_refresh_check < min_interval:
            return
        self._last_refresh_check = now
        database_version = database_demands_version()
        if database_version and database_version != self.source_version:
            self.load()
            return
        if not database_version and self.path.exists():
            try:
                stat = self.path.stat()
                file_version = f"file:{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                return
            if file_version != self.source_version:
                self.load()

    def stats(self) -> dict:
        self.refresh_if_changed()
        return {"demand_count": len(self.demands), "loaded_at": self.loaded_at}

    def by_id(self, demand_id: str) -> dict | None:
        demand_id = clean_text(demand_id)
        for demand in self.demands:
            if demand.get("需求ID") == demand_id:
                return demand
        return None

    def search(self, keyword: str = "", limit: int = 50) -> list[dict]:
        items, _ = self.search_page(keyword=keyword, offset=0, limit=limit)
        return items

    def search_page(self, keyword: str = "", offset: int = 0, limit: int = 24) -> tuple[list[dict], int]:
        self.refresh_if_changed()
        keyword = clean_text(keyword)
        offset = max(0, int(offset or 0))
        limit = max(1, min(60, int(limit or 24)))
        if not keyword:
            matched_rows = self.demands
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
            matched_rows = [demand for _, demand in scored]
        total = len(matched_rows)
        rows = matched_rows[offset : offset + limit]
        return [sanitize_demand(row, include_detail=True) for row in rows], total


def prepare_demand_row(item: dict) -> dict:
    cleaned = {clean_text(k): clean_text(v) for k, v in item.items()}
    cleaned["_structured_tags"] = extract_demand_tags(cleaned)
    tag_text = tags_to_text(cleaned["_structured_tags"])
    if not cleaned.get("需求ID") and not cleaned.get("需求名称"):
        return {}
    search_text = " ".join(
        cleaned.get(field, "")
        for field in ("需求名称", "技术领域", "需求类型", "所在地区", "需求详情", "合作方式", "发布者")
    )
    cleaned["_search_text"] = " ".join([search_text, tag_text]).strip()
    cleaned["_tokens"] = tokenize(cleaned["_search_text"])
    return cleaned


def load_demands_from_file(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"未找到需求库文件：{path}")
    demands: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            cleaned = prepare_demand_row(item)
            if not cleaned:
                continue
            demands.append(cleaned)
    return demands


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
        "publisher": demand.get("发布者", ""),
    }
    if include_detail:
        item["detail_summary"] = clip(demand.get("需求详情", ""), 260)
    return item


def admin_demand_payload(demand: dict) -> dict:
    item = sanitize_demand(demand, include_detail=True)
    item.update(
        {
            "publisher": clean_text(demand.get("发布者")),
            "contact": clean_text(demand.get("联系方式")),
            "source_url": clean_text(demand.get("详情页链接")),
            "full_detail": clean_text(demand.get("需求详情")),
        }
    )
    return item


def build_user_text(data: dict, fields: tuple[str, ...]) -> str:
    return " ".join(clean_text(data.get(field, "")) for field in fields)


def extract_submission_tags_local(submission: dict) -> dict:
    tech_text = build_user_text(submission, ("tech_field", "title", "summary", "advantages", "problem", "extra_note", "attachment_note"))
    scene_text = build_user_text(submission, ("application_scene", "summary", "problem", "extra_note", "attachment_note"))
    industry_text = build_user_text(submission, ("tech_field", "application_scene", "summary", "cooperation", "advantages", "extra_note", "attachment_note"))
    cooperation_text = build_user_text(submission, ("cooperation", "summary", "extra_note", "attachment_note"))
    full_text = build_user_text(
        submission,
        ("title", "tech_field", "application_scene", "summary", "advantages", "problem", "cooperation", "region", "extra_note", "attachment_note"),
    )
    return normalize_tag_payload(
        {
            "tech_tags": extract_vocab_tags(tech_text, TECH_TAG_VOCAB, limit=6),
            "scene_tags": extract_vocab_tags(scene_text, SCENE_TAG_VOCAB, limit=6),
            "industry_tags": extract_vocab_tags(industry_text, INDUSTRY_TAG_VOCAB, limit=6),
            "cooperation_tags": extract_vocab_tags(cooperation_text, COOPERATION_TAG_VOCAB, limit=4),
            "keywords": top_keywords(full_text, 10),
            "region_tokens": extract_region_tokens(clean_text(submission.get("region", ""))),
            "maturity_label": maturity_label(clean_text(submission.get("maturity", ""))),
        }
    )


def extract_demand_tags(demand: dict) -> dict:
    tech_text = " ".join([demand.get(DEMAND_NAME_FIELD, ""), demand.get(DEMAND_TECH_FIELD, ""), demand.get(DEMAND_DETAIL_FIELD, "")])
    scene_text = " ".join([demand.get(DEMAND_NAME_FIELD, ""), demand.get(DEMAND_DETAIL_FIELD, "")])
    industry_text = " ".join([demand.get(DEMAND_TECH_FIELD, ""), demand.get(DEMAND_TYPE_FIELD, ""), demand.get(DEMAND_COOP_FIELD, ""), demand.get(DEMAND_DETAIL_FIELD, "")])
    all_text = " ".join(
        [
            demand.get(DEMAND_NAME_FIELD, ""),
            demand.get(DEMAND_TECH_FIELD, ""),
            demand.get(DEMAND_TYPE_FIELD, ""),
            demand.get(DEMAND_REGION_FIELD, ""),
            demand.get(DEMAND_COOP_FIELD, ""),
            demand.get(DEMAND_DETAIL_FIELD, ""),
        ]
    )
    return normalize_tag_payload(
        {
            "tech_tags": extract_vocab_tags(tech_text, TECH_TAG_VOCAB, limit=6),
            "scene_tags": extract_vocab_tags(scene_text, SCENE_TAG_VOCAB, limit=6),
            "industry_tags": extract_vocab_tags(industry_text, INDUSTRY_TAG_VOCAB, limit=6),
            "cooperation_tags": extract_vocab_tags(demand.get(DEMAND_COOP_FIELD, ""), COOPERATION_TAG_VOCAB, limit=4),
            "keywords": top_keywords(all_text, 12),
            "region_tokens": extract_region_tokens(demand.get(DEMAND_REGION_FIELD, "")),
            "maturity_label": maturity_label(demand.get(DEMAND_DETAIL_FIELD, "")),
        }
    )


def merge_tag_profiles(*profiles: dict | None) -> dict:
    merged = normalize_tag_payload({})
    for profile in profiles:
        current = normalize_tag_payload(profile)
        for field in ("tech_tags", "scene_tags", "industry_tags", "cooperation_tags", "keywords", "region_tokens"):
            max_limit = 10 if field == "keywords" else 6
            merged[field] = dedupe_keep_order([*merged[field], *current[field]], max_limit)
        if not merged["maturity_label"] and current["maturity_label"]:
            merged["maturity_label"] = current["maturity_label"]
    return merged


def maturity_distance_score(left_label: str, right_label: str) -> int:
    reverse = {value: key for key, value in MATURITY_LABELS.items()}
    left = reverse.get(clean_text(left_label))
    right = reverse.get(clean_text(right_label))
    if not left or not right:
        return 0
    return max(0, 16 - abs(left - right) * 6)


def recall_score_demand(submission: dict, demand: dict, tags: dict) -> float:
    user_text = build_user_text(
        submission,
        ("title", "tech_field", "application_scene", "summary", "advantages", "problem", "cooperation", "region", "extra_note", "attachment_note"),
    )
    user_tokens = tokenize(" ".join([user_text, tags_to_text(tags)]))
    lexical = cosine(user_tokens, demand.get("_tokens", Counter())) if user_tokens else 0.0
    demand_tags = normalize_tag_payload(demand.get("_structured_tags"))
    tech_overlap = overlap_tags(tags.get("tech_tags", []), demand_tags.get("tech_tags", []))
    scene_overlap = overlap_tags(tags.get("scene_tags", []), demand_tags.get("scene_tags", []))
    industry_overlap = overlap_tags(tags.get("industry_tags", []), demand_tags.get("industry_tags", []))
    cooperation_overlap = overlap_tags(tags.get("cooperation_tags", []), demand_tags.get("cooperation_tags", []))
    keyword_overlap = overlap_tags(tags.get("keywords", []), demand_tags.get("keywords", []), limit=8)
    region_overlap = overlap_tags(tags.get("region_tokens", []), demand_tags.get("region_tokens", []), limit=4)
    score = lexical
    if tech_overlap:
        score += 0.55 + len(tech_overlap) * 0.18
    if scene_overlap:
        score += 0.45 + len(scene_overlap) * 0.16
    if industry_overlap:
        score += 0.32 + len(industry_overlap) * 0.12
    if cooperation_overlap:
        score += 0.18 + len(cooperation_overlap) * 0.06
    if keyword_overlap:
        score += min(0.32, len(keyword_overlap) * 0.05)
    if region_overlap:
        score += 0.12
    score += maturity_distance_score(tags.get("maturity_label", ""), demand_tags.get("maturity_label", "")) / 100.0
    title = clean_text(submission.get("title", ""))
    if title and title in demand.get("_search_text", ""):
        score += 0.22

    tech_field = clean_text(submission.get("tech_field", ""))
    if tech_field and tech_field in demand.get(DEMAND_TECH_FIELD, ""):
        score += 0.28
    return score


def score_demand(submission: dict, demand: dict, *, tags: dict | None = None, recall_score: float = 0.0) -> dict:
    tags = normalize_tag_payload(tags or extract_submission_tags_local(submission))
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
    demand_tags = normalize_tag_payload(demand.get("_structured_tags"))
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

    tech_overlap = overlap_tags(tags.get("tech_tags", []), demand_tags.get("tech_tags", []))
    scene_overlap = overlap_tags(tags.get("scene_tags", []), demand_tags.get("scene_tags", []))
    industry_overlap = overlap_tags(tags.get("industry_tags", []), demand_tags.get("industry_tags", []))
    cooperation_overlap = overlap_tags(tags.get("cooperation_tags", []), demand_tags.get("cooperation_tags", []))
    region_overlap = overlap_tags(tags.get("region_tokens", []), demand_tags.get("region_tokens", []), limit=4)
    tag_keywords = overlap_tags(tags.get("keywords", []), demand_tags.get("keywords", []), limit=8)

    if tech_overlap:
        field_score = max(field_score, min(100, 72 + len(tech_overlap) * 10))
    if scene_overlap:
        scene_score = max(scene_score, min(100, 70 + len(scene_overlap) * 9))
    if industry_overlap:
        industry_score = max(industry_score, min(100, 68 + len(industry_overlap) * 8))
    if cooperation_overlap:
        industry_score = min(100, industry_score + 6)
    if region_overlap:
        industry_score = min(100, industry_score + 6)
    mature_score = min(100, mature_score + maturity_distance_score(tags.get("maturity_label", ""), demand_tags.get("maturity_label", "")))

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
    if recall_score > 0:
        total += min(8, round(recall_score * 4))
    total = max(0, min(100, total))
    keywords = dedupe_keep_order([*tech_overlap, *scene_overlap, *industry_overlap, *tag_keywords], 8) or shared_keywords(user_all, demand_all)
    matched_tags = {
        "tech_tags": tech_overlap,
        "scene_tags": scene_overlap,
        "industry_tags": industry_overlap,
        "cooperation_tags": cooperation_overlap,
        "keywords": keywords,
    }
    reason = build_reason(submission, demand, matched_tags, total)
    suggestion = build_suggestion(demand, matched_tags)
    return {
        **sanitize_demand(demand, include_detail=True),
        "score": total,
        "structured_tags": compact_tag_payload(demand_tags),
        "matched_tags": compact_tag_payload(matched_tags),
        "recall_score": round(recall_score, 4),
        "dimensions": {
            "技术领域": field_score,
            "应用场景": scene_score,
            "产业方向": industry_score,
            "成熟度": mature_score,
        },
        "reason": reason,
        "suggestion": suggestion,
    }


def build_reason(submission: dict, demand: dict, matched_tags: dict, score: int) -> str:
    tech = clean_text(demand.get("技术领域", "")).split(",")[0] or "相关技术领域"
    demand_type = clean_text(demand.get("需求类型", "")) or "技术需求"
    summary_tags = dedupe_keep_order(
        [
            *matched_tags.get("tech_tags", []),
            *matched_tags.get("scene_tags", []),
            *matched_tags.get("industry_tags", []),
            *matched_tags.get("keywords", []),
        ],
        5,
    )
    if summary_tags:
        keywords = summary_tags
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


def build_suggestion(demand: dict, matched_tags: dict) -> str:
    keywords = dedupe_keep_order(
        [
            *matched_tags.get("tech_tags", []),
            *matched_tags.get("scene_tags", []),
            *matched_tags.get("industry_tags", []),
            *matched_tags.get("keywords", []),
        ],
        3,
    )
    demand_type = clean_text(demand.get("需求类型", "")) or "该需求"
    focus = "、".join(keywords[:3]) if keywords else "样品、指标和应用场景"
    return f"建议先围绕{focus}准备一页技术说明，明确可验证指标、已有样品或案例，再由平台人工审核后撮合双方沟通。"


def match_demands(store: DemandStore, submission: dict, limit: int = 8, candidate_limit: int = 180, tags: dict | None = None) -> list[dict]:
    store.refresh_if_changed()
    tags = normalize_tag_payload(tags or extract_submission_tags_local(submission))
    scored_candidates: list[tuple[float, dict]] = []
    for demand in store.demands:
        base = recall_score_demand(submission, demand, tags)
        tech_field = clean_text(submission.get("tech_field", ""))
        if tech_field and tech_field in demand.get("技术领域", ""):
            base += 0.45
        title = clean_text(submission.get("title", ""))
        if title and title in demand.get("_search_text", ""):
            base += 0.25
        if base > 0 or not any(tags.values()):
            scored_candidates.append((base, demand))

    if any(tags.values()):
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        candidates = scored_candidates[:candidate_limit]
    else:
        candidates = [(0.0, demand) for demand in store.demands[:candidate_limit]]

    results = [score_demand(submission, demand, tags=tags, recall_score=base) for base, demand in candidates]
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
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("AI 输出为空")

    candidates: list[str] = [raw]
    fenced = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    if fenced and fenced not in candidates:
        candidates.append(fenced)

    start = fenced.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escaped = False
        end = -1
        for index, char in enumerate(fenced[start:], start):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end > start:
            balanced = fenced[start : end + 1]
            cleaned = re.sub(r",\s*([}\]])", r"\1", balanced)
            cleaned = cleaned.replace("\ufeff", "")
            cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
            if balanced not in candidates:
                candidates.append(balanced)
            if cleaned not in candidates:
                candidates.append(cleaned)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError as exc:
            last_error = exc
    else:
        raise last_error or ValueError("AI 输出不是合法 JSON")

    if not isinstance(data, dict):
        raise ValueError("AI 输出不是 JSON 对象")
    return data


def build_json_repair_messages(text: str, task_name: str) -> list[dict]:
    system_prompt = (
        "你是 JSON 修复助手。"
        "请把用户提供的文本修复成一个合法 JSON 对象。"
        "不要解释，不要补充无关字段，不要输出 Markdown 代码块。"
    )
    user_prompt = json.dumps(
        {
            "task": task_name,
            "input": str(text or ""),
        },
        ensure_ascii=False,
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_json_object_with_ai(config: dict, text: str, *, task_name: str) -> dict:
    try:
        return parse_json_object(text)
    except Exception as first_error:
        if not ai_is_configured(config):
            raise
        repair_content = deepseek_chat(config, build_json_repair_messages(text, task_name), max_tokens=3200)
        try:
            return parse_json_object(repair_content)
        except Exception as second_error:
            raise RuntimeError(
                f"{task_name} JSON 解析失败：{first_error}; 修复后仍失败：{second_error}"
            ) from second_error


def build_tag_extraction_messages(submission: dict, local_tags: dict) -> list[dict]:
    vocab_payload = {
        "技术标签候选": list(TECH_TAG_VOCAB.keys()),
        "应用标签候选": list(SCENE_TAG_VOCAB.keys()),
        "产业标签候选": list(INDUSTRY_TAG_VOCAB.keys()),
        "合作标签候选": list(COOPERATION_TAG_VOCAB.keys()),
        "成熟度标签候选": list(MATURITY_LABELS.values()),
    }
    system_prompt = (
        "你是 TechNexus 的标签抽取助手。"
        "请先阅读技术成果描述，再输出结构化标签。"
        "优先使用提供的标准标签候选，不要编造不存在的行业标签。"
        "只输出合法 JSON。"
    )
    user_payload = {
        "submission": compact_submission(submission),
        "local_seed_tags": compact_tag_payload(local_tags),
        "standard_vocab": vocab_payload,
        "required_json_schema": {
            "技术标签": ["最多6个"],
            "应用标签": ["最多6个"],
            "产业标签": ["最多6个"],
            "合作标签": ["最多4个"],
            "成熟度标签": "从候选中选1个，无法判断可留空",
            "关键词": ["最多8个"],
        },
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def normalize_ai_tag_payload(payload: dict) -> dict:
    return normalize_tag_payload(
        {
            "tech_tags": normalize_vocab_values(payload.get("技术标签"), TECH_ALIAS_LOOKUP, TECH_TAG_VOCAB, limit=6),
            "scene_tags": normalize_vocab_values(payload.get("应用标签"), SCENE_ALIAS_LOOKUP, SCENE_TAG_VOCAB, limit=6),
            "industry_tags": normalize_vocab_values(payload.get("产业标签"), INDUSTRY_ALIAS_LOOKUP, INDUSTRY_TAG_VOCAB, limit=6),
            "cooperation_tags": normalize_vocab_values(payload.get("合作标签"), COOP_ALIAS_LOOKUP, COOPERATION_TAG_VOCAB, limit=4),
            "keywords": dedupe_keep_order(payload.get("关键词") or [], 8),
            "region_tokens": [],
            "maturity_label": clean_text(payload.get("成熟度标签", "")),
        }
    )


def extract_tags_with_ai(config: dict, submission: dict, local_tags: dict) -> tuple[dict, dict]:
    local_tags = normalize_tag_payload(local_tags)
    if not ai_is_configured(config):
        return local_tags, {
            "used_ai": False,
            "source": "local",
            "local_tags": compact_tag_payload(local_tags),
            "merged_tags": compact_tag_payload(local_tags),
            "message": "未配置 DeepSeek API，已使用本地标签抽取。",
        }
    try:
        content = deepseek_chat(config, build_tag_extraction_messages(submission, local_tags), max_tokens=1200)
        ai_payload = parse_json_object_with_ai(config, content, task_name="标签抽取")
        ai_tags = normalize_ai_tag_payload(ai_payload)
        merged_tags = merge_tag_profiles(local_tags, ai_tags)
        return merged_tags, {
            "used_ai": True,
            "source": "local+ai",
            "local_tags": compact_tag_payload(local_tags),
            "ai_tags": compact_tag_payload(ai_tags),
            "merged_tags": compact_tag_payload(merged_tags),
            "message": "已使用 DeepSeek 完成标签抽取。",
        }
    except Exception as exc:
        return local_tags, {
            "used_ai": False,
            "source": "local",
            "local_tags": compact_tag_payload(local_tags),
            "merged_tags": compact_tag_payload(local_tags),
            "message": f"AI 标签抽取失败，已退回本地标签：{exc}",
        }


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


def build_ai_messages(submission: dict, local_results: list[dict], tag_profile: dict | None = None) -> list[dict]:
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
        "structured_tags": compact_tag_payload(tag_profile),
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
        base["scoring_source"] = "AI标签 + DeepSeek精排"
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


def refine_matches_with_ai(
    config: dict,
    submission: dict,
    local_results: list[dict],
    *,
    tag_profile: dict | None = None,
    tag_meta: dict | None = None,
) -> tuple[list[dict], dict]:
    if not ai_is_configured(config):
        for item in local_results:
            item["scoring_source"] = "本地规则"
        return local_results, {"used_ai": False, "match_mode": "ai", "message": "未配置 DeepSeek API，已使用本地规则匹配。"}

    try:
        messages = build_ai_messages(submission, local_results, tag_profile)
        content = deepseek_chat(config, messages)
        ai_payload = parse_json_object_with_ai(config, content, task_name="AI精排")
        refined = merge_ai_results(local_results, ai_payload, config)
        ai_ranked_count = sum(1 for item in refined if item.get("scoring_source") == "AI标签 + DeepSeek精排")
        if ai_ranked_count == 0:
            for item in local_results:
                item["scoring_source"] = "本地规则"
            return local_results, {
                "used_ai": False,
                "match_mode": "ai",
                "message": "已使用 DeepSeek 完成标签抽取，但精排结果未命中候选需求，已退回本地规则排序。",
                "model": clean_text(config.get("model", "")),
                "tag_extraction": tag_meta or {},
                "structured_tags": compact_tag_payload(tag_profile),
            }
        return refined, {
            "used_ai": True,
            "match_mode": "ai",
            "message": "已使用 DeepSeek API 进行 AI 精排。",
            "model": clean_text(config.get("model", "")),
            "tag_extraction": tag_meta or {},
            "structured_tags": compact_tag_payload(tag_profile),
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
        item["scoring_source"] = "结构化快速匹配"
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


def demand_public_payload(row: dict) -> dict:
    return {field: clean_text(row.get(field)) for field in DEMAND_FIELDS}


def database_demands_version() -> str:
    try:
        with db_connect() as conn:
            row = db_execute(conn, "SELECT COUNT(*) AS count, MAX(updated_at) AS updated_at FROM demands").fetchone()
    except Exception:
        return ""
    if not row:
        return ""
    item = dict(row)
    count = int(item.get("count") or 0)
    if count <= 0:
        return ""
    return f"db:{count}:{clean_text(item.get('updated_at'))}"


def load_demands_from_database() -> list[dict]:
    try:
        with db_connect() as conn:
            rows = db_execute(
                conn,
                """
                SELECT demand_json
                FROM demands
                ORDER BY updated_at DESC, first_seen_at DESC
                """,
            ).fetchall()
    except Exception:
        return []

    demands: list[dict] = []
    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(clean_text(item.get("demand_json")))
        except json.JSONDecodeError:
            continue
        cleaned = prepare_demand_row(payload if isinstance(payload, dict) else {})
        if cleaned:
            demands.append(cleaned)
    return demands


def existing_demand_ids() -> set[str]:
    try:
        with db_connect() as conn:
            rows = db_execute(conn, "SELECT demand_id FROM demands").fetchall()
            return {clean_text(dict(row).get("demand_id")) for row in rows if clean_text(dict(row).get("demand_id"))}
    except Exception:
        return set()


def save_demand_rows_to_database(rows: list[dict], *, update_existing: bool = True) -> dict:
    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    timestamp = now_iso()
    inserted = 0
    updated = 0
    skipped = 0
    with db_connect() as conn:
        for raw in rows:
            row = demand_public_payload(raw)
            demand_id = clean_text(row.get("需求ID"))
            name = clean_text(row.get("需求名称"))
            if not demand_id or not name:
                skipped += 1
                continue
            if not update_existing:
                cursor = db_execute(
                    conn,
                    """
                    INSERT INTO demands (
                        demand_id, demand_no, name, demand_json, source, source_url, first_seen_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (demand_id) DO NOTHING
                    """,
                    (
                        demand_id,
                        row.get("需求编号", ""),
                        name,
                        json_dumps(row),
                        "jstec",
                        row.get("详情页链接", ""),
                        timestamp,
                        timestamp,
                    ),
                )
                if getattr(cursor, "rowcount", 0):
                    inserted += 1
                else:
                    skipped += 1
                continue

            existing = db_execute(conn, "SELECT 1 FROM demands WHERE demand_id = ?", (demand_id,)).fetchone()
            db_execute(
                conn,
                """
                INSERT INTO demands (
                    demand_id, demand_no, name, demand_json, source, source_url, first_seen_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (demand_id) DO UPDATE SET
                    demand_no = excluded.demand_no,
                    name = excluded.name,
                    demand_json = excluded.demand_json,
                    source = excluded.source,
                    source_url = excluded.source_url,
                    updated_at = excluded.updated_at
                """,
                (
                    demand_id,
                    row.get("需求编号", ""),
                    name,
                    json_dumps(row),
                    "jstec",
                    row.get("详情页链接", ""),
                    timestamp,
                    timestamp,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def migrate_demands_file_to_database() -> None:
    if not DEMANDS_FILE.exists():
        return
    try:
        if existing_demand_ids():
            return
        rows = [demand_public_payload(row) for row in load_demands_from_file(DEMANDS_FILE)]
        save_demand_rows_to_database(rows, update_existing=False)
    except Exception as exc:
        print(f"需求库文件迁移到数据库失败，仍将使用本地文件：{exc}")


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

    CREATE TABLE IF NOT EXISTS match_followups (
        followup_id TEXT PRIMARY KEY,
        match_id TEXT NOT NULL,
        submission_id TEXT,
        demand_id TEXT NOT NULL,
        status TEXT NOT NULL,
        contact_note TEXT DEFAULT '',
        project_progress TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (match_id, demand_id)
    );

    CREATE TABLE IF NOT EXISTS demands (
        demand_id TEXT PRIMARY KEY,
        demand_no TEXT,
        name TEXT NOT NULL,
        demand_json TEXT NOT NULL,
        source TEXT DEFAULT 'jstec',
        source_url TEXT,
        first_seen_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_demands_updated_at ON demands (updated_at);
    CREATE INDEX IF NOT EXISTS idx_match_followups_match_id ON match_followups (match_id);
    """
    with db_connect() as conn:
        if using_postgres():
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    db_execute(conn, statement)
        else:
            conn.executescript(schema_sql)
    migrate_database_schema()
    migrate_jsonl_to_database()
    migrate_demands_file_to_database()


def column_exists(conn: object, table: str, column: str) -> bool:
    if using_postgres():
        row = db_execute(
            conn,
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            LIMIT 1
            """,
            (table, column),
        ).fetchone()
        return row is not None
    rows = db_execute(conn, f"PRAGMA table_info({table})").fetchall()
    return any(dict(row).get("name") == column for row in rows)


def add_column_if_missing(conn: object, table: str, column: str, definition: str) -> None:
    if column_exists(conn, table, column):
        return
    db_execute(conn, f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_database_schema() -> None:
    with db_connect() as conn:
        add_column_if_missing(conn, "intents", "query_code", "TEXT")
        add_column_if_missing(conn, "intents", "public_note", "TEXT DEFAULT ''")
        add_column_if_missing(conn, "intents", "progress_json", "TEXT DEFAULT ''")
        add_column_if_missing(conn, "intents", "deal_amount", "TEXT DEFAULT ''")
        add_column_if_missing(conn, "intents", "deal_note", "TEXT DEFAULT ''")

        rows = db_execute(
            conn,
            """
            SELECT intent_id, created_at, query_code, progress_json, public_note
            FROM intents
            """,
        ).fetchall()
        for row in rows:
            item = dict(row)
            updates: list[str] = []
            params: list[str] = []
            query_code = clean_text(item.get("query_code"))
            if not query_code:
                query_code = generate_unique_query_code(conn)
                updates.append("query_code = ?")
                params.append(query_code)
            if not clean_text(item.get("progress_json")):
                updates.append("progress_json = ?")
                params.append(json_dumps(default_progress(item.get("created_at"))))
            if not clean_text(item.get("public_note")):
                updates.append("public_note = ?")
                params.append(f"已收到合作意向，{PUBLIC_RESPONSE_PROMISE}")
            if updates:
                params.append(clean_text(item.get("intent_id")))
                db_execute(conn, f"UPDATE intents SET {', '.join(updates)} WHERE intent_id = ?", params)


def generate_query_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "TN-" + "".join(secrets.choice(alphabet) for _ in range(8))


def generate_unique_query_code(conn: object | None = None) -> str:
    own_conn = conn is None
    if own_conn:
        conn = db_connect()
    try:
        for _ in range(30):
            code = generate_query_code()
            row = db_execute(conn, "SELECT 1 FROM intents WHERE query_code = ?", (code,)).fetchone()
            if row is None:
                return code
    finally:
        if own_conn and conn is not None:
            conn.close()
    return "TN-" + uuid.uuid4().hex[:8].upper()


def default_progress(created_at: object = "") -> list[dict]:
    timestamp = clean_text(created_at) or now_iso()
    progress: list[dict] = []
    for key, label, public_label in PROGRESS_STEPS:
        done = key == "submitted"
        progress.append(
            {
                "key": key,
                "label": label,
                "public_label": public_label,
                "done": done,
                "updated_at": timestamp if done else "",
                "note": "",
                "public_note": "",
            }
        )
    return progress


def normalize_progress(value: object, created_at: object = "") -> list[dict]:
    raw_items: list[dict] = []
    if isinstance(value, list):
        raw_items = [item for item in value if isinstance(item, dict)]
    elif value:
        try:
            parsed = json.loads(str(value))
            if isinstance(parsed, list):
                raw_items = [item for item in parsed if isinstance(item, dict)]
        except json.JSONDecodeError:
            raw_items = []

    by_key = {clean_text(item.get("key")): item for item in raw_items}
    normalized = default_progress(created_at)
    for item in normalized:
        existing = by_key.get(item["key"]) or {}
        item["done"] = bool(existing.get("done", item["done"]))
        item["updated_at"] = clean_text(existing.get("updated_at")) or item["updated_at"]
        item["note"] = clean_text(existing.get("note"))
        item["public_note"] = clean_text(existing.get("public_note"))
    return normalized


def public_progress(progress: list[dict]) -> list[dict]:
    return [
        {
            "key": clean_text(item.get("key")),
            "label": clean_text(item.get("public_label") or item.get("label")),
            "done": bool(item.get("done")),
            "updated_at": clean_text(item.get("updated_at")),
            "public_note": clean_text(item.get("public_note")),
        }
        for item in progress
    ]


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
                     contact_json, message, attachment_note, selected_result_json, followup_note,
                     query_code, public_note, progress_json, deal_amount, deal_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    clean_text(item.get("query_code")) or generate_unique_query_code(conn),
                    clean_text(item.get("public_note")) or f"已收到合作意向，{PUBLIC_RESPONSE_PROMISE}",
                    json_dumps(normalize_progress(item.get("progress"), item.get("created_at"))),
                    clean_text(item.get("deal_amount")),
                    clean_text(item.get("deal_note")),
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
        query_code = clean_text(intent.get("query_code")) or generate_unique_query_code(conn)
        progress = normalize_progress(intent.get("progress") or intent.get("progress_json"), timestamp)
        db_execute(
            conn,
            """
            INSERT INTO intents
                (intent_id, created_at, updated_at, status, agreement_version, submission_id,
                 contact_json, message, attachment_note, selected_result_json, followup_note,
                 query_code, public_note, progress_json, deal_amount, deal_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                followup_note = excluded.followup_note,
                query_code = excluded.query_code,
                public_note = excluded.public_note,
                progress_json = excluded.progress_json,
                deal_amount = excluded.deal_amount,
                deal_note = excluded.deal_note
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
                query_code,
                clean_text(intent.get("public_note")) or f"已收到合作意向，{PUBLIC_RESPONSE_PROMISE}",
                json_dumps(progress),
                clean_text(intent.get("deal_amount")),
                clean_text(intent.get("deal_note")),
            ),
        )


def decode_json_field(value: object, default: object) -> object:
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8", errors="replace")
    try:
        return json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def match_mode_label(ai_meta: dict) -> str:
    mode = clean_text(ai_meta.get("match_mode"))
    used_ai = bool(ai_meta.get("used_ai"))
    if mode == "quick":
        return "快速匹配"
    if used_ai:
        return "AI智能匹配"
    return "AI匹配-本地兜底"


def match_search_text(item: dict) -> str:
    submission = item.get("submission") or {}
    results = item.get("results") or []
    values: list[object] = [
        item.get("created_at"),
        item.get("match_mode_label"),
        item.get("ai_message"),
        submission.get("name"),
        submission.get("phone"),
        submission.get("company"),
        submission.get("title"),
        submission.get("tech_field"),
        submission.get("region"),
        submission.get("application_scene"),
        submission.get("summary"),
        submission.get("advantage"),
        submission.get("advantages"),
        submission.get("problem"),
        submission.get("maturity"),
        submission.get("ip_status"),
        submission.get("cooperation"),
        submission.get("extra_note"),
        submission.get("client_source"),
    ]
    for result in results:
        values.extend(
            [
                result.get("name"),
                result.get("tech_field"),
                result.get("demand_type"),
                result.get("region"),
                result.get("reason"),
                result.get("suggestion"),
            ],
        )
    return " ".join(clean_text(value) for value in values).lower()


def list_matches(limit: int = 120, keyword: str = "") -> list[dict]:
    keyword = clean_text(keyword).lower()
    with db_connect() as conn:
        rows = db_execute(
            conn,
            """
            SELECT match_id, submission_id, created_at, ai_meta_json, results_json, submission_json
            FROM matches
            ORDER BY created_at DESC
            """,
        ).fetchall()

    items: list[dict] = []
    for row in rows:
        item = dict(row)
        ai_meta = decode_json_field(item.pop("ai_meta_json", ""), {})
        results = decode_json_field(item.pop("results_json", ""), [])
        submission = decode_json_field(item.pop("submission_json", ""), {})
        if not isinstance(ai_meta, dict):
            ai_meta = {}
        if not isinstance(results, list):
            results = []
        if not isinstance(submission, dict):
            submission = {}
        item["ai_meta"] = ai_meta
        item["results"] = results[:5]
        item["submission"] = submission
        item["match_mode_label"] = match_mode_label(ai_meta)
        item["ai_message"] = clean_text(ai_meta.get("message"))
        if keyword and keyword not in match_search_text(item):
            continue
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


def get_match_record(match_id: str) -> dict:
    match_id = clean_text(match_id)
    with db_connect() as conn:
        row = db_execute(
            conn,
            """
            SELECT match_id, submission_id, created_at, ai_meta_json, results_json, submission_json
            FROM matches
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()
    if row is None:
        raise KeyError("未找到匹配记录")
    item = dict(row)
    item["ai_meta"] = decode_json_field(item.pop("ai_meta_json", ""), {})
    item["results"] = decode_json_field(item.pop("results_json", ""), [])
    item["submission"] = decode_json_field(item.pop("submission_json", ""), {})
    if not isinstance(item["ai_meta"], dict):
        item["ai_meta"] = {}
    if not isinstance(item["results"], list):
        item["results"] = []
    if not isinstance(item["submission"], dict):
        item["submission"] = {}
    item["match_mode_label"] = match_mode_label(item["ai_meta"])
    item["ai_message"] = clean_text(item["ai_meta"].get("message"))
    return item


def list_match_followups(match_id: str) -> dict[str, dict]:
    with db_connect() as conn:
        rows = db_execute(
            conn,
            """
            SELECT followup_id, match_id, submission_id, demand_id, status,
                   contact_note, project_progress, created_at, updated_at
            FROM match_followups
            WHERE match_id = ?
            """,
            (clean_text(match_id),),
        ).fetchall()
    return {clean_text(dict(row).get("demand_id")): dict(row) for row in rows}


def get_match_detail(store: DemandStore, match_id: str) -> dict:
    item = get_match_record(match_id)
    followups = list_match_followups(item["match_id"])
    enriched_results: list[dict] = []
    for result in item.get("results") or []:
        if not isinstance(result, dict):
            continue
        demand_id = clean_text(result.get("demand_id"))
        raw_demand = store.by_id(demand_id) or {}
        private = admin_demand_payload(raw_demand) if raw_demand else {}
        enriched_results.append(
            {
                **result,
                **private,
                "demand_id": demand_id,
                "followup": followups.get(demand_id)
                or {
                    "match_id": item["match_id"],
                    "submission_id": item.get("submission_id", ""),
                    "demand_id": demand_id,
                    "status": MATCH_FOLLOWUP_STATUSES[0],
                    "contact_note": "",
                    "project_progress": "",
                    "created_at": "",
                    "updated_at": "",
                },
            }
        )
    item["results"] = enriched_results
    return item


def save_match_followup(
    store: DemandStore,
    match_id: str,
    demand_id: str,
    status: str,
    contact_note: str = "",
    project_progress: str = "",
) -> dict:
    match_id = clean_text(match_id)
    demand_id = clean_text(demand_id)
    status = clean_text(status)
    if status not in MATCH_FOLLOWUP_STATUSES:
        raise ValueError("请选择有效的对接状态")
    match_record = get_match_record(match_id)
    candidate_ids = {
        clean_text(result.get("demand_id"))
        for result in (match_record.get("results") or [])
        if isinstance(result, dict)
    }
    if not demand_id or demand_id not in candidate_ids:
        raise ValueError("该需求不属于当前匹配记录")
    timestamp = now_iso()
    followup_id = hashlib.sha256(f"{match_id}:{demand_id}".encode("utf-8")).hexdigest()[:32]
    with db_connect() as conn:
        db_execute(
            conn,
            """
            INSERT INTO match_followups
                (followup_id, match_id, submission_id, demand_id, status,
                 contact_note, project_progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (match_id, demand_id) DO UPDATE SET
                status = excluded.status,
                contact_note = excluded.contact_note,
                project_progress = excluded.project_progress,
                updated_at = excluded.updated_at
            """,
            (
                followup_id,
                match_id,
                clean_text(match_record.get("submission_id")),
                demand_id,
                status,
                clean_text(contact_note),
                clean_text(project_progress),
                timestamp,
                timestamp,
            ),
        )
    return get_match_detail(store, match_id)


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
        item["progress"] = normalize_progress(item.pop("progress_json", ""), item.get("created_at"))
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
    item["progress"] = normalize_progress(item.pop("progress_json", ""), item.get("created_at"))
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
        item.get("query_code", ""),
        item.get("message", ""),
        item.get("attachment_note", ""),
        item.get("followup_note", ""),
        item.get("public_note", ""),
        item.get("deal_amount", ""),
        item.get("deal_note", ""),
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
        "查询码",
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
        "对外说明",
        "成交金额",
        "成交备注",
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
                item.get("query_code", ""),
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
                item.get("public_note", ""),
                item.get("deal_amount", ""),
                item.get("deal_note", ""),
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
        "Q": 30,
        "R": 20,
        "S": 30,
        "T": 34,
        "U": 24,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        for index in (3, 5, 20, 21):
            row[index - 1].number_format = "@"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def update_intent_status(
    intent_id: str,
    status: str,
    note: str,
    operator: str,
    *,
    public_note: str = "",
    progress: list[dict] | None = None,
    deal_amount: str | None = None,
    deal_note: str | None = None,
) -> dict:
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
        current = dict(row)
        progress_value = normalize_progress(progress if progress is not None else current.get("progress_json"), current.get("created_at"))
        public_note_value = clean_text(public_note) or clean_text(current.get("public_note"))
        deal_amount_value = clean_text(deal_amount) if deal_amount is not None else clean_text(current.get("deal_amount"))
        deal_note_value = clean_text(deal_note) if deal_note is not None else clean_text(current.get("deal_note"))
        db_execute(
            conn,
            """
            UPDATE intents
            SET status = ?, followup_note = ?, public_note = ?, progress_json = ?,
                deal_amount = ?, deal_note = ?, updated_at = ?
            WHERE intent_id = ?
            """,
            (
                status,
                clean_text(note),
                public_note_value,
                json_dumps(progress_value),
                deal_amount_value,
                deal_note_value,
                timestamp,
                intent_id,
            ),
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


def get_progress_by_query_code(query_code: str) -> dict:
    query_code = clean_text(query_code).upper()
    if not query_code:
        raise KeyError("请输入查询码")
    with db_connect() as conn:
        row = db_execute(conn, "SELECT * FROM intents WHERE UPPER(query_code) = ?", (query_code,)).fetchone()
        if row is None:
            raise KeyError("未找到该查询码对应的合作意向")
    item = row_to_intent(row)
    selected = item.get("selected_result") or {}
    return {
        "query_code": item.get("query_code", ""),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "status": item.get("status", ""),
        "public_note": item.get("public_note", "") or f"已收到合作意向，{PUBLIC_RESPONSE_PROMISE}",
        "promise": PUBLIC_RESPONSE_PROMISE,
        "demand": {
            "name": selected.get("name", ""),
            "score": selected.get("score", ""),
            "tech_field": selected.get("tech_field", ""),
            "demand_type": selected.get("demand_type", ""),
            "region": selected.get("region", ""),
            "reason": clip(selected.get("reason", ""), 220),
            "scoring_source": selected.get("scoring_source", ""),
        },
        "progress": public_progress(item.get("progress") or []),
    }


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
        if parsed.path == "/api/public/demands":
            query = parse_qs(parsed.query)
            try:
                offset = max(0, int(query.get("offset", ["0"])[0] or 0))
                limit = max(1, min(60, int(query.get("limit", ["24"])[0] or 24)))
            except ValueError:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "分页参数不正确")
                return
            items, total = self.store.search_page(keyword="", offset=offset, limit=limit)
            self.send_json({"items": items, "total": total, "offset": offset, "limit": limit})
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
        if parsed.path == "/api/matches":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            keyword = query.get("keyword", [""])[0]
            self.send_json({"items": list_matches(120, keyword=keyword)})
            return
        if parsed.path == "/api/matches/detail":
            if not self.require_admin():
                return
            query = parse_qs(parsed.query)
            try:
                match = get_match_detail(self.store, query.get("match_id", [""])[0])
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                return
            self.send_json({"match": match, "statuses": MATCH_FOLLOWUP_STATUSES})
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
            if clean_text(submission.get("client_source")) in {"网页端", "微信小程序"}:
                if not all(clean_text(submission.get(field)) for field in ("name", "phone", "company")):
                    self.send_error_json(HTTPStatus.BAD_REQUEST, "请填写姓名、手机号和单位，便于平台后续联系")
                    return
            submission_id = uuid.uuid4().hex
            record = {
                "submission_id": submission_id,
                "created_at": now_iso(),
                "submission": submission,
            }
            local_tag_profile = extract_submission_tags_local(submission)
            if match_mode == "quick":
                tag_profile = local_tag_profile
                tag_meta = {
                    "used_ai": False,
                    "source": "local",
                    "local_tags": compact_tag_payload(local_tag_profile),
                    "merged_tags": compact_tag_payload(local_tag_profile),
                    "message": "已使用本地规则完成标签抽取。",
                }
            else:
                tag_profile, tag_meta = extract_tags_with_ai(self.ai_config, submission, local_tag_profile)
            local_results = match_demands(self.store, submission, limit=18, candidate_limit=180, tags=tag_profile)
            if match_mode == "quick":
                refined_results, ai_meta = use_quick_match(local_results)
            else:
                refined_results, ai_meta = refine_matches_with_ai(
                    self.ai_config,
                    submission,
                    local_results,
                    tag_profile=tag_profile,
                    tag_meta=tag_meta,
                )
            ai_meta["tag_extraction"] = tag_meta
            ai_meta["structured_tags"] = compact_tag_payload(tag_profile)
            results = refined_results[:5]
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
            if not clean_text(contact.get("name")) or not clean_text(contact.get("phone")) or not clean_text(contact.get("company")):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "请填写姓名、手机号和单位，便于后续人工撮合")
                return
            selected = payload.get("selected_result") or {}
            timestamp = now_iso()
            intent = {
                "intent_id": uuid.uuid4().hex,
                "created_at": timestamp,
                "status": "待审核",
                "agreement_version": AGREEMENT_VERSION,
                "submission_id": clean_text(payload.get("submission_id", "")),
                "contact": {clean_text(k): clean_text(v) for k, v in contact.items()},
                "message": clean_text(payload.get("message", "")),
                "attachment_note": clean_text(payload.get("extra_note") or payload.get("attachment_note", "")),
                "selected_result": selected,
                "updated_at": timestamp,
                "followup_note": "",
                "query_code": generate_unique_query_code(),
                "public_note": f"已收到合作意向，{PUBLIC_RESPONSE_PROMISE}",
                "progress": default_progress(timestamp),
                "deal_amount": "",
                "deal_note": "",
            }
            save_intent(intent)
            self.send_json(
                {
                    "ok": True,
                    "intent": {
                        **intent,
                        "promise": PUBLIC_RESPONSE_PROMISE,
                    },
                }
            )
            return

        if parsed.path == "/api/progress/query":
            payload = self.read_json()
            try:
                progress = get_progress_by_query_code(clean_text(payload.get("query_code")))
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                return
            self.send_json({"ok": True, "progress": progress})
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
                    public_note=clean_text(payload.get("public_note")),
                    progress=payload.get("progress") if isinstance(payload.get("progress"), list) else None,
                    deal_amount=clean_text(payload.get("deal_amount")) if "deal_amount" in payload else None,
                    deal_note=clean_text(payload.get("deal_note")) if "deal_note" in payload else None,
                )
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                return
            except ValueError as exc:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self.send_json({"ok": True, "intent": intent, "items": list_intents(200)})
            return

        if parsed.path == "/api/matches/followup":
            if not self.require_admin():
                return
            payload = self.read_json()
            try:
                match = save_match_followup(
                    self.store,
                    clean_text(payload.get("match_id")),
                    clean_text(payload.get("demand_id")),
                    clean_text(payload.get("status")),
                    clean_text(payload.get("contact_note")),
                    clean_text(payload.get("project_progress")),
                )
            except KeyError as exc:
                self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                return
            except ValueError as exc:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self.send_json({"ok": True, "match": match, "statuses": MATCH_FOLLOWUP_STATUSES})
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
