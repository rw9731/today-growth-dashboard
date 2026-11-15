// 截日报「七、拖后腿的素材 · 判差 3 天以上还在花」这一块（Reina 11/15：发投放群时带图）。
// 用法：node tools/shot_stuck.js D [d3.min.js 路径]  → shots/stuck-D.png；同时打印表里每行（素材、判差、昨天消耗、判差后多花）。
// CDN 在沙箱里打不开，d3 用本地文件（npm pack d3@7.8.5 解出来的 dist/d3.min.js）。
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const ROOT = path.dirname(__dirname); const D = process.argv[2]; const D3 = process.argv[3] || '/tmp/h/d3.min.js';
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
  await p.route('**/*', r => { const u = r.request().url(); if (u.includes('d3')) return r.fulfill({ body: fs.readFileSync(D3), contentType: 'application/javascript' }); if (u.startsWith('file:')) return r.continue(); return r.abort(); });
  await p.goto('file://' + path.join(ROOT, D, 'index.html')); await p.waitForTimeout(3000);
  const box = await p.evaluate(() => {
    const tb = document.querySelector('[data-draw="stuckrows"]'); const sec = document.getElementById('bad');
    const h2 = sec.querySelector('.lx-h2'); const card = tb.closest('.lx-card');
    const a = h2.getBoundingClientRect(), c = card.getBoundingClientRect();
    const rows = [...tb.querySelectorAll('tr')].map(tr => [...tr.children].map(td => td.innerText.replace(/\s+/g, ' ').trim()));
    return { x: Math.max(0, Math.min(a.left, c.left) - 12), y: a.top + window.scrollY - 12, w: Math.max(a.width, c.width) + 24, h: c.bottom - a.top + 24, rows };
  });
  fs.mkdirSync(path.join(ROOT, 'shots'), { recursive: true });
  const out = path.join(ROOT, 'shots', `stuck-${D}.png`);
  await p.screenshot({ path: out, clip: { x: box.x, y: box.y, width: box.w, height: box.h }, fullPage: true });
  console.log(JSON.stringify({ out, rows: box.rows }, null, 0)); await b.close();
})();
