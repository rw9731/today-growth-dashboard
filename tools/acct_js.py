"""Make the browser snippets that pull 素材 × 账户 data for the daily report (Reina 11/9：被建和带量放进日报第五节).

Usage:
  python3 tools/acct_js.py --date D --out /tmp/linkjs

Writes acct.js and acct_get.js. Run them with the built-in browser's javascript_tool on
https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746 (巨量升级版工作台，要已登录；跳到登录页就停):
  1. acct.js 全文跑一次（返回 started）。
  2. 再跑 `await __acctWait()`，st 是 run 就再跑，done 为止。
  3. 依次跑 acct_get.js 里的 `__acctGet(0)`、`__acctGet(1)`……直到返回的 d 是空字符串，把每次返回的 d 用 ; 连起来，
     用 python3 tools/acct_save.py --date D 存成 notes/acct-D.json（见 acct_save.py）。

数据：巨量升级版工作台视频分析的数据集 EBP_management_mid_analysis，按 天 × 素材ID × 账户 拉 stat_cost、show_cnt（只读）。
最近 14 天，在页面里按素材汇总：首次有展示日、有展示的账户数、有消耗的账户数、在该账户首次展示后 3 天内花到 ¥100 / ¥300 的账户数、
单账户 3 天最高消耗、D 当天有展示 / 有消耗的账户数。只留最近 10 天第一次有展示的素材（日报第五节只看最近 10 个上传日）。只调查询接口，不点任何按钮。
"""
import argparse, datetime as dt, json, os

PAGE = 'https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746'

JS = r"""{ const D = %s, DAYS = %s;
const q = async (day) => { const b = {sophonxType: 3, appKeys: ['0', '80', '10168'], dataSetKey: 'EBP_management_mid_analysis', metrics: ['stat_cost', 'show_cnt'], dimensions: ['material_id', 'advertiser_id'], filters: {ConditionRelationshipType: 1, Conditions: []}, startTime: day, endTime: day, orderType: 2, orderField: 'stat_cost', advertiserIds: [], needBpList: true, componentType: 1, extra: {delivery_mode: '1'}, ebpids: [], pageParams: {Limit: 50, Offset: 0}};
  const r = await fetch('/api/ebp/common/sophonx/get_material_sophonx_data?ebpid=1878449164572746', {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)}); return r.json(); };
window.__acct = {st: 'run', done: 0, rows: 0, err: [], out: [], total: {}};
const add = (d, n) => new Date(new Date(d + 'T00:00:00Z').getTime() + n * 86400000).toISOString().slice(0, 10);
(async () => { try {
  const M = {};
  for (const day of DAYS) {
    const j = await q(day); const t = j.data && j.data.tableList; const l = (t && t.list) || [];
    if (j.code !== 0) __acct.err.push(day + ' code ' + j.code + ' ' + (j.msg || ''));
    if (t && t.pagination && t.pagination.total > l.length) __acct.err.push(day + ' 只拿到 ' + l.length + '/' + t.pagination.total);
    let tot = 0;
    for (const r of l) { const c = parseFloat(String(r.stat_cost).replace(/,/g, '')) || 0, s = parseInt(String(r.show_cnt).replace(/,/g, '')) || 0; tot += c;
      const x = M[r.material_id] || (M[r.material_id] = {}); const y = x[r.advertiser_id] || (x[r.advertiser_id] = {fs: null, days: {}});
      if ((s > 0 || c > 0) && (!y.fs || day < y.fs)) y.fs = day; y.days[day] = (y.days[day] || 0) + c; if (s > 0 && day === D) y.showD = 1; }
    __acct.total[day] = Math.round(tot); __acct.rows += l.length; __acct.done++;
  }
  for (const [m, accs] of Object.entries(M)) { let fs = null, nShow = 0, nSpend = 0, n100 = 0, n300 = 0, max3 = 0, showD = 0, spendD = 0;
    for (const y of Object.values(accs)) { if (!y.fs) continue; nShow++; const t = Object.values(y.days).reduce((p, q) => p + q, 0); if (t > 0) nSpend++; if (!fs || y.fs < fs) fs = y.fs;
      let c3 = 0; for (let k = 0; k < 3; k++) c3 += y.days[add(y.fs, k)] || 0; if (c3 >= 100) n100++; if (c3 >= 300) n300++; if (c3 > max3) max3 = c3; if (y.showD) showD++; if ((y.days[D] || 0) > 0) spendD++; }
    if (fs && fs >= DAYS[DAYS.length - 10]) __acct.out.push([m, fs.slice(5), nShow, nSpend, n100, n300, Math.round(max3), showD, spendD].join(',')); }
  __acct.st = 'done';
} catch (e) { __acct.st = 'error'; __acct.err.push(String(e)); } })();
window.__acctWait = async () => { for (let i = 0; i < 40 && __acct.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __acct.st, done: __acct.done, of: DAYS.length, rows: __acct.rows, mats: __acct.out.length, err: __acct.err, total: __acct.total}); };
window.__acctGet = (k) => JSON.stringify({acck: k, d: __acct.out.slice(k * 150, k * 150 + 150).join(';')});
}
'started'"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date)
    days = [(d - dt.timedelta(k)).isoformat() for k in range(a.days - 1, -1, -1)]
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'acct.js'), 'w').write(f'// 在这个页面跑（巨量升级版工作台，要已登录）：{PAGE}\n' + JS % (json.dumps(a.date), json.dumps(days)))
    open(os.path.join(a.out, 'acct_get.js'), 'w').write('// 依次跑 await __acctGet(0)、__acctGet(1)……直到 d 是空字符串\nawait __acctGet(0)\n')
    print(json.dumps({'date': a.date, 'days': len(days), 'page': PAGE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
