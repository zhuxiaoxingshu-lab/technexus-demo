"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Demand = { demand_id?: string; name: string; tech_field?: string; demand_type?: string; region?: string; intended_price?: string; cooperation_mode?: string; detail_summary?: string };

const fallbackDemands: Demand[] = [
  { name: "工程机械橡胶履带板疲劳及预张紧力优化研究", tech_field: "新材料", demand_type: "关键技术研发", region: "江苏省 · 盐城市", intended_price: "5万", detail_summary: "针对履带板易开裂、脱落和使用寿命短等问题，建立多工况疲劳仿真模型，优化橡胶配方与骨架结构，并形成标准化预张紧力匹配方法。" },
  { name: "多功能柔性导电材料的关键技术研发", tech_field: "新能源与节能", demand_type: "合作开发", region: "江苏省 · 盐城市", intended_price: "面议", detail_summary: "研发兼具高透明、保水、抗冻和可拉伸导电特性的离子导电有机水凝胶，配套柔性应变传感器并完成材料配方及元件验证。" },
  { name: "复合相变储能墙体制备工艺及传热特性研究", tech_field: "新材料", demand_type: "关键技术研发", region: "江苏省 · 盐城市", intended_price: "面议", detail_summary: "研发石蜡基相变陶粒储能砂浆，建立分层传热模型，明确不同构造墙体的相变温度适配及节能传热规律。" },
];

export function LiveStats() {
  const [total, setTotal] = useState(5160);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/backend?path=stats", { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setTotal(Number(data.demand_count || data.total || 5160)))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);
  return <div className="stats-grid">
    <div><strong>{total.toLocaleString("zh-CN")}<sup>+</sup></strong><span>已入库真实技术需求</span></div>
    <div><strong>6<sup>维</sup></strong><span>技术任务结构化评分</span></div>
    <div><strong>5<sup>条</sup></strong><span>单次返回优选需求</span></div>
    <div><strong>3<sup>日</sup></strong><span>承诺初步审核反馈</span></div>
  </div>;
}

export function DemandPreview() {
  const [items, setItems] = useState<Demand[]>(fallbackDemands);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/backend?path=public/demands&limit=3", { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => Array.isArray(data.items) && data.items.length ? setItems(data.items.slice(0, 3)) : undefined)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);
  return <div className="demand-grid">
    {items.map((item, index) => <article className="demand-card" key={item.demand_id || item.name}>
      <div className="demand-number">{String(index + 1).padStart(2, "0")}</div>
      <div className="tags"><span>{item.tech_field || "技术需求"}</span><span>{item.demand_type || item.cooperation_mode || "合作开发"}</span></div>
      <h3>{item.name}</h3><p>{item.detail_summary}</p>
      <div className="demand-meta"><span>{normalizeRegion(item.region)}</span><b>{item.intended_price ? `意向投入 ${item.intended_price}` : "投入面议"}</b></div>
      <Link href="/match">用我的成果匹配此类需求 →</Link>
    </article>)}
  </div>;
}

function normalizeRegion(value?: string) {
  return (value || "江苏省").replace(/\s*\/\s*/g, " · ").replace(/ · \d{6}$/, "");
}
