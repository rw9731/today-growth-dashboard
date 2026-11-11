"""素材集中度（Reina 11/11）：昨天每条素材在单个项目里最多花了多少、占它总消耗多少、在几个项目里花了钱。

两步，都只调查询接口，不点任何按钮（不点「体验智擎版」、编辑、开关）：
1. python3 tools/conc_js.py --date D --out /tmp/linkjs  → 写 conc.js。
   在 https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746 （巨量升级版工作台，跳到登录页就停，不输账号密码）
   用 javascript_tool 跑 conc.js 全文，返回值原样存成 /tmp/linkjs/conc.json（从会话记录里解析工具结果写文件，不手抄）。
   这一步拿 D 当天「素材 × 账户」消耗（接口一次返回全部行，只调一次），只留 D 花了 ¥100 以上的素材。
2. python3 tools/conc_js.py --date D --out /tmp/linkjs --ebp /tmp/linkjs/conc.json  → 写 conc_proj.js。
   打开 https://ad.oceanengine.com/ad/web/std/manage?aadvid=1879654096082505 （巨量广告智擎版投放管理，只看不点），
   javascript_tool 跑 conc_proj.js 全文（返回 started），再反复跑 `await __concWait()` 到 st 是 done；err 不空（接口偶尔 500）就跑 `await __concRedo()` 重查没查到的账户，
   然后依次跑 `__concGet(0)`、`__concGet(1)`……每次返回值原样存成 /tmp/linkjs/concp_k.json，直到 d 是空字符串。
   这一步对第 1 步里每个花了钱的账户：std/projects/list 拿 D 有消耗的项目，再 std/promotion/materials/list 拿每个项目里各素材的消耗。
3. python3 tools/conc_save.py --date D /tmp/linkjs/conc.json /tmp/linkjs/concp_*.json → notes/conc-D.json，compute.py 默认读它。
口径：按项目（cdp project）算，只算 D 当天有消耗的项目。智擎户走 std 接口；没有智擎项目的户（普通户）走普通版报表 ad_material_data（项目 × 素材）。
两边都查不到的账户整户当一个项目，conc_save 写进 warn。
"""
import argparse, datetime as dt, json, os

EBP_PAGE = 'https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746'
AD_PAGE = 'https://ad.oceanengine.com/ad/web/std/manage?aadvid=1879654096082505'

JS1 = r"""// 在这个页面跑（巨量升级版工作台，要已登录）：__PAGE__
{ const D = "__D__";
const b = {sophonxType: 3, appKeys: ['0', '80', '10168'], dataSetKey: 'EBP_management_mid_analysis', metrics: ['stat_cost'], dimensions: ['material_id', 'advertiser_id'], filters: {ConditionRelationshipType: 1, Conditions: []}, startTime: D, endTime: D, orderType: 2, orderField: 'stat_cost', advertiserIds: [], needBpList: true, componentType: 1, extra: {delivery_mode: '1'}, ebpids: [], pageParams: {Limit: 50, Offset: 0}};
const j = await (await fetch('/api/ebp/common/sophonx/get_material_sophonx_data?ebpid=1878449164572746', {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)})).json();
const t = j.data && j.data.tableList, L = (t && t.list) || [];
const M = {};
for (const r of L) { const c = parseFloat(String(r.stat_cost).replace(/,/g, '')) || 0; if (c <= 0) continue; (M[r.material_id] = M[r.material_id] || []).push([r.advertiser_id, Math.round(c * 100) / 100]); }
const rows = [];
for (const [m, a] of Object.entries(M)) { const s = a.reduce((p, q) => p + q[1], 0); if (s >= 100) for (const [adv, c] of a) rows.push(m + ',' + adv + ',' + c); }
JSON.stringify({date: D, code: j.code, total: t && t.pagination && t.pagination.total, got: L.length, d: rows.join(';')});
}"""

