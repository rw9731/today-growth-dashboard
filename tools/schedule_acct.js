// 内容下钻看操作：在已登录的巨量页面（ad.oceanengine.com，素材中心）里跑，只读。
// 用法：把账户 id 列表放进 ACCTS，改 DAY，跑完取 window.__acct。4 并发，668 户约 3.5 分钟，跑的时候 tab 不能离开这个页面。
// 结果：by[素材ID] = [[账户id, 消耗], ...]，acc[账户id] = {name, ct}。账户名带「B组」的是 2 组（熊斌那组），不带的是 1 组（金铭那组）。
(async (DAY, ACCTS) => {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
  const S = (window.__acct = { st: 'run', day: DAY, done: 0, cost: 0, err: 0, by: {} });
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
})(/* DAY */ 'YYYY-MM-DD', /* ACCTS */ []);
