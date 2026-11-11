// 巨量广告智擎版投放管理页跑（只调查询接口，不点按钮）。ADVS 换成当天花过钱的账户（conc.json 里的账户）；T0/T1 是 D-9 到 D。
// 跑完反复 await __pjWait() 到 st=done，再 JSON.stringify({pjk:k, d:__pjGet(k)}) 按 k=0,1,2… 取，每行 \t 分隔：adv pid 创建时间 项目名 预算 出价 深度出价 状态 消耗 素材ID:消耗|…
{ const ADVS = [/* 账户ID */];
const T0 = Date.parse('2026-11-01T00:00:00+08:00'), T1 = Date.parse('2026-11-10T23:59:59+08:00');
const post = async (u, b) => { for (let i = 0; ; i++) { const r = await fetch(u, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)}); const t = await r.text(); try { return JSON.parse(t); } catch (e) { if (i >= 3) throw new Error('HTTP ' + r.status); await new Promise((z) => setTimeout(z, 1500 * (i + 1))); } } };
window.__pj = {st: 'run', done: 0, of: ADVS.length, out: [], err: [], old: 0};
const one = async (adv) => {
  const ps = [];
  for (let off = 0; off < 2000; off += 100) { const j = await post('/ad/api/agw/promotion/std/projects/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['cdp_project_id', 'cdp_project_name', 'promotion_id', 'cdp_promotion_id', 'advertiser_id'], fields: ['stat_cost'], limit: 100, offset: off, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1}, filter: {}});
    if (j.code !== 0) { __pj.err.push(adv + ' projects ' + j.code); return; } const rs = (j.data && j.data.rows) || []; ps.push(...rs); if (rs.length < 100) break; }
  for (const p of ps) {
    if ((p.create_time || '') < '2026-10-25') { __pj.old++; continue; }
    const ms = [];
    for (let off = 0; off < 1000; off += 100) { const mj = await post('/ad/api/std/promotion/materials/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['material_id', 'advertiser_id', 'lego_mid'], fields: ['stat_cost'], limit: 100, offset: off, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1, needProjectBasicStats: false}, filter: {materialFilter: {type: 3, materialStatusFirst: [-1], autoMaterialSources: [0, 18]}, promotion: {promotionIds: [p.promotion_id]}, stdProject: {projectIds: [p.project_id]}, isAigc: false, isAutoStar: false, isLive: false}});
      if (mj.code !== 0) { __pj.err.push(adv + '/' + p.project_id + ' mats ' + mj.code); break; } const rs = (mj.data && mj.data.rows) || []; for (const r of rs) ms.push(r.material_id + ':' + (parseFloat(String((r.metrics || {}).stat_cost || 0).replace(/,/g, '')) || 0)); if (rs.length < 100) break; }
    __pj.out.push([adv, p.project_id, p.create_time, p.project_name, p.campaign_budget, p.project_bid, p.project_deep_cpa_bid, p.oc_project_status_first_name, (p.metrics || {}).stat_cost, ms.join('|')].join('\t'));
  }
};
(async () => { const q = ADVS.slice(); const run = async () => { while (q.length) { const a = q.shift(); try { await one(a); } catch (e) { __pj.err.push(a + ' ' + e); } __pj.done++; } }; await Promise.all([run(), run(), run(), run()]); __pj.st = 'done'; })();
window.__pjWait = async () => { for (let i = 0; i < 40 && __pj.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __pj.st, done: __pj.done, of: __pj.of, rows: __pj.out.length, err: __pj.err.slice(0, 10)}); };
window.__pjGet = (k) => __pj.out.slice(k * 150, k * 150 + 150).join('\n');
}
'started'
