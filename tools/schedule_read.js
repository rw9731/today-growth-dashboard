// 排期进度：读一个飞书 tab，只读，不写任何单元格。
// 在内置浏览器打开带 ?sheet=<tab id> 的表格页面（切 tab 只能靠 URL），用 javascript_tool 跑这个文件全文，返回值原样存成 <输出目录>/<tab id>.json。
// A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片、nPw5Dc 新素材每周排期
// B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪、3KtioB 扩量素材迭代排期
// 然后跑 python3 tools/schedule_progress.py，见 tools/RUN.md「排期看板（每天）」。
const __WANT = {
  '扩量素材迭代排期': ['日期', 'UC_ID', 'Use case', '条数', '怎么改', '是否做了', '扩量素材名'],
  '脚本及成片': ['素材命名', 'UC_ID', '脚本状态', '成片', '完成时间', '成片状态'],
  '新素材每周排期': ['周', '日期', 'UC_ID', 'Use case', '注意事项'],
  '脚本&成片': ['产出日期', '素材命名', 'UC_ID', '脚本状态', '成片', '完成时间', '成片状态'],
  '真人素材和ai切片二剪': ['产出日期', '素材命名', 'UC_ID', '二创成片'],
};
const __KEEP = { '怎么改': 60, '注意事项': 60, 'Use case': 24, '素材命名': 60 };
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
for (let r = 1; r < __sh.getRowCount(); r++) {
  const row = { r: r + 1 };
  let any = false;
  for (const w of __WANT[__name]) {
    const t = __cell(r, __cols[w]);
    if (!t) continue;
    any = true;
    if (w === '扩量素材名') row[w] = t.split('\n').map((s) => s.trim()).filter(Boolean).map((s) => s.slice(-30)); // 只要条数和名字结尾
    else row[w] = __KEEP[w] ? t.slice(0, __KEEP[w]) : t;
  }
  if (any) __rows.push(row);
}
JSON.stringify({ tab: __name, sheet: __tab, doc: __url.pathname.split('/').pop(), rows: __rows });
