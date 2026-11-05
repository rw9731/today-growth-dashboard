// 内容下钻看操作：在已登录的巨量页面（ad.oceanengine.com，素材中心）里跑，只读。账户列表它自己拉。
// 用法：改最后一行的日期，跑完（4 并发，668 户约 3.5 分钟，跑的时候 tab 不能离开这个页面）取 window.__acct['YYYY-MM-DD']。
// 结果：by[素材ID] = [[账户id, 消耗], ...]，acc[账户id] = {name, ct}。账户名带「B组」的是 2 组（熊斌那组），不带的是 1 组（金铭那组）。
// 按账户对比要扫 D 和 D-1 两天。
(async (DAY) => {
  const root = '1878223927194825';
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
  const acc = {};
  for (let p = 1; ; p++) {
    const j = await (await fetch(`/ad/api/navigator/advertiser/list?page=${p}&limit=50&keyword=&aadvid=${root}`, { credentials: 'include' })).json();
    const L = j.data.user_account_infos || [];
    for (const x of L) acc[x.id] = { name: x.name, ct: x.create_time };
    if (!L.length || p >= j.data.total_pages) break;
  }
  const ACCTS = Object.keys(acc);
  window.__acct = window.__acct || {};
  const S = (window.__acct[DAY] = { st: 'run', day: DAY, done: 0, cost: 0, err: 0, by: {}, acc });
  let i = 0;
  const one = async (a) => {
    for (let page = 1; ; page++) {
      let j;
      try {
        const r = await fetch('/material_center/api/v1/analysis/adv/video/material_list?aadvid=' + a, {
          method: 'POST', credentials: 'include',
          headers: { 'content-type': 'application/json', 'x-csrftoken': csrf },
          body: JSON.stringify({ fields: ['stat_cost', 'active'], order_field: 'stat_cost', order_type: 2, statistic_start_time: DAY + ' 00:00:00', statistic_end_time: DAY + ' 23:59:59', page, limit: 50, scene: '2D373838343330373937' }),
        });
        j = await r.json();
      } catch (e) { S.err++; return; }
      const d = j.data || {}, L = d.materials || d.list || d.material_list || [];
      let any = false;
      for (const m of L) {
        const id = String(m.material_id || m.id || (m.video_info && m.video_info.material_id) || ''), c = +((m.metrics && m.metrics.stat_cost) || 0);
        if (c > 0) { any = true; S.cost += c; (S.by[id] = S.by[id] || []).push([a, c]); }
      }
      if (!any || L.length < 50) return;
    }
  };
  const worker = async () => { while (i < ACCTS.length) { await one(ACCTS[i++]); S.done++; } };
  await Promise.all([worker(), worker(), worker(), worker()]);
  S.st = 'done';
})('YYYY-MM-DD');
