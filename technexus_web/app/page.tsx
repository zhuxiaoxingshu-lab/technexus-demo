import Link from "next/link";
import { DemandPreview, LiveStats } from "./components/HomeData";
import { SiteFooter, SiteHeader } from "./components/SiteChrome";

const workflow = [
  ["01", "提交技术成果", "说明技术原理、应用场景、量化指标与现有验证基础。"],
  ["02", "构建成果能力画像", "系统拆解技术标的、核心问题、所需功能、技术路线与交付成熟度。"],
  ["03", "召回技术任务", "先从完整需求库中召回具体技术任务，不以宽泛行业词作为主要依据。"],
  ["04", "AI 复核与评分", "DeepSeek 对候选项目逐项核验，输出依据、待验证项和合作建议。"],
];

export default function Home() {
  return (
    <main>
      <SiteHeader />

      <section className="hero shell">
        <div className="hero-copy">
          <div className="eyebrow"><span />江苏产业技术需求库 · 技术成果转化服务</div>
          <h1>让技术成果找到<br /><em>真正能够承接的产业需求</em></h1>
          <p className="hero-lead">
            元数智转围绕需求正文拆解技术任务，以 AI 完成候选召回、技术可行性复核与解释型评分，
            再由技术经理人开展人工审核和项目对接。
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/match">开始 AI 匹配 <span>↗</span></Link>
            <Link className="button button-secondary" href="/demands">浏览需求样本</Link>
          </div>
          <div className="trust-line">
            <span>✓ 前台信息脱敏</span><span>✓ 需求正文参与评分</span><span>✓ 结果人工复核</span>
          </div>
        </div>

        <div className="hero-console" aria-label="AI 技术匹配示意">
          <div className="console-top"><span className="console-dot" />TECHNEXUS / MATCH ENGINE <b>LIVE</b></div>
          <div className="console-stage">
            <div className="console-label">成果能力画像</div>
            <h3>功能性低温导电银浆</h3>
            <div className="console-grid">
              <div><small>技术标的</small><strong>纳米球形银粉 · 精细片状银粉</strong></div>
              <div><small>核心问题</small><strong>进口依赖 · 形貌控制 · 刻蚀良率</strong></div>
              <div><small>交付形态</small><strong>材料配方 · 制备工艺 · 验证样品</strong></div>
              <div><small>成熟度</small><strong>小试 / 待中试验证</strong></div>
            </div>
            <div className="match-path"><span>成果解析</span><i>→</i><span>任务召回</span><i>→</i><span>AI 复核</span></div>
          </div>
          <div className="console-result">
            <div><small>建议优先对接</small><strong>高端导电材料国产化关键技术</strong></div>
            <div className="score-ring"><b>91</b><small>综合评分</small></div>
          </div>
        </div>
      </section>

      <section className="stats-band">
        <div className="shell"><LiveStats /></div>
      </section>

      <section className="section shell" id="method">
        <div className="section-heading split-heading">
          <div><div className="eyebrow"><span />匹配方法</div><h2>从“行业相似”转向<br />“技术任务可承接”</h2></div>
          <p>行业和领域只用于扩大候选范围。真正决定排序的是需求正文中的技术标的、问题机制、功能目标、路线约束、指标与交付条件。</p>
        </div>
        <div className="workflow-grid">
          {workflow.map(([number, title, description]) => (
            <article className="workflow-card" key={number}>
              <span>{number}</span><h3>{title}</h3><p>{description}</p>
            </article>
          ))}
        </div>
        <div className="method-note">
          <div className="method-code">Target → Problem → Function → Route → Constraint → Evidence</div>
          <p>匹配结果同步展示评分依据、具体需求正文、已识别对应点与尚待验证事项，减少“高分但不知为什么”的黑箱感。</p>
        </div>
      </section>

      <section className="section section-tint">
        <div className="shell">
          <div className="section-heading split-heading">
            <div><div className="eyebrow"><span />真实需求样本</div><h2>来自江苏产业一线的<br />具体技术任务</h2></div>
            <div className="heading-action"><p>公开页面只展示脱敏后的需求内容，不展示发布单位、联系人与联系方式。</p><Link href="/demands">进入需求大厅 →</Link></div>
          </div>
          <DemandPreview />
        </div>
      </section>

      <section className="section shell">
        <div className="service-panel">
          <div>
            <div className="eyebrow eyebrow-light"><span />技术经理人服务</div>
            <h2>AI 负责提高初筛效率，<br />关键对接仍由专业人员完成</h2>
          </div>
          <div className="service-list">
            <div><b>01</b><span><strong>人工复核</strong>核查技术适配性、信息完整度和合作边界</span></div>
            <div><b>02</b><span><strong>供需沟通</strong>联系双方确认指标、样品、验证与交付条件</span></div>
            <div><b>03</b><span><strong>项目推进</strong>记录沟通进度，协助形成技术合作方案</span></div>
          </div>
        </div>
      </section>

      <section className="cta-section shell">
        <div><span>TECHNOLOGY × INDUSTRY</span><h2>准备好让技术成果接受真实产业需求检验了吗？</h2></div>
        <Link className="button button-light" href="/match">提交成果并开始匹配 <span>↗</span></Link>
      </section>

      <SiteFooter />
    </main>
  );
}
