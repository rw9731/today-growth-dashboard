// 素材产出看板「还没成片的脚本」：读脚本表和扩量排期当下的状态，只读，不写任何单元格（Reina 11/11）。
// 只看最新时间点，不追溯过去：每天跑一次，结果只放进当周页面。
// 4 个 tab 都要跑：在内置浏览器打开带 ?sheet=<tab id> 的表格页面，用 javascript_tool 跑这个文件全文，返回的 JSON 原样存成 /tmp/out/stage_<tab id>.json，再跑 output_build.py。
// A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：f18d7b 脚本及成片、kMJdAv 扩量素材迭代排期
// B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9 脚本&成片、3KtioB 扩量素材迭代排期
// 脚本表：「脚本状态」是需修改 / 修改后待审核 / 未审核（或空） = 还在脚本中；「脚本状态」是可制作、「成片」还空着 = 脚本已完成、还没开始做。
// 成片有了的、脚本未通过的、脚本备注写了先不拍 / 不用拍 / 弃用 / 顺延这类的都不算（Reina 11/11：说了不要做的、弃用的不算）。A 组从第 485 行（11 月起）读。
// 扩量排期：每行的日期（合并单元格往下带）和这一行是不是叫停了（怎么改、成片备注里写了先不拍 / 弃用 / 顺延这类），B 组再带上扩量素材名里写的脚本表行号（「45，46脚本已贴表」）。
// output_build.py 用它们给脚本定交付日：「脚本已完成、还没开始做」只算交付日在本周的（Reina 11/11），排期行叫停了的也不算。
const __KILL = /先不[拍做剪审]|顺延|不用[拍做]|别[拍做]|不要[拍做]|弃用|作废|停[拍做]|不拍了|不做了|取消/;
const __CFG = { f18d7b: { g: 'A', kind: 'sc', start: 485, name: '' }, c665d9: { g: 'B', kind: 'sc', start: 2, name: '素材命名', date: '产出日期' },
  kMJdAv: { g: 'A', kind: 'kx' }, '3KtioB': { g: 'B', kind: 'kx' } };
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
const __col = (w) => __H.findIndex((h) => h === w || h.startsWith(w));
const __t = (r, c) => (c < 0 ? '' : (__sh.getText(r, c) || '').trim());
const __md = (s) => { const m = /^(?:\d{4}[\/-])?(\d{1,2})[\/-月](\d{1,2})/.exec(s || ''); return m ? String(m[1]).padStart(2, '0') + String(m[2]).padStart(2, '0') : (/^下周/.test(s || '') ? 'next' : ''); };
let out;
if (__cfg.kind === 'kx') {
  const cHow = __col('怎么改'), cNote = __col('成片备注'), cName = __col('扩量素材名');
  out = { tab: __tab, g: __cfg.g, rows: {} };
  let day = '';
  for (let r = 1; r < __sh.getRowCount(); r++) {
    const d = __md(__t(r, 0)); if (d) day = d;
    const x = { d: day };
    if (__KILL.test(__t(r, cHow) + ' ' + __t(r, cNote))) x.x = 1;
    const refs = (__t(r, cName).match(/([\d，,、\s]+)脚本已/) || ['', ''])[1].match(/\d+/g); if (refs) x.sc = refs.map(Number);
    out.rows[r + 1] = x;
  }
} else {
  const cSt = __col('脚本状态'), cNote = __col('脚本备注'), cFile = __col('成片'), cUC = __col('UC_ID'), cSc = __col('脚本'), cName = __cfg.name ? __col(__cfg.name) : 0, cD = __cfg.date ? __col(__cfg.date) : -1;
  if (cSt < 0 || cFile < 0) throw new Error('header not found');
  out = { tab: __tab, g: __cfg.g, start: __cfg.start, in_script: [], ready: [], killed: 0 };
  for (let r = __cfg.start - 1; r < __sh.getRowCount(); r++) {
    const st = __t(r, cSt).split('\n')[0], sc = __t(r, cSc), file = __t(r, cFile), note = __t(r, cNote);
    if (!st && !sc) continue;
    if (file || /未通过/.test(st)) continue;
    if (__KILL.test(note)) { out.killed++; continue; }
    let name = __t(r, cName).split('\n')[0];
    if (!/[_-]/.test(name) || name.length < 6) name = sc.split('\n')[0];
    let uc = __t(r, cUC).split('\n')[0].slice(0, 6); if (!uc) { const m = /(?:^|[^A-Za-z])([A-Z]{2}\d{2})(?!\d)/.exec(name + ' ' + sc.slice(0, 200)); if (m) uc = m[1]; }
    const x = { r: r + 1, uc, st: st || '未审核', name: name.slice(0, 80) };
    const d = cD >= 0 ? __md(__t(r, cD)) : ''; if (d) x.d = d;
    (st === '可制作' ? out.ready : out.in_script).push(x);
  }
}
JSON.stringify(out);
