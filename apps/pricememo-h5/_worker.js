/**
 * Cloudflare Worker / Pages Worker Script for shop.pricememo.cn
 *
 * 主办单位: 湖南湘江新区彩头软件开发工作室（个体工商户）
 * 备案号: 湘ICP备2026030136号-1
 * 挂载域名: shop.pricememo.cn
 */

const HTML_CONTENT = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>彩头软件 · 官方移动端商城 - 湖南湘江新区彩头软件开发工作室</title>
  <meta name="description" content="湖南湘江新区彩头软件开发工作室官方移动端商城，提供专业软件定制开发、智能数字化工具订阅、技术咨询与系统运维服务。">
  <meta property="og:type" content="website">
  <meta property="og:title" content="彩头软件 · 官方移动商城">
  <meta property="og:description" content="湖南湘江新区彩头软件开发工作室官方商城，专业技术服务与软件开发，即时在线交付。">
  <meta property="og:url" content="https://shop.pricememo.cn/">
  <style>
    :root {
      --primary: #2563eb; --primary-dark: #1d4ed8; --primary-light: #eff6ff;
      --accent: #10b981; --accent-light: #ecfdf5; --danger: #ef4444;
      --text-main: #0f172a; --text-muted: #64748b; --text-light: #94a3b8;
      --bg-body: #f8fafc; --bg-card: #ffffff;
      --border-line: #e2e8f0; --border-subtle: #f1f5f9;
      --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-full: 9999px;
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-body); color: var(--text-main); line-height: 1.5; font-size: 14px;
      padding-bottom: calc(72px + var(--safe-bottom)); -webkit-font-smoothing: antialiased;
    }
    .header-bar {
      position: sticky; top: 0; z-index: 100; height: 52px; background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-line);
      display: flex; align-items: center; justify-content: space-between; padding: 0 16px;
    }
    .brand-wrap { display: flex; align-items: center; gap: 8px; }
    .brand-logo {
      width: 28px; height: 28px; background: linear-gradient(135deg, #2563eb, #06b6d4);
      border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 800; font-size: 15px;
    }
    .brand-title { font-size: 15px; font-weight: 700; color: var(--text-main); }
    .brand-tag { font-size: 10px; background: var(--accent-light); color: var(--accent); padding: 2px 6px; border-radius: var(--radius-full); font-weight: 600; }
    .btn-share {
      display: inline-flex; align-items: center; gap: 5px; padding: 6px 12px;
      background: var(--primary-light); color: var(--primary); border: 1px solid rgba(37,99,235,0.2);
      border-radius: var(--radius-full); font-size: 12px; font-weight: 600; cursor: pointer;
    }
    .btn-share svg { width: 14px; height: 14px; }
    .app-container { max-width: 640px; margin: 0 auto; padding: 12px 14px; }
    .hero-banner {
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      border-radius: var(--radius-lg); padding: 20px 18px; color: #ffffff; margin-bottom: 14px;
    }
    .hero-badge {
      display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
      color: #93c5fd; background: rgba(255, 255, 255, 0.1); padding: 3px 8px; border-radius: var(--radius-full); margin-bottom: 8px;
    }
    .hero-title { font-size: 19px; font-weight: 800; line-height: 1.3; margin-bottom: 6px; }
    .hero-desc { font-size: 12px; color: #94a3b8; line-height: 1.5; margin-bottom: 12px; }
    .hero-features { display: flex; gap: 12px; font-size: 11px; color: #cbd5e1; }
    .category-tabs { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 10px 2px; }
    .tab-btn {
      white-space: nowrap; padding: 7px 14px; background: var(--bg-card); border: 1px solid var(--border-line);
      border-radius: var(--radius-full); font-size: 13px; font-weight: 500; color: var(--text-muted); cursor: pointer;
    }
    .tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
    .section-header { display: flex; align-items: center; justify-content: space-between; margin: 12px 2px 10px; }
    .section-title { font-size: 15px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 6px; }
    .section-title::before { content: ''; display: inline-block; width: 4px; height: 14px; background: var(--primary); border-radius: 2px; }
    .product-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .product-card {
      background: var(--bg-card); border: 1px solid var(--border-line); border-radius: var(--radius-md);
      padding: 14px; display: flex; gap: 14px;
    }
    .product-thumb {
      width: 84px; height: 84px; border-radius: var(--radius-sm);
      background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
      display: flex; align-items: center; justify-content: center; flex-shrink: 0; position: relative; border: 1px solid var(--border-line);
    }
    .product-badge-corner { position: absolute; top: 0; left: 0; background: var(--accent); color: #fff; font-size: 9px; font-weight: 700; padding: 2px 6px; border-bottom-right-radius: 6px; }
    .product-info { flex: 1; display: flex; flex-direction: column; justify-content: space-between; }
    .product-name { font-size: 14px; font-weight: 700; color: var(--text-main); line-height: 1.35; margin-bottom: 4px; }
    .product-desc { font-size: 11px; color: var(--text-muted); line-height: 1.4; margin-bottom: 8px; }
    .product-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
    .tag-chip { font-size: 10px; padding: 1px 5px; border-radius: 4px; background: var(--bg-body); color: var(--text-muted); border: 1px solid var(--border-line); }
    .product-foot { display: flex; align-items: flex-end; justify-content: space-between; }
    .price-box { display: flex; align-items: baseline; gap: 4px; }
    .price-symbol { font-size: 12px; font-weight: 700; color: var(--danger); }
    .price-val { font-size: 18px; font-weight: 800; color: var(--danger); }
    .price-original { font-size: 11px; color: var(--text-light); text-decoration: line-through; }
    .btn-buy {
      padding: 6px 14px; background: var(--primary); color: #fff; font-size: 12px; font-weight: 600;
      border: none; border-radius: var(--radius-full); cursor: pointer;
    }
    .trust-section { background: var(--bg-card); border: 1px solid var(--border-line); border-radius: var(--radius-md); padding: 14px 16px; margin-top: 16px; }
    .trust-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
    .trust-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
    .trust-icon-wrap { width: 34px; height: 34px; border-radius: 50%; background: var(--primary-light); color: var(--primary); display: flex; align-items: center; justify-content: center; }
    .trust-name { font-size: 11px; font-weight: 700; }
    .trust-sub { font-size: 10px; color: var(--text-muted); }
    .merchant-profile { background: var(--bg-card); border: 1px solid var(--border-line); border-radius: var(--radius-md); padding: 14px 16px; margin-top: 14px; }
    .profile-title { font-size: 13px; font-weight: 700; color: var(--text-main); margin-bottom: 8px; display: flex; justify-content: space-between; }
    .profile-row { display: flex; justify-content: space-between; font-size: 11px; line-height: 1.8; border-bottom: 1px dashed var(--border-subtle); padding: 3px 0; }
    .profile-row:last-child { border-bottom: none; }
    .profile-label { color: var(--text-muted); }
    .profile-value { font-weight: 500; color: var(--text-main); }
    .legal-links { display: flex; justify-content: center; gap: 16px; margin: 18px 0 10px; font-size: 11px; }
    .legal-links a { color: var(--text-muted); text-decoration: underline; cursor: pointer; }
    .icp-footer { text-align: center; padding: 14px 12px 10px; color: var(--text-muted); font-size: 11px; line-height: 1.7; }
    .icp-link { color: var(--primary); font-weight: 600; text-decoration: none; }
    .copyright { color: var(--text-light); font-size: 10px; margin-top: 4px; }
    .bottom-nav {
      position: fixed; bottom: 0; left: 0; right: 0; height: calc(56px + var(--safe-bottom));
      padding-bottom: var(--safe-bottom); background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(12px);
      border-top: 1px solid var(--border-line); display: flex; align-items: center; justify-content: space-around;
      z-index: 99; max-width: 640px; margin: 0 auto;
    }
    .nav-tab { display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 10px; color: var(--text-muted); cursor: pointer; border: none; background: transparent; }
    .nav-tab.active { color: var(--primary); font-weight: 700; }
    .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(15,23,42,0.55); z-index: 200; display: none; align-items: flex-end; justify-content: center; }
    .modal-overlay.active { display: flex; }
    .modal-sheet { width: 100%; max-width: 640px; background: #fff; border-top-left-radius: var(--radius-lg); border-top-right-radius: var(--radius-lg); padding: 20px 18px calc(20px + var(--safe-bottom)); max-height: 85vh; overflow-y: auto; }
    .modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; border-bottom: 1px solid var(--border-line); padding-bottom: 12px; }
    .modal-title { font-size: 16px; font-weight: 700; }
    .btn-close-modal { background: var(--bg-body); border: none; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; }
    .share-content { text-align: center; padding: 10px 0; }
    .share-url-box { background: var(--bg-body); border: 1px solid var(--border-line); border-radius: var(--radius-sm); padding: 10px 12px; font-family: monospace; font-size: 13px; color: var(--primary); word-break: break-all; margin: 12px 0; }
    .btn-copy-url { width: 100%; padding: 12px; background: var(--primary); color: #fff; font-size: 14px; font-weight: 700; border: none; border-radius: var(--radius-full); cursor: pointer; }
    .toast {
      position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
      background: rgba(15, 23, 42, 0.9); color: #fff; font-size: 13px; padding: 10px 20px;
      border-radius: var(--radius-full); z-index: 300; opacity: 0; pointer-events: none; transition: opacity 0.2s ease;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <header class="header-bar">
    <div class="brand-wrap">
      <div class="brand-logo">彩</div>
      <div class="brand-title">彩头软件 · 移动商城</div>
      <span class="brand-tag">官方自营</span>
    </div>
    <button class="btn-share" onclick="handleShareClick()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
      <span>分享</span>
    </button>
  </header>
  <main class="app-container">
    <section class="hero-banner">
      <div class="hero-badge">官方正品自营 · 企业实名认证保障</div>
      <h1 class="hero-title">彩头软件移动端服务中心</h1>
      <p class="hero-desc">专业从事计算机软件定制开发、智能数字化工具订阅、技术咨询与系统运维保障服务。</p>
      <div class="hero-features">
        <div>即时开通交付</div>
        <div>实体资质认证</div>
        <div>专业售后保障</div>
      </div>
    </section>
    <div class="section-header">
      <div class="section-title">热销数字化技术服务</div>
      <div style="font-size:11px;color:var(--text-muted);">正规自营交付 · 在线实时核验开通</div>
    </div>
    <section class="product-grid">
      <article class="product-card">
        <div class="product-thumb">
          <div class="product-badge-corner">爆款</div>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        </div>
        <div class="product-info">
          <div>
            <h2 class="product-name">AI 智能生产力旗舰年付订阅服务</h2>
            <p class="product-desc">整合前沿智能化大模型技术，办公文本辅助与知识库助手，个人与工作室提效首选。</p>
            <div class="product-tags"><span class="tag-chip">自动交付</span><span class="tag-chip">独立账号</span><span class="tag-chip">365天保固</span></div>
          </div>
          <div class="product-foot">
            <div class="price-box"><span class="price-symbol">¥</span><span class="price-val">399.00</span><span class="price-original">¥599.00</span></div>
            <button class="btn-buy" onclick="handleShareClick()">获取链接</button>
          </div>
        </div>
      </article>
      <article class="product-card">
        <div class="product-thumb">
          <div class="product-badge-corner">现货</div>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>
        </div>
        <div class="product-info">
          <div>
            <h2 class="product-name">高性能技术开发 API 调用资源包 (1000万额度)</h2>
            <p class="product-desc">高可用云端专线接入，高并发稳定吞吐，适配业务系统、微服务及数据接口集成。</p>
            <div class="product-tags"><span class="tag-chip">实时划拨</span><span class="tag-chip">接口统一</span><span class="tag-chip">长期有效</span></div>
          </div>
          <div class="product-foot">
            <div class="price-box"><span class="price-symbol">¥</span><span class="price-val">199.00</span><span class="price-original">¥280.00</span></div>
            <button class="btn-buy" onclick="handleShareClick()">获取链接</button>
          </div>
        </div>
      </article>
    </section>
    <section class="merchant-profile">
      <div class="profile-title">
        <span>商户经营主体资质公示</span>
        <span style="color:var(--accent);font-size:11px;">已通过实名核验</span>
      </div>
      <div class="profile-row"><span class="profile-label">主办单位名称</span><span class="profile-value">湖南湘江新区彩头软件开发工作室（个体工商户）</span></div>
      <div class="profile-row"><span class="profile-label">商户服务域名</span><span class="profile-value">shop.pricememo.cn</span></div>
      <div class="profile-row"><span class="profile-label">工信部备案号</span><span class="profile-value">湘ICP备2026030136号-1</span></div>
      <div class="profile-row"><span class="profile-label">经营业务范围</span><span class="profile-value">软件开发；信息技术咨询服务；技术服务</span></div>
      <div class="profile-row"><span class="profile-label">服务交付方式</span><span class="profile-value">数字化在线交付 / 远程技术支持</span></div>
    </section>
    <footer class="icp-footer">
      <div>工信部ICP备案号：<a class="icp-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">湘ICP备2026030136号-1</a></div>
      <div>主办单位：湖南湘江新区彩头软件开发工作室（个体工商户）</div>
      <div class="copyright">Copyright © 2026 湖南湘江新区彩头软件开发工作室（个体工商户） 版权所有</div>
    </footer>
  </main>
  <div class="modal-overlay" id="shareModal">
    <div class="modal-sheet">
      <div class="modal-header">
        <div class="modal-title">分享商城给好友</div>
        <button class="btn-close-modal" onclick="closeModal('shareModal')">✕</button>
      </div>
      <div class="share-content">
        <p style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
          扫描二维码或复制下方链接，快速分享访问彩头软件官方商城：
        </p>
        <div class="share-url-box" id="shareUrlDisplay">https://shop.pricememo.cn/</div>
        <button class="btn-copy-url" onclick="copyCurrentShareLink()">一键复制商城链接</button>
      </div>
    </div>
  </div>
  <div class="toast" id="appToast">链接已复制到剪贴板</div>
  <script>
    function getStandardH5Url() {
      if (window.location.protocol.startsWith('http') && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        return window.location.origin + window.location.pathname;
      }
      return 'https://shop.pricememo.cn/';
    }
    function handleShareClick() {
      const url = getStandardH5Url();
      if (navigator.share && /mobile|android|iphone/i.test(navigator.userAgent)) {
        navigator.share({ title: '彩头软件 · 官方移动商城', text: '湖南湘江新区彩头软件开发工作室官方商城', url: url }).catch(() => openModal('shareModal'));
      } else {
        openModal('shareModal');
      }
    }
    function copyCurrentShareLink() {
      const url = getStandardH5Url();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
          showToast('商城链接已成功复制到剪贴板！');
          setTimeout(() => closeModal('shareModal'), 1200);
        });
      }
    }
    function openModal(id) { document.getElementById(id).classList.add('active'); }
    function closeModal(id) { document.getElementById(id).classList.remove('active'); }
    function showToast(msg) {
      const t = document.getElementById('appToast');
      t.textContent = msg; t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2000);
    }
  </script>
</body>
</html>`;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === '/health' || url.pathname === '/status') {
      return new Response(JSON.stringify({
        status: 'ok',
        service: 'shop-pricememo-h5',
        entity: '湖南湘江新区彩头软件开发工作室（个体工商户）',
        icp: '湘ICP备2026030136号-1',
        timestamp: Date.now()
      }), {
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
      });
    }

    if (url.pathname === '/robots.txt') {
      return new Response("User-agent: *\nAllow: /\n", {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    return new Response(HTML_CONTENT, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=60',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  },
};
