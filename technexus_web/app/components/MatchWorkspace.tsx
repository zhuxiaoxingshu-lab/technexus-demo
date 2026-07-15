"use client";

import { FormEvent, useMemo, useState } from "react";

type ResultItem = {
  demand_id?: string; name: string; score?: number; tech_field?: string; demand_type?: string; intended_price?: string; region?: string; cooperation_mode?: string;
  detail_summary?: string; reason?: string; suggestion?: string; scoring_source?: string; dimensions?: Record<string, number>;
  technical_target?: string; core_problem?: string; matched_capability?: string; transfer_path?: string; confidence?: number;
  verified_items?: string[]; unverified_items?: string[]; hard_conflicts?: string[]; hard_gate?: string;
};
type MatchResponse = { submission_id?: string; results?: ResultItem[]; ai_meta?: { used_ai?: boolean; message?: string; capability_profile?: Record<string, unknown> }; message?: string };
type Submission = Record<string, string>;

const fields = ["新材料", "新能源与节能", "电子信息", "智能制造", "生物医药", "环保低碳", "高端装备", "其他"];

export function MatchWorkspace() {
  const [mode, setMode] = useState("ai");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState<MatchResponse | null>(null);
  const [submission, setSubmission] = useState<Submission>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(""); setResponse(null);
    const form = event.currentTarget;
    const body = Object.fromEntries(new FormData(form).entries()) as Submission;
    body.match_mode = mode; body.client_source = "网页端";
    setSubmission(body);
    try {
      const result = await fetch("/api/backend?path=match", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const text = await result.text();
      const data = text ? JSON.parse(text) as MatchResponse : { message: "服务器未返回数据" };
      if (!result.ok) throw new Error(data.message || "匹配服务暂时不可用");
      setResponse(data);
      setTimeout(() => document.getElementById("match-results")?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "匹配失败，请稍后重试"); }
    finally { setLoading(false); }
  }

  return <>
    <form className="panel" onSubmit={submit}>
      <div className="match-mode">
        <label className={`mode-option ${mode === "ai" ? "active" : ""}`}><input type="radio" checked={mode === "ai"} onChange={() => setMode("ai")} /><span><b>AI 智能匹配</b><small>本地召回候选后，由 DeepSeek 读取成果画像与需求正文进行复核、评分和解释。</small></span></label>
        <label className={`mode-option ${mode === "quick" ? "active" : ""}`}><input type="radio" checked={mode === "quick"} onChange={() => setMode("quick")} /><span><b>快速规则匹配</b><small>不调用外部 AI，适合先查看本地技术任务召回结果。</small></span></label>
      </div>
      <div className="notice">联系人信息仅用于平台人工审核和项目对接，不会在前台公开；匹配结果也不会展示需求发布单位及联系方式。</div>
      <FormSection number="01" title="联系人信息" description="用于确认成果真实性并在高匹配项目出现时联系您。">
        <div className="form-grid">
          <Field label="姓名" required><input name="name" required placeholder="请输入联系人姓名" /></Field>
          <Field label="手机号" required><input name="phone" required inputMode="tel" placeholder="请输入手机号" /></Field>
          <Field label="单位" required><input name="company" required placeholder="高校、科研院所或企业" /></Field>
          <Field label="成果名称" required><input name="achievement_name" required placeholder="请输入成果、专利或技术方案名称" /></Field>
          <Field label="技术领域"><select name="tech_field" defaultValue=""><option value="">请选择或留空</option>{fields.map((item) => <option key={item}>{item}</option>)}</select></Field>
          <Field label="所在地区"><input name="region" placeholder="例如：江苏省 / 南通市" /></Field>
        </div>
      </FormSection>
      <FormSection number="02" title="技术任务信息" description="系统主要依据这里的内容与需求正文进行技术层面的对照。">
        <div className="form-grid">
          <Field label="应用场景" required className="full"><textarea name="application_scene" required placeholder="这项成果主要用于哪些行业、产品、设备或生产环节？" /></Field>
          <Field label="技术成果摘要" required className="full"><textarea name="summary" required placeholder="成果是什么、目前完成了什么、能够解决什么具体技术问题？" /></Field>
          <Field label="底层原理与技术路线" required className="full"><textarea name="technical_route" required placeholder="请说明采用的材料、配方、工艺、算法、设备或系统路线，以及关键作用机制。" /></Field>
          <Field label="量化指标" className="wide"><textarea name="indicators" placeholder="例如：导热系数≥10 W/mK、识别精度≥95%、寿命≥6000次。" /></Field>
          <Field label="验证基础"><textarea name="evidence" placeholder="例如：已有样品、检测报告、中试记录、客户案例、专利或论文。" /></Field>
          <Field label="相对优势" className="wide"><textarea name="advantages" placeholder="相较现有方案在成本、效率、可靠性、性能或规模化方面的优势。" /></Field>
          <Field label="拟解决的产业问题"><textarea name="problem" placeholder="希望帮助企业解决什么具体痛点？" /></Field>
        </div>
      </FormSection>
      <FormSection number="03" title="成熟度与合作方式" description="帮助系统判断需求交付条件是否与成果现状相符。">
        <div className="form-grid">
          <Field label="技术成熟度"><select name="maturity" defaultValue=""><option value="">请选择</option><option>概念验证阶段</option><option>实验室样品</option><option>小试阶段</option><option>中试阶段</option><option>具备量产条件</option></select></Field>
          <Field label="知识产权状态"><select name="ip_status" defaultValue=""><option value="">请选择</option><option>已授权专利</option><option>专利申请中</option><option>软件著作权</option><option>技术秘密</option><option>论文或科研成果</option><option>暂无</option></select></Field>
          <Field label="期望合作方式"><select name="cooperation" defaultValue=""><option value="">请选择</option><option>合作开发</option><option>技术转让</option><option>技术许可</option><option>技术服务</option><option>委托研发</option><option>可协商</option></select></Field>
        </div>
      </FormSection>
      <div className="form-submit"><button className="button button-primary" type="submit" disabled={loading}>{loading ? "正在分析与匹配…" : "开始 AI 智能匹配 ↗"}</button><p>AI 结果用于技术转移初筛，不构成技术可行性、投资、法律或知识产权结论。</p></div>
      {loading && <div className="loading-box"><span className="spinner" /><div><b>正在拆解成果能力画像并召回技术任务</b><br /><small>免费服务器首次唤醒可能需要约 1 分钟，请保持页面打开。</small></div></div>}
      {error && <div className="error-box">{error}</div>}
    </form>
    {response && <MatchResults response={response} submission={submission} />}
  </>;
}

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: React.ReactNode }) { return <section className="form-section"><div className="form-section-head"><span>{number}</span><div><h2>{title}</h2><p>{description}</p></div></div>{children}</section>; }
function Field({ label, required, className = "", children }: { label: string; required?: boolean; className?: string; children: React.ReactNode }) { return <div className={`field ${className}`}><label>{label}{required && <em> *</em>}</label>{children}</div>; }

