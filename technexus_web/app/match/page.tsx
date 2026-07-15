import type { Metadata } from "next";
import { MatchWorkspace } from "../components/MatchWorkspace";
import { SiteFooter, SiteHeader } from "../components/SiteChrome";

export const metadata: Metadata = { title: "AI 技术成果匹配", description: "提交技术成果，由 AI 从真实产业技术需求库中召回并复核可承接的技术任务。" };

export default function MatchPage() {
  return <main><SiteHeader /><section className="page-hero"><div className="shell"><div className="eyebrow"><span />AI MATCHING</div><h1>提交技术成果，匹配具体产业任务</h1><p>尽量写清技术原理、可解决的问题、量化指标和现有验证基础。系统会读取需求正文并输出可解释的匹配结果。</p></div></section><div className="page-content shell"><MatchWorkspace /></div><SiteFooter /></main>;
}
