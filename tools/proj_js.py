"""冷启的项目数据（Reina 11/11）：新素材建进了哪些项目、新建项目有没有起量。写 proj.js，在巨量广告智擎版投放管理页跑。

用法：
1. python3 tools/proj_js.py --date D --ebp /tmp/linkjs/conc.json --out /tmp/linkjs  → 写 proj.js（账户 = 集中度第 1 步 conc.json 里 D 花过钱的账户）。
2. 打开 https://ad.oceanengine.com/ad/web/std/manage?aadvid=1879654096082505 （只看不点），javascript_tool 跑 proj.js 全文（返回 started），
   反复跑 `await __pjWait()` 到 st 是 done（约 5 到 10 分钟），再依次跑 `__pjGet(0)`、`__pjGet(1)`……每次返回值原样存成 /tmp/linkjs/proj_k.json，直到 d 是空字符串。
   返回值太长被存成文件的，从那个文件里解析出来再存，不手抄。
3. python3 tools/proj_save.py --date D /tmp/linkjs/proj_*.json → notes/proj-D.json，compute.py 默认读它。
只调查询接口（std/projects/list、std/promotion/materials/list），不点任何按钮。只查智擎户，普通户不在内。
每行：账户 \\t 项目ID \\t 创建时间 \\t 项目名 \\t 预算 \\t 出价 \\t 深度出价 \\t 状态 \\t D-9 到 D 消耗 \\t 素材数 \\t 有消耗的素材（ID:消耗|…） \\t D-14 起上传的素材（ID|…）
"""
import argparse, datetime as dt, json, os

PAGE = 'https://ad.oceanengine.com/ad/web/std/manage?aadvid=1879654096082505'

JS = r"""// 在这个页面跑（巨量广告智擎版投放管理，只看不点）：__PAGE__
{ const D = "__D__", ADVS = __ADVS__, RECENT = "__RECENT__";
const T0 = Date.parse("__D0__T00:00:00+08:00"), T1 = Date.parse(D + 'T23:59:59+08:00');
const upDay = (id) => { try { return new Date(Number(BigInt(id) >> 32n) * 1000 + 8 * 3600000).toISOString().slice(0, 10); } catch (e) { return ''; } };
const post = async (u, b) => { for (let i = 0; ; i++) { const r = await fetch(u, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)}); const t = await r.text(); try { return JSON.parse(t); } catch (e) { if (i >= 3) throw new Error('HTTP ' + r.status); await new Promise((z) => setTimeout(z, 1500 * (i + 1))); } } };
const num = (s) => parseFloat(String(s == null ? 0 : s).replace(/,/g, '')) || 0;
window.__pj = {st: 'run', done: 0, of: ADVS.length, out: [], err: []};
const one = async (adv) => {
  const ps = [];
  for (let off = 0; off < 3000; off += 100) {
    const j = await post('/ad/api/agw/promotion/std/projects/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['cdp_project_id', 'cdp_project_name', 'promotion_id', 'cdp_promotion_id', 'advertiser_id'], fields: ['stat_cost'], limit: 100, offset: off, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1}, filter: {}});
    if (j.code !== 0) { __pj.err.push(adv + ' projects ' + j.code); return; }
    const rs = (j.data && j.data.rows) || []; ps.push(...rs); if (rs.length < 100) break; }
  for (const p of ps) {
    let n = 0; const sp = [], rc = [];
    for (let off = 0; off < 2000; off += 100) {
      const mj = await post('/ad/api/std/promotion/materials/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['material_id', 'advertiser_id', 'lego_mid'], fields: ['stat_cost'], limit: 100, offset: off, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1, needProjectBasicStats: false}, filter: {materialFilter: {type: 3, materialStatusFirst: [-1], autoMaterialSources: [0, 18]}, promotion: {promotionIds: [p.promotion_id]}, stdProject: {projectIds: [p.project_id]}, isAigc: false, isAutoStar: false, isLive: false}});
      if (mj.code !== 0) { __pj.err.push(adv + '/' + p.project_id + ' mats ' + mj.code); break; }
      const rs = (mj.data && mj.data.rows) || [];
      for (const r of rs) { n++; const c = num(r.metrics && r.metrics.stat_cost); if (c > 0) sp.push(r.material_id + ':' + Math.round(c * 100) / 100); if (upDay(r.material_id) >= RECENT) rc.push(r.material_id); }
      if (rs.length < 100) break; }
    __pj.out.push([adv, p.project_id, p.create_time, String(p.project_name || '').replace(/[\t\n]/g, ' '), p.campaign_budget, p.project_bid, p.project_deep_cpa_bid, p.oc_project_status_first_name, (p.metrics || {}).stat_cost, n, sp.join('|'), rc.join('|')].join('\t'));
  }
};
(async () => { const q = ADVS.slice(); const run = async () => { while (q.length) { const a = q.shift(); try { await one(a); } catch (e) { __pj.err.push(a + ' ' + e); } __pj.done++; } }; await Promise.all([run(), run(), run(), run()]); __pj.st = 'done'; })();
window.__pjWait = async () => { for (let i = 0; i < 40 && __pj.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __pj.st, done: __pj.done, of: __pj.of, rows: __pj.out.length, err: __pj.err.slice(0, 20)}); };
window.__pjGet = (k) => JSON.stringify({date: D, k: k, d: __pj.out.slice(k * 80, k * 80 + 80).join('\n')});
}
'started'"""


def load(p):
    x = json.loads(open(p).read().strip())
    return json.loads(x) if isinstance(x, str) else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--ebp', required=True, help='集中度第 1 步 conc.js 的返回值文件（账户列表从这里取）')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date)
    x = load(a.ebp)
    advs = sorted({r.split(',')[1] for r in (x.get('d') or '').split(';') if r})
    js = (JS.replace('__PAGE__', PAGE).replace('__D__', a.date).replace('__D0__', (d - dt.timedelta(days=9)).isoformat())
          .replace('__RECENT__', (d - dt.timedelta(days=14)).isoformat()).replace('__ADVS__', json.dumps(advs)))
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'proj.js'), 'w').write(js)
    print(json.dumps({'date': a.date, 'accounts': len(advs), 'page': PAGE, 'bytes': len(js)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