function MatchResults({ response, submission }: { response: MatchResponse; submission: Submission }) {
  const items = response.results || [];
  const [selected, setSelected] = useState<number | null>(null);
  return <section className="results-wrap" id="match-results">
    <div className="results-heading"><div><h2>AI 匹配结果</h2><p>{response.ai_meta?.used_ai ? "已完成 DeepSeek 技术复核" : "已使用本地技术任务规则评分"} · 仅展示达到推荐阈值的项目</p></div><span className="chip">共 {items.length} 条</span></div>
    {!items.length && <div className="panel"><h3>暂未找到达到推荐阈值的需求</h3><p className="notice">建议补充底层原理、可解决的问题、量化指标、样品或案例后重新匹配。系统不会仅因为行业词相似而返回高分项目。</p></div>}
    {items.map((item, index) => <ResultCard key={item.demand_id || `${item.name}-${index}`} item={item} selected={selected === index} onSelect={() => setSelected(selected === index ? null : index)} submission={submission} submissionId={response.submission_id || ""} />)}
  </section>;
}

function ResultCard({ item, selected, onSelect, submission, submissionId }: { item: ResultItem; selected: boolean; onSelect: () => void; submission: Submission; submissionId: string }) {
  const dimensions = useMemo(() => normalizeDimensions(item.dimensions), [item.dimensions]);
  return <article className="result-card">
    <div className="result-head"><div><h3>{item.name}</h3><div className="tags">{[item.tech_field, item.demand_type, item.intended_price ? `意向投入 ${item.intended_price}` : "", cleanRegion(item.region), item.cooperation_mode, item.scoring_source].filter(Boolean).map((tag) => <span key={tag}>{tag}</span>)}</div></div><div className="result-score"><strong>{Math.round(item.score || 0)}%</strong><small>{scoreLabel(item.score)}</small></div></div>
    {dimensions.length > 0 && <div className="score-bars">{dimensions.map(([label, value]) => <div className="score-bar" key={label}>{label}<span>{value}</span><div className="score-track"><i style={{ width: `${value}%` }} /></div></div>)}</div>}
    <div className="demand-detail"><h4>项目具体技术需求</h4><p>{item.detail_summary || "需求正文正在完善，申请对接后由平台进一步核实。"}</p></div>
    <div className="reason-grid"><div><b>匹配依据</b><span>{item.reason || item.matched_capability || "系统根据技术任务结构化信息完成综合判断。"}</span></div><div><b>合作建议</b><span>{item.suggestion || item.transfer_path || "建议补充技术说明、指标与验证材料，由平台人工复核后开展对接。"}</span></div></div>
    {(item.verified_items?.length || item.unverified_items?.length || item.hard_conflicts?.length) ? <div className="reason-grid"><Assessment title="已识别对应点" values={item.verified_items} /><Assessment title="尚待验证" values={[...(item.unverified_items || []), ...(item.hard_conflicts || [])]} /></div> : null}
    <div className="result-actions"><small>前台不展示需求发布单位及联系方式</small><button className="button button-primary" type="button" onClick={onSelect}>{selected ? "收起申请" : "申请人工对接"}</button></div>
    {selected && <IntentForm item={item} submission={submission} submissionId={submissionId} />}
  </article>;
}

