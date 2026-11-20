// 排期看板「外部 agency」进度：读悦普执行表、知定堂星广排期表，只读，不写任何单元格（Reina 11/12）。
// 在内置浏览器打开带 ?sheet= 的表格页面，用 javascript_tool 跑这个文件全文，返回的 JSON 原样存成 /tmp/sched/agency/<tab id>.json，再跑 python3 tools/agency_progress.py。
// 悦普 https://my.feishu.cn/wiki/OmjFw42Tpiq8lykD9zzclekTnfd?sheet=5cypAT（11月执行表，每月一张，换月要换 sheet id，存文件名还用 5cypAT.json）：只取抖音、合作形式是星图的行。
// 知定堂 https://my.feishu.cn/wiki/RBAwwr8CRi8xBYkeqQyclodQnny?sheet=et1SeP（排期和审核）：全取，星广都在这张表。
// 素材产出看板另读悦普每月「数据表-小红书」（11 月 3l6KgR，存 yp-xhs.json）和唯西「自建号脚本与成片」（UJsWF1，存 self-published.json）。
const __CFG = {
  yp: { test: (n) => /执行表$/.test(n), want: ['合作平台', '博主名称', '最终合作价', '合作形式', 'use case', '稿件进度', '发布档期', '发布链接', '初稿提交时间'] },
  zdt: { test: (n) => n === '排期和审核', want: ['交付日期', 'UC_ID', '账号名称', '脚本审核情况', '视频链接', '成片审核情况', '成片定稿时间', '发布链接', '素材id'] },
  xhs: { test: (n) => /数据表[-－]小红书$/.test(n), want: ['博主名称', '合作形式', '发布时间', '发布链接'] },
  self: { test: (n) => n === '自建号脚本与成片', want: ['素材命名', 'UC_ID', '成片', '完成时间', '素材ID', '素材名称', '发布情况'] },
};
const __tab = new URL(location.href).searchParams.get('sheet');
let __sh = null, __kind = null;
for (let i = 0; i < 60; i++) {
  try {
    __sh = window.spread && window.spread.getActiveSheet();
    if (__sh && (!__tab || __sh.id() === __tab) && __sh.getText(0, 0)) {
      __kind = Object.keys(__CFG).find((k) => __CFG[k].test(__sh.name()));
      if (__kind) break;
    }
  } catch (e) { /* 还没加载 */ }
  __sh = null; await new Promise((r) => setTimeout(r, 500));
}
if (!__sh) throw new Error('sheet 没加载，或者这个 tab 不在清单里：' + (__tab || location.href));
const __H = []; for (let c = 0; c < __sh.getColumnCount(); c++) __H.push((__sh.getText(0, c) || '').trim());
const __cols = {};
for (const w of __CFG[__kind].want) {
  let c = __H.indexOf(w); if (c < 0) c = __H.findIndex((h) => h.startsWith(w));
  if (c < 0 && __kind === 'yp' && w === '合作平台') c = __H.indexOf('平台');
  if (c < 0) throw new Error(__sh.name() + ' 找不到表头：' + w + '，现在的表头：' + __H.join('|'));
  __cols[w] = c;
}
const __t = (r, w) => (__sh.getText(r, __cols[w]) || '').trim();
// 一格里有几条：附件个数和链接个数取大的（知定堂一行常传真人版、AI 版两条）
const __n = (r, w) => { let a = 0; try { a = (__sh.getSegmentArray(r, __cols[w]) || []).filter((s) => s.type === 'attachment').length; } catch (e) { /* 没有附件 */ } const u = (__t(r, w).match(/https?:\/\//g) || []).length; return Math.max(a, u, __t(r, w) && !a && !u ? 1 : 0); };
const __files = (r, w) => { const out = []; try { for (const x of (__sh.getSegmentArray(r, __cols[w]) || [])) { if (x.type === 'attachment' && x.text) out.push(x.text.slice(0, 80)); } } catch (e) { /* 没有附件 */ } for (const u of (__t(r, w).match(/https?:\/\/\S+/g) || [])) out.push(u.slice(0, 120)); return out; };
const __has = (r, w) => { if (__t(r, w)) return 1; try { return (__sh.getSegmentArray(r, __cols[w]) || []).some((s) => s.type === 'attachment') ? 1 : 0; } catch (e) { return 0; } };
const __rows = [];
for (let r = 1; r < __sh.getRowCount(); r++) {
  if (__kind === 'yp') {
    if (!/抖/.test(__t(r, '合作平台')) || !/^星图/.test(__t(r, '合作形式'))) continue;
    __rows.push({ r: r + 1, name: __t(r, '博主名称').slice(0, 30), price: __t(r, '最终合作价'), uc: __t(r, 'use case').slice(0, 30), st: __t(r, '稿件进度').split('\n')[0].slice(0, 12), d: __t(r, '发布档期').slice(0, 16), pub: __has(r, '发布链接') });
  } else if (__kind === 'xhs') {
    const format = __t(r, '合作形式'), d = __t(r, '发布时间');
    const post = __t(r, '发布链接').split(/[?#]/)[0].replace(/\/$/, '').split('/').at(-1);
    if (format.includes('视频') && d && post) __rows.push({ r: r + 1, name: __t(r, '博主名称'), format, d, post });
  } else if (__kind === 'self') {
    const status = __t(r, '发布情况');
    if (status !== '已发') continue;
    const d = __sh.getText(r, __H.lastIndexOf('完成时间')).trim() || __t(r, '完成时间');
    const file = (__sh.getSegmentArray(r, __cols['成片']) || []).find((s) => s.type === 'attachment')?.text;
    const name = __t(r, '素材名称') || __t(r, '素材命名') || file || '';
    __rows.push({ r: r + 1, name, d, status, id: __t(r, '素材ID'), uc: __t(r, 'UC_ID') });
  } else {
    if (!__t(r, '交付日期') && !__t(r, 'UC_ID')) continue;
    __rows.push({ r: r + 1, d: __t(r, '交付日期').slice(0, 12), uc: __t(r, 'UC_ID').slice(0, 6), acct: __t(r, '账号名称').slice(0, 20), sst: __t(r, '脚本审核情况').split('\n')[0].slice(0, 8), vid: __n(r, '视频链接'), files: __files(r, '视频链接'), vst: __t(r, '成片审核情况').split('\n')[0].slice(0, 8), fin: __t(r, '成片定稿时间').slice(0, 12), pub: __has(r, '发布链接'), mid: __t(r, '素材id') ? 1 : 0 });
  }
}
JSON.stringify({ kind: __kind, sheet: __tab, name: __sh.name(), rows: __rows });
