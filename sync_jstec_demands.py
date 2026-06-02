#!/usr/bin/env python3
"""
Incrementally sync new JSTEC technical demands into the TechNexus demand database.

Typical usage:
    python sync_jstec_demands.py
    python sync_jstec_demands.py --dry-run
    python sync_jstec_demands.py --max-pages 5 --stop-after-known 20
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from scrape_jstec_demands import (
    append_skip_log,
    build_session,
    clean_text,
    extract_row,
    fetch_area_code_map,
    fetch_detail,
    fetch_list_page,
    fetch_list_page_one_by_one,
)
from technexus_app.app import (
    DEMANDS_FILE,
    existing_demand_ids,
    init_database,
    load_demands_from_file,
    save_demand_rows_to_database,
)


def known_ids_from_file() -> set[str]:
    if not DEMANDS_FILE.exists():
        return set()
    try:
        rows = load_demands_from_file(DEMANDS_FILE)
    except Exception:
        return set()
    return {clean_text(row.get("需求ID")) for row in rows if clean_text(row.get("需求ID"))}


def load_known_ids() -> set[str]:
    ids = existing_demand_ids()
    if ids:
        return ids
    return known_ids_from_file()


def fetch_recent_new_rows(args: argparse.Namespace) -> tuple[list[dict], dict[str, Any]]:
    session = build_session()
    area_map = fetch_area_code_map(session, args.timeout)
    known_ids = load_known_ids()
    new_rows: list[dict] = []
    seen_new_ids: set[str] = set()
    known_streak = 0
    pages_scanned = 0
    total = 0
    skip_log_path = Path(args.skip_log)

    for page in range(1, args.max_pages + 1):
        pages_scanned = page
        try:
            list_rows, total_count = fetch_list_page(
                session,
                page=page,
                page_size=args.page_size,
                timeout=args.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - fallback mirrors the full crawler.
            message = f"第 {page} 页批量读取失败：{exc}"
            print(message, file=sys.stderr)
            append_skip_log(skip_log_path, message)
            list_rows, total_count = fetch_list_page_one_by_one(
                session,
                page=page,
                page_size=args.page_size,
                timeout=args.timeout,
                known_total=total,
                skip_log_path=skip_log_path,
            )

        total = total_count or total
        if not list_rows:
            break

        print(f"扫描第 {page} 页：{len(list_rows)} 条，总数 {total_count}", file=sys.stderr)
        for item in list_rows:
            demand_id = clean_text(item.get("id"))
            if not demand_id:
                continue
            if demand_id in known_ids:
                known_streak += 1
                if known_streak >= args.stop_after_known:
                    return new_rows, {
                        "pages_scanned": pages_scanned,
                        "known_streak": known_streak,
                        "known_count": len(known_ids),
                        "site_total": total,
                    }
                continue

            known_streak = 0
            if demand_id in seen_new_ids:
                continue
            seen_new_ids.add(demand_id)

            try:
                detail = fetch_detail(session, demand_id, timeout=args.timeout)
            except Exception as exc:  # noqa: BLE001 - keep the daily sync moving.
                message = f"需求 {demand_id} 详情读取失败，已用列表页信息占位：{exc}"
                print(message, file=sys.stderr)
                append_skip_log(skip_log_path, message)
                detail = item

            row = extract_row(detail, area_map)
            if row.get("需求ID"):
                new_rows.append(row)
                print(f"发现新增需求：{row.get('需求名称')} ({row.get('需求ID')})", file=sys.stderr)

            if args.limit_new and len(new_rows) >= args.limit_new:
                return new_rows, {
                    "pages_scanned": pages_scanned,
                    "known_streak": known_streak,
                    "known_count": len(known_ids),
                    "site_total": total,
                }
            if args.delay > 0:
                time.sleep(args.delay)

        if total_count and page * args.page_size >= total_count:
            break

    return new_rows, {
        "pages_scanned": pages_scanned,
        "known_streak": known_streak,
        "known_count": len(known_ids),
        "site_total": total,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="增量同步 JSTEC 最新技术需求到 TechNexus 需求库")
    parser.add_argument("--max-pages", type=int, default=12, help="最多扫描前多少页")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数，建议保持 10")
    parser.add_argument("--stop-after-known", type=int, default=30, help="连续遇到多少条已存在需求后停止")
    parser.add_argument("--limit-new", type=int, default=0, help="最多新增多少条；0 表示不限制")
    parser.add_argument("--delay", type=float, default=0.3, help="每条详情请求后的等待秒数")
    parser.add_argument("--timeout", type=float, default=20, help="单次请求超时时间，秒")
    parser.add_argument("--dry-run", action="store_true", help="只扫描，不写入数据库")
    parser.add_argument("--skip-log", default="technexus_data/jstec_sync.skipped.log", help="失败记录日志")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_database()
    rows, meta = fetch_recent_new_rows(args)
    if args.dry_run:
        result = {"dry_run": True, "new_count": len(rows), **meta}
    else:
        saved = save_demand_rows_to_database(rows, update_existing=True)
        result = {"dry_run": False, "new_count": len(rows), **saved, **meta}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
