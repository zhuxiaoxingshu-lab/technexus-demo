import type { Metadata } from "next";
import { ProgressQuery } from "../components/ProgressQuery";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";

export const metadata: Metadata = { title: "查询对接进度", description: "使用合作申请查询码查看技术项目当前对接进度。" };
export default function ProgressPage() { return <main><SiteHeader /><section className="page-hero"><div className="shell"><div className="eyebrow"><span />PROJECT STATUS</div><h1>查询项目对接进度</h1><p>输入提交合作申请后获得的查询码，查看平台人工审核、供需联系和项目推进状态。</p></div></section><div className="page-content shell"><ProgressQuery /></div><SiteFooter /></main>; }
