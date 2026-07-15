import type { Metadata } from "next";
import { DemandHall } from "../components/DemandHall";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";

export const metadata: Metadata = { title: "技术需求大厅", description: "浏览脱敏后的真实产业技术需求样本，并通过 AI 匹配完整需求库。" };
export default function DemandsPage() { return <main><SiteHeader /><section className="page-hero"><div className="shell"><div className="eyebrow"><span />DEMAND LIBRARY</div><h1>技术需求大厅</h1><p>公开展示部分真实产业技术需求样本。平台不提供关键词筛选，也不展示需求方身份及联系方式；提交成果后由 AI 从完整需求库中召回更适合的项目。</p></div></section><div className="page-content shell"><DemandHall /></div><SiteFooter /></main>; }
