// 排期进度：读一个飞书 tab，只读，不写任何单元格。
// 在内置浏览器打开带 ?sheet=<tab id> 的表格页面（切 tab 只能靠 URL），用 javascript_tool 跑这个文件全文，返回值原样存成 <输出目录>/<tab id>.json。
// A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片、nPw5Dc 新素材每周排期
// B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪、3KtioB 扩量素材迭代排期
// 本周实际产出还要读 A 组两个 tab：lheDJa 星广脚本审核表、L1c0HC 付费达人执行表（星图达人）。
// 然后跑 python3 tools/schedule_progress.py，见 tools/RUN.md「排期看板（每天）」。
// 返回值要原样存成文件，所以只留算进度要的字段，只留最近 10 天的行。
const __WANT = {
  '扩量素材迭代排期': ['日期', 'UC_ID', '条数', '怎么改', '扩量素材名'],
  '脚本及成片': ['素材命名', 'UC_ID', '成片', '完成时间', '成片状态'],
  '新素材每周排期': ['日期', 'UC_ID', '注意事项'],
  '脚本&成片': ['产出日期', 'UC_ID', '脚本备注', '成片', '完成时间?'],
  '真人素材和ai切片二剪': ['产出日期', 'UC_ID', '备注?', '二创成片'],
  '星广脚本审核表': ['UC_ID', '视频链接', '成片完成时间'],
  '付费达人执行表': ['合作形式', 'uc_id', '视频链接', '发布时间', '发布链接'],
};
// 文件名里的日期：_20261104、-261104。返回 MMDD，没有就空。
const __fd = (t) => { const L = [...(t || '').matchAll(/(?<![0-9a-zA-Z])(?:20)?26(\d{2})(\d{2})(?!\d)/g)].filter((m) => +m[1] >= 1 && +m[1] <= 12); return L.length ? L[L.length - 1][1] + L[L.length - 1][2] : ''; }; // 改过的版本名字里有好几个日期，取最后一个
// 调整写在开头的【】里（【11/4 调整：顺延下周，这周先不拍】）。正文里也可能出现「先不拍」，那种不算。
const __TAG = /【(AI|AI 切片二剪|二创[^】]*|重配[^】]*)】|还要做，\d{1,2}\/\d{1,2} ?交|拍 ?\d+ ?条/g;
const __tags = (t) => {
  const adj = /^【[^】]*(先不[拍剪做审]|顺延)[^】]*】/.exec(t);
  const keep = adj ? ((/(\d+) ?条照做/.exec(adj[0]) || [])[0] || '') + ' 先不做' : '';
  return ((t.match(__TAG) || []).join(' ') + ' ' + keep).trim();
};
const __OLD = Date.now() - 10 * 864e5;
const __isOld = (s) => {
  let m = /^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})/.exec(s || '');
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).getTime() < __OLD;
  m = /^(?:\d{2}年)?(\d{1,2})[\/月](\d{1,2})/.exec(s || '');
  return !!m && new Date(new Date().getFullYear(), +m[1] - 1, +m[2]).getTime() < __OLD;
};
const __url = new URL(location.href);
const __tab = __url.searchParams.get('sheet');
let __sh = null;
for (let i = 0; i < 60; i++) {
  try {
    __sh = window.spread && window.spread.getActiveSheet();
    if (__sh && (!__sh.id || !__tab || __sh.id() === __tab) && __WANT[__sh.name()] && __sh.getText(0, 0)) break;
    __sh = null;
  } catch (e) { __sh = null; }
  await new Promise((r) => setTimeout(r, 500));
}
if (!__sh) throw new Error('sheet 没加载，或者这个 tab 不在清单里：' + (__tab || location.href));
const __name = __sh.name();
const __hdr = [];
for (let c = 0; c < __sh.getColumnCount(); c++) __hdr.push((__sh.getText(0, c) || '').trim());
const __cols = {};
for (const w of __WANT[__name]) {
  let c = __hdr.indexOf(w);
  if (c < 0) c = __hdr.findIndex((h) => h.startsWith(w));
  if (c < 0 && w === '日期' && __name === '扩量素材迭代排期') c = 0; // A 组这张表 A1 在 11/5 被改成了「照真人」，A 列内容还是日期
  if (c < 0 && w.endsWith('?')) continue; // 可选列，这张表没有就跳过
  if (c < 0) throw new Error(__name + ' 找不到表头：' + w + '，现在的表头：' + __hdr.join('|'));
  __cols[w] = c;
}
const __cell = (r, c) => {
  let t = (__sh.getText(r, c) || '').trim();
  if (!t) {
    try { t = (__sh.getSegmentArray(r, c) || []).filter((s) => s.type === 'attachment').map((s) => s.text).join('\n').trim(); } catch (e) { /* 这一格没有附件 */ }
  }
  return t;
};
const __rows = [];
const __dateCol = ['日期', '产出日期'].find((w) => __cols[w] !== undefined);
let __day = '';
for (let r = 1; r < __sh.getRowCount(); r++) {
  if (__dateCol) { const d = __cell(r, __cols[__dateCol]); if (d) __day = d; }
  if (__day && __isOld(__day)) continue; // 日期是合并单元格，往下带
  const row = { r: r + 1 };
  let any = false;
  for (const w of __WANT[__name]) {
    if (__cols[w] === undefined) continue;
    const t = __cell(r, __cols[w]);
    if (!t) continue;
    any = true;
    const k = w.replace('?', '');
    if (w === '扩量素材名') { // 条数，加上每条文件名里的日期（实际产出按它算）
      const L = t.split('\n').filter((s) => s.trim());
      row[k] = L.length;
      row.ds = L.map(__fd);
      row.nec = L.filter((x) => /二创/.test(x)).length; // 文件名含二创的条数，这一行没写类型时用
    }
    else if (w === '成片' || w === '二创成片') { row[k] = 1; const d = __fd(t); if (d) row.fd = d; } // 有没有，加文件名里的日期
    else if (w === '视频链接' || w === '发布链接') { row[k] = 1; const d = __fd(t); if (d) row.fd = d; }
    else if (w === '完成时间?' || w === '成片完成时间' || w === '发布时间') row[k] = t.slice(0, 14);
    else if (w === '怎么改' || w === '注意事项') row[k] = __tags(t); // 开头可能有很长的调整说明
    else if (w === '脚本备注' || w === '备注?') { if (/先不[拍剪做审]|顺延/.test(t)) row[k] = '先不做'; }
    else if (w === '日期' || w === '产出日期') row[k] = t.slice(0, 10);
    else if (w === '成片状态') row[k] = t.includes('通过') ? '通过' : t.slice(0, 8);
    else row[k] = t.split('\n')[0].slice(0, 12);
  }
  if (__name === '星广脚本审核表' && (!row['视频链接'] || __isOld(row['成片完成时间']))) any = false;
  if (__name === '付费达人执行表' && !row['发布时间'] && !row['发布链接']) any = false;
  if (__name === '脚本及成片') {
    if (/二创|KOC|KOL|原片/i.test(__cell(r, __cols['素材命名']) + ' ' + __cell(r, __cols['成片']))) row.ec = 1; // 剪真人原片的，算二创
    if (!row['成片'] || !row['完成时间'] || __isOld(row['完成时间'])) any = false;
    if (!row['UC_ID']) { // 11/2 起这列没填，UC 在素材命名或者成片文件名里
      const m = /(?:^|[^A-Za-z])([A-Z]{2}\d{2})(?!\d)/.exec(__cell(r, __cols['素材命名']) + ' ' + __cell(r, __cols['成片']));
      if (m) row['UC_ID'] = m[1];
    }
  }
  if (any) __rows.push(row);
}
let __out = __rows;
if (__name === '脚本及成片') { // 500 多行，按 use case 和完成时间合起来：n 是成片条数，rv 是还没通过的条数
  const m = {};
  for (const x of __rows) {
    const k = (x['UC_ID'] || '') + '|' + x['完成时间'];
    m[k] = m[k] || { r: 0, UC_ID: x['UC_ID'], 完成时间: x['完成时间'], 成片: 1, n: 0, rv: 0, ec: 0 };
    m[k].n += 1;
    if (x.ec) m[k].ec += 1;
    if (x['成片状态'] !== '通过') m[k].rv += 1;
  }
  __out = Object.values(m);
}
JSON.stringify({ tab: __name, sheet: __tab, doc: __url.pathname.split('/').pop(), rows: __out });
