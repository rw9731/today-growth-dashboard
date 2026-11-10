// 素材产出看板：读一个飞书 tab 里这几天交的素材，只读，不写任何单元格（Reina 11/10）。
// 在内置浏览器打开带 ?sheet=<tab id> 的表格页面，用 javascript_tool 跑这个文件全文。跑之前把下面 SINCE 改成要读的第一天（MMDD）。
// 返回一段文本，每行一条素材，用 \t 分隔：组 表 行号 成片列 日期MMDD UC 细分场景 类型(V 变式 / S 同脚本换画面 / N 新测试 / X 只换前贴不计) AI或二创(A/E) 素材名
// 原样存成 <输出目录>/<tab id>.tsv，再跑 python3 tools/output_build.py，见 tools/RUN.md「素材产出看板」。
// A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片
// B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：3KtioB 扩量素材迭代排期、c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪
const SINCE = '1109';
const __CFG = {
  kMJdAv: { g: 'A', kind: 'kx', file: '迭代素材成片' },
  '3KtioB': { g: 'B', kind: 'kx', file: '扩量素材名' },
  f18d7b: { g: 'A', kind: 'sc', name: '素材命名', file: '成片', date: '完成时间' },
  c665d9: { g: 'B', kind: 'sc', name: '素材命名', file: '成片', date: '产出日期' },
  EnYgPG: { g: 'B', kind: 'ec', name: '素材命名', file: '二创成片', date: '产出日期' },
};
const __tab = new URL(location.href).searchParams.get('sheet');
const __cfg = __CFG[__tab];
if (!__cfg) throw new Error('这个 tab 不在清单里：' + __tab);
let __sh = null;
for (let i = 0; i < 60; i++) {
  try { __sh = window.spread && window.spread.getActiveSheet(); if (__sh && __sh.id() === __tab && __sh.getText(0, 1)) break; } catch (e) { /* 还没加载 */ }
  __sh = null; await new Promise((r) => setTimeout(r, 500));
}
if (!__sh) throw new Error('sheet 没加载：' + __tab);
const __H = []; for (let c = 0; c < __sh.getColumnCount(); c++) __H.push((__sh.getText(0, c) || '').trim());
const __col = (w) => { let c = __H.indexOf(w); if (c < 0) c = __H.findIndex((h) => h.startsWith(w)); return c; };
const __txt = (r, c) => (c < 0 ? '' : (__sh.getText(r, c) || '').trim());
const __att = (r, c) => { try { return (__sh.getSegmentArray(r, c) || []).filter((s) => s.type === 'attachment').map((s) => s.text); } catch (e) { return []; } };
const __L = (n) => { let s = ''; n += 1; while (n) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; };
const __fd = (t) => { const L = [...(t || '').matchAll(/(?<![0-9a-zA-Z])(?:20)?26(\d{2})(\d{2})(?!\d)/g)].filter((m) => +m[1] >= 1 && +m[1] <= 12); return L.length ? L[L.length - 1][1] + L[L.length - 1][2] : ''; };
const __md = (s) => { let m = /^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})/.exec(s || ''); if (m) return String(m[2]).padStart(2, '0') + String(m[3]).padStart(2, '0'); m = /^(?:\d{2}年)?(\d{1,2})[\/月](\d{1,2})/.exec(s || ''); return m ? String(m[1]).padStart(2, '0') + String(m[2]).padStart(2, '0') : ''; };
const __clean = (s) => s.replace(/\.(mp4|mov|m4v)$/i, '').replace(/[\t\n]/g, ' ').trim();
const __kindOf = (name, how) => (/换前贴/.test(name) ? 'X' : /同脚本换画面/.test(name) || /^(【[^】]*】)*【AI｜同脚本换画面/.test(how) ? 'S' : /头部模板/.test(how) ? 'V' : 'N');
const __out = [];
const cUC = __col('UC_ID'), cSc = __col('细分场景'), cTy = __col('素材类型'), cHow = __col('怎么改'), cBasis = __col('依据'), cFile = __col(__cfg.file);
if (__cfg.kind === 'kx') {
  const cName = __col('扩量素材名');
  let day = '';
  for (let r = 1; r < __sh.getRowCount(); r++) {
    const d = __md(__txt(r, 0)); if (d) day = d;
    let names = __txt(r, cName).split('\n').map((s) => s.trim()).filter((s) => /[_-]/.test(s) && s.length >= 10 && !/待制作|已贴表|脚本已/.test(s)); // B 组这一格有时写的是「脚本已贴表，待制作」
    if (!names.length) names = __att(r, cFile);
    if (!names.length) continue;
    const how = __txt(r, cHow) + ' ' + __txt(r, cBasis), ty = __txt(r, cTy);
    for (const n0 of names) {
      const n = __clean(n0), d2 = __fd(n) || day;
      if (!d2 || d2 < SINCE) continue;
      const t = /二创/.test(ty) || (!ty && /二创|KOC|KOL/i.test(n)) ? 'E' : 'A';
      __out.push([__cfg.g, __tab, r + 1, __L(cFile), d2, __txt(r, cUC).split('\n')[0].slice(0, 6), __txt(r, cSc).split('：')[0].slice(0, 24), __kindOf(n, how), t, n].join('\t'));
    }
  }
} else {
  const cName = __col(__cfg.name), cDate = __col(__cfg.date);
  let day = '';
  for (let r = 1; r < __sh.getRowCount(); r++) {
    const d = __md(__txt(r, cDate)); if (__tab === 'f18d7b') day = d; else if (d) day = d; // A 组脚本表完成时间每行都填，B 组产出日期是合并单元格
    const files = __att(r, cFile);
    if (!files.length && !__txt(r, cFile)) continue;
    const ok = (x) => /[_-]/.test(x) && x.length >= 10 && !/待制作|已贴表|务必/.test(x);
    let names = __txt(r, cName).split(/\n/).map((x) => x.trim()).filter(ok); // 二剪表一格里常写好几条素材名
    if (!names.length) names = (files.length ? files : [__txt(r, cFile)]).map(__clean).filter(ok);
    for (const n0 of names) {
      const n = __clean(n0), d2 = __fd(n) || __fd(files[0] || '') || day;
      if (!d2 || d2 < SINCE) continue;
      let uc = __txt(r, cUC).split('\n')[0].slice(0, 6); if (!uc) { const m = /(?:^|[^A-Za-z])([A-Z]{2}\d{2})(?!\d)/.exec(n); if (m) uc = m[1]; }
      const t = __cfg.kind === 'ec' || /二创|KOC|KOL/i.test(n) ? 'E' : 'A';
      __out.push([__cfg.g, __tab, r + 1, __L(cFile), d2, uc, __txt(r, cSc).split('：')[0].slice(0, 24), __kindOf(n, ''), t, n].join('\t'));
    }
  }
}
__out.join('\n');