function Assessment({ title, values }: { title: string; values?: string[] }) { return <div><b>{title}</b><span>{values?.length ? values.join("；") : "无明显信息"}</span></div>; }

function IntentForm({ item, submission, submissionId }: { item: ResultItem; submission: Submission; submissionId: string }) {
  const [done, setDone] = useState<{ query_code?: string } | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submitIntent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try { const response = await fetch("/api/backend?path=intents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ submission_id: submissionId, contact: { name: data.name, phone: data.phone, company: data.company }, message: data.message, agreement: data.agreement === "on", selected_result: item }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.message || "提交失败"); setDone(payload.intent || {}); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "提交失败，请稍后重试"); } finally { setBusy(false); }
  }
  if (done) return <div className="success-box"><span>合作申请已提交，请保存查询码：</span><strong>{done.query_code || "请在平台后台查询"}</strong><small>平台将在 3 个工作日内完成初步审核或联系。</small></div>;
  return <form className="intent-panel" onSubmit={submitIntent}><h4>申请人工对接</h4><div className="form-grid"><Field label="姓名" required><input name="name" required defaultValue={submission.name} /></Field><Field label="手机号" required><input name="phone" required defaultValue={submission.phone} /></Field><Field label="单位" required><input name="company" required defaultValue={submission.company} /></Field><Field label="补充说明" className="full"><textarea name="message" placeholder="希望平台重点核实哪些指标或合作条件？" /></Field></div><label className="agreement"><input type="checkbox" name="agreement" required />我确认提交信息真实，并同意平台仅为本次技术匹配与项目对接使用上述联系方式。</label><button className="button button-primary" disabled={busy} type="submit">{busy ? "正在提交…" : "确认申请对接"}</button>{error && <div className="error-box">{error}</div>}</form>;
}

function normalizeDimensions(dimensions?: Record<string, number>) { const map: [string, string[]][] = [["核心问题", ["核心问题", "core_problem"]], ["技术标的", ["技术标的", "technical_target"]], ["所需功能", ["所需功能", "required_function"]], ["技术路线", ["技术路线", "technical_route"]], ["指标约束", ["指标约束", "constraints"]], ["交付成熟度", ["交付成熟度", "maturity"]]]; return map.map(([label, keys]) => [label, Math.max(0, Math.min(100, Number(keys.map((key) => dimensions?.[key]).find((value) => value !== undefined) || 0)))] as [string, number]).filter(([, value]) => value > 0); }
function scoreLabel(score?: number) { const value = Number(score || 0); return value >= 80 ? "优先对接" : value >= 65 ? "建议补充材料" : "进一步核验"; }
function cleanRegion(value?: string) { return (value || "").replace(/\s*\/\s*/g, " · ").replace(/ · \d{6}$/, ""); }
