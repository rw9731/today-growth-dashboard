// 唯西自建号：读巨量星广任务「Today-唯西星广」的达人视频列表，只读。
// 用法：内置浏览器打开 https://business.oceanengine.com/ebp/material/management/star-task?ebpid=1878449164572746 ，
// resize_window 1400x1000，用 find 找「查看详情」按 ref 点开（只看，不点停投广告、下载、编辑、视频确认），
// 进到「达人视频数据」列表后，把这个文件全文用 javascript_tool 跑一次，返回值原样存成 /tmp/zjh.json，
// 再跑 python3 tools/zjh_merge.py /tmp/zjh.json（只收 tools/zijianhao.json 里 accounts 那几个抖音号的视频）。
// 翻页只点分页器里的页码。
(async () => {
  const out = {};
  const grab = () => {
    const rows = [...document.querySelectorAll('tr')].map((tr) => tr.innerText.replace(/\s+/g, ' ').trim()).filter((t) => /ID:\d{19}/.test(t));
    for (const t of rows) {
      const id = t.match(/ID:(\d{19})/)[1];
      const dy = t.match(/(?:公开可见|仅自己可见|私密|不可见|已删除) (.+?) ID：(\S+)/) || [];
      out[id] = {name: t.split(' ID:')[0], acc: dy[1] || '', dyid: dy[2] || '', st: (t.match(/(公开可见|仅自己可见|私密|已删除|不可见)/) || [''])[0]};
    }
    return rows.length;
  };
  grab();
  const pager = () => [...document.querySelectorAll('[class*="pagination"] *, [class*="pager"] *')].filter((e) => e.children.length === 0 && /^\d+$/.test((e.textContent || '').trim()));
  const n = Math.max(1, ...pager().map((e) => +e.textContent.trim()));
  for (let p = 1; p <= Math.min(n, 30); p++) {
    const el = pager().find((e) => e.textContent.trim() === String(p));
    if (!el) continue;
    el.click();
    await new Promise((r) => setTimeout(r, 2500));
    grab();
  }
  const total = (document.body.innerText.match(/共 (\d+) 条记录/) || [])[1];
  return JSON.stringify({total: total ? +total : null, n: Object.keys(out).length, videos: out});
})();