JS2 = r"""// 在这个页面跑（巨量广告智擎版投放管理，只看不点）：__PAGE__
{ const D = "__D__", A2M = __A2M__;
const T0 = Date.parse(D + 'T00:00:00+08:00'), T1 = T0 + 86400000 - 1;
const post = async (u, b) => { for (let i = 0; ; i++) { const r = await fetch(u, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)}); const t = await r.text();
  try { return JSON.parse(t); } catch (e) { if (i >= 3) throw new Error('HTTP ' + r.status + ' ' + t.slice(0, 40)); await new Promise((z) => setTimeout(z, 1500 * (i + 1))); } } };
const num = (s) => parseFloat(String(s == null ? 0 : s).replace(/,/g, '')) || 0;
window.__conc = {st: 'run', done: 0, of: Object.keys(A2M).length, out: [], miss: [], err: []};
const one = async (adv) => {
  const want = new Set(A2M[adv]);
  const reg = async () => { // 非智擎户：普通版自定义报表 ad_material_data 按 项目 × 素材
    const b = {DataSetKey: 'ad_material_data', Dimensions: ['cdp_project_id', 'material_id'], StartTime: D + ' 00:00:00', EndTime: D + ' 23:59:59', Filters: {ConditionRelationshipType: 1, Conditions: [{Field: 'advertiser_id', Operator: 7, Values: [adv]}]}, IsDownload: false, Metrics: ['stat_cost'], OrderBy: [{Field: 'stat_cost', Type: 2}], PageParams: {Limit: 1000, Offset: 0}};
    const j = await post('/report/api/tool/agw/statistics_sophonx/statQuery?aadvid=' + adv, b); let n = 0;
    for (const r of (j.data && j.data.StatsData && j.data.StatsData.Rows) || []) { const m = r.Dimensions.material_id.ValueStr, p = r.Dimensions.cdp_project_id.ValueStr, c = num(r.Metrics.stat_cost.Value); if (c > 0 && want.has(m)) { __conc.out.push([m, adv, p, c].join(',')); n++; } }
    if (!n) __conc.miss.push(adv); };
  const pj = await post('/ad/api/agw/promotion/std/projects/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['cdp_project_id', 'cdp_project_name', 'promotion_id', 'cdp_promotion_id', 'advertiser_id'], fields: ['stat_cost'], limit: 100, offset: 0, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1}, filter: {}});
  if (pj.code !== 0) { __conc.err.push(adv + ' projects ' + pj.code + ' ' + (pj.msg || '')); __conc.miss.push(adv); return; }
  const ps = ((pj.data && pj.data.rows) || []).filter((x) => num(x.metrics && x.metrics.stat_cost) > 0);
  if (!ps.length) return reg();
  let got = 0;
  for (const p of ps) {
    for (let off = 0; off < 1000; off += 100) {
      const mj = await post('/ad/api/std/promotion/materials/list?aadvid=' + adv, {parameter: {startTime: T0, endTime: T1, cascadeMetrics: ['material_id', 'advertiser_id', 'lego_mid'], fields: ['stat_cost'], limit: 100, offset: off, orderField: 'stat_cost', orderType: 1, oneCampaignMode: 1, needProjectBasicStats: false}, filter: {materialFilter: {type: 3, materialStatusFirst: [-1], autoMaterialSources: [0, 18]}, promotion: {promotionIds: [p.promotion_id]}, stdProject: {projectIds: [p.project_id]}, isAigc: false, isAutoStar: false, isLive: false}});
      if (mj.code !== 0) { __conc.err.push(adv + '/' + p.project_id + ' materials ' + mj.code + ' ' + (mj.msg || '')); break; }
      const rs = (mj.data && mj.data.rows) || []; let zero = false;
      for (const r of rs) { const c = num(r.metrics && r.metrics.stat_cost); if (c <= 0) { zero = true; break; } if (want.has(r.material_id)) { __conc.out.push([r.material_id, adv, p.project_id, c].join(',')); got++; } }
      if (zero || rs.length < 100) break;
    }
  }
  if (!got) return reg();
};
(async () => { try {
  const q = Object.keys(A2M); const run = async () => { while (q.length) { const a = q.shift(); try { await one(a); } catch (e) { __conc.err.push(a + ' ' + e); __conc.miss.push(a); } __conc.done++; } };
  await Promise.all([run(), run(), run(), run()]); __conc.st = 'done';
} catch (e) { __conc.st = 'error'; __conc.err.push(String(e)); } })();
window.__concRedo = async () => { const m = __conc.miss.splice(0); __conc.out = __conc.out.filter((r) => !m.includes(r.split(',')[1])); __conc.err = []; for (const a of m) { try { await one(a); } catch (e) { __conc.err.push(a + ' ' + e); __conc.miss.push(a); } } return JSON.stringify({redo: m.length, miss: __conc.miss.length, rows: __conc.out.length, err: __conc.err.slice(0, 10)}); };
window.__concWait = async () => { for (let i = 0; i < 40 && __conc.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __conc.st, done: __conc.done, of: __conc.of, rows: __conc.out.length, miss: __conc.miss.length, err: __conc.err.slice(0, 20)}); };
window.__concGet = (k) => JSON.stringify({date: D, k: k, miss: k === 0 ? __conc.miss.join(',') : '', d: __conc.out.slice(k * 400, k * 400 + 400).join(';')});
}
'started'"""


def load(p):
    x = json.loads(open(p).read().strip())
    return json.loads(x) if isinstance(x, str) else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ebp', help='第 1 步 conc.js 的返回值文件；给了就写第 2 步的 conc_proj.js')
    a = ap.parse_args()
    dt.date.fromisoformat(a.date)
    os.makedirs(a.out, exist_ok=True)
    if not a.ebp:
        open(os.path.join(a.out, 'conc.js'), 'w').write(JS1.replace('__D__', a.date).replace('__PAGE__', EBP_PAGE))
        print(json.dumps({'date': a.date, 'step': 1, 'page': EBP_PAGE}, ensure_ascii=False))
        return
    x = load(a.ebp)
    if x.get('date') != a.date:
        raise SystemExit(f"日期对不上：文件是 {x.get('date')}，参数是 {a.date}")
    a2m = {}
    for row in (x.get('d') or '').split(';'):
        if row:
            m, adv, _ = row.split(',')
            a2m.setdefault(adv, []).append(m)
    js = JS2.replace('__D__', a.date).replace('__PAGE__', AD_PAGE).replace('__A2M__', json.dumps(a2m, separators=(',', ':')))
    open(os.path.join(a.out, 'conc_proj.js'), 'w').write(js)
    print(json.dumps({'date': a.date, 'step': 2, 'accounts': len(a2m), 'page': AD_PAGE, 'bytes': len(js)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
