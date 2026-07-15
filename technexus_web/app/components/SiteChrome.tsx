import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="brand" href="/" aria-label="元数智转首页">
          <span className="brand-mark">元</span>
          <span><b>元数智转</b><small>TECHNEXUS</small></span>
        </Link>
        <nav aria-label="主导航">
          <Link href="/">首页</Link>
          <Link href="/match">AI 匹配</Link>
          <Link href="/demands">需求大厅</Link>
          <Link href="/progress">查询进度</Link>
        </nav>
        <a className="admin-link" href="https://technexus-demo.onrender.com/" target="_blank" rel="noreferrer">后台管理 ↗</a>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div><div className="brand brand-light"><span className="brand-mark">元</span><span><b>元数智转</b><small>TECHNEXUS</small></span></div><p>AI 驱动的技术成果匹配与技术经理人服务平台</p></div>
        <div><strong>平台入口</strong><Link href="/match">AI 成果匹配</Link><Link href="/demands">技术需求大厅</Link><Link href="/progress">对接进度查询</Link></div>
        <div><strong>服务说明</strong><p>匹配结论用于技术转移初筛参考，正式合作前需进一步开展技术、法律与知识产权核验。</p></div>
      </div>
      <div className="shell footer-bottom">© 2026 南通元数启科技有限公司 · 元数智转</div>
    </footer>
  );
}
