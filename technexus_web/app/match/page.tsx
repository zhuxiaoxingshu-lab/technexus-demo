import type { Metadata } from "next";
import { MatchWorkspace } from "../components/MatchWorkspace";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";

export const metadata: Metadata = { title: "AI 技术成果匹配", description: "粘贴完整技术成果材料，由 AI 拆解成果能力画像并从真实产业需求库中匹配具体技术任务。" };

export default function MatchPage() {
  return <main><SiteHeader /><section className="page-hero"><div className="shell"><div className="eyebrow"><span />AI MATCHING</div><h1>粘贴完整成果，让 AI 拆解后精准匹配</h1><p>无需先手工拆分表单。直接粘贴专利、论文、技术说明或项目材料，系统会提取技术标的、核心问题、技术路线、指标与证据，再与真实需求正文逐项对照。</p></div></section><div className="page-content shell"><MatchWorkspace /></div><SiteFooter /></main>;
}
