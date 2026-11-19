"""新老项目基建（Reina 11/19）：从巨量后台「操作日志」还原每条素材在冷启窗口里放进了几个新、老项目（分 iOS、安卓）。

为什么用操作日志：项目快照（proj_js.py）只列近期有活动的项目，老项目只记到一半；MCP 只有报表，没有放置记录。
操作日志里项目对象的「新建」「修改 → 新增 视频: 添加: 【素材ID:…】」带时间，是完整的放置记录（户的日志从开户开始）。

用法（每天，D = 数据日）：
1. python3 tools/oplog_js.py --date D --out /tmp/oplog
   → 写 /tmp/oplog/oplog.js（拉 D-4 到 D 的日志）和 /tmp/oplog/ids.json（要算的素材：上传日在 D-4 到 D 的，取自当天 compute 的 cs_mats；
     没有就先跑一遍 compute），并打印 ids_js：一段 JS，把素材 ID 列表放进页面。
2. 在 Reina 的 Chrome 打开 https://ad.oceanengine.com/ad/web/tools/tools_console/operation-log?aadvid=1879654096082505（只看不点），
   javascript_tool 跑 oplog.js 全文（返回 started），反复跑 `await __opWait()` 到 st 是 done（416 个户、5 天约 5–10 分钟）。
   再跑 ids_js，然后依次跑 `__opGet(0)`、`__opGet(1)`……（每段 70 条素材，返回值不到 1,000 字，javascript_tool 不会截断），
   每段原样存成 /tmp/oplog/op_k.txt，直到返回空字符串。
3. python3 tools/oplog_save.py --date D /tmp/oplog → 合并进 notes/jjlog.json，compute.py 读它算「新老项目基建不够」。
只调查询接口（opt_log/dataSearch），不点任何按钮。户列表：notes/jj-accounts.json（BigQuery fact 里有数的智擎户），脚本运行时从看板站点读。
"""
import argparse, datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = 'https://ad.oceanengine.com/ad/web/tools/tools_console/operation-log?aadvid=1879654096082505'
ACC = 'https://rw9731.github.io/today-growth-dashboard/notes/jj-accounts.json'  # 户列表从看板站点取，省得每天把 416 个户贴进脚本

JS = r"""// 在这个页面跑（巨量操作日志，只看不点）：__PAGE__
{ const S = "__S__", E = "__E__", ACC = "__ACC__";
const dOf = (id) => new Date(Number(BigInt(id) >> 32n) * 1000 + 8 * 3600000).toISOString().slice(0, 10);
const addD = (d, k) => new Date(Date.parse(d + 'T00:00:00Z') + k * 86400000).toISOString().slice(0, 10);
window.__op = {st: 'run', done: 0, of: 0, err: [], pairs: new Map(), pname: new Map(), nlog: 0};
const get = async (adv, p) => { for (let i = 0; ; i++) { try { const r = await fetch(`/nbs/api/statistics/opt_log/dataSearch?start_time=${S}&end_time=${E}&page=${p}&limit=100&version=1&qt=[]&q_ids=[]&aadvid=${adv}`, {credentials: 'include'}); const j = await r.json(); if (j.code === 0) return j; if (i >= 3) throw new Error('code ' + j.code); } catch (e) { if (i >= 3) throw e; } await new Promise((z) => setTimeout(z, 1200 * (i + 1))); } };
const one = async (adv) => { for (let p = 1; p <= 400; p++) { const j = await get(adv, p); const L = (j.data && j.data.logs) || [];
  for (const x of L) { __op.nlog++; if (x.object_type !== '项目') continue; __op.pname.set(x.object_id, x.object_name);
    const segs = Array.isArray(x.content_log) ? x.content_log : [String(x.content_log)];
    for (const s of segs) for (const line of String(s).split('\n')) {
      if (!/素材ID/.test(line)) continue; if (/删除/.test(line) && !/添加/.test(line)) continue; if (!(/添加/.test(line) || x.content_title === '新建')) continue;
      for (const m of line.matchAll(/素材ID[:：]\s*(\d{15,})/g)) { const k = m[1] + '|' + x.object_id, o = __op.pairs.get(k); if (!o || x.create_time < o) __op.pairs.set(k, x.create_time); } } }
  if (L.length < 100 || !(j.data.pagination || {}).has_more) break; } };
(async () => { let ADVS; try { ADVS = (await (await fetch(ACC + '?t=' + Date.now())).json()).ids; } catch (e) { __op.err.push('户列表 ' + e); __op.st = 'error'; return; } __op.of = ADVS.length; const q = ADVS.slice(); const run = async () => { while (q.length) { const a = q.shift(); try { await one(a); } catch (e) { __op.err.push(a + ' ' + e); } __op.done++; } }; await Promise.all([run(), run(), run(), run(), run(), run()]);
  // 每条素材：窗口（上传日到 +2 天）里放进的项目，按项目 ID 高 32 位的创建日分新老（建在上传日前一天或之后算新），按项目名开头 ios 分端
  const C = new Map(), pc = new Map();
  for (const [k, t] of __op.pairs) { const i = k.indexOf('|'), mid = k.slice(0, i), pid = k.slice(i + 1), U = dOf(mid), d = t.slice(0, 10);
    if (U < S || d < U || d > addD(U, 2)) continue; let c = pc.get(pid); if (!c) { c = dOf(pid); pc.set(pid, c); }
    const ios = /^ios/i.test((__op.pname.get(pid) || '').trim()), nw = c >= addD(U, -1); let a = C.get(mid); if (!a) { a = [0, 0, 0, 0]; C.set(mid, a); } a[(ios ? 0 : 2) + (nw ? 0 : 1)]++; }
  __op.C = C; __op.st = 'done'; })();
window.__opWait = async () => { for (let i = 0; i < 38 && __op.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __op.st, done: __op.done, of: __op.of, nlog: __op.nlog, pairs: __op.pairs.size, mats: __op.C ? __op.C.size : 0, err: __op.err.slice(0, 5)}); };
// 每段 70 条素材，每条「iOS 新 iOS 老 安卓新 安卓老」四个数空格分开、条与条用分号分开（不到 1,000 字；36 进制会被当成 base64 拦掉）
window.__opGet = (k) => (window.__opIds || []).slice(k * 70, k * 70 + 70).map((m) => (__op.C.get(m) || [0, 0, 0, 0]).join(' ')).join(';');
}
'started'"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--start', help='日志起始日，默认 D-4')
    ap.add_argument('--cs', help='compute 输出 json（含 cs_mats），默认 /tmp/rc/r-D 的日号.json')
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date)
    s = a.start or (d - dt.timedelta(days=4)).isoformat()
    advs = json.load(open(os.path.join(os.path.dirname(HERE), 'notes', 'jj-accounts.json')))['ids']
    cs = a.cs or f'/tmp/rc/r-{a.date[-2:]}.json'
    ids = sorted({m['id'] for m in json.load(open(cs))['cs_mats'] if m['up'][:10] >= s}) if os.path.exists(cs) else []
    if not ids:
        sys.exit(f'没有素材列表：先跑 compute 生成 {cs}')
    js = JS.replace('__PAGE__', PAGE).replace('__S__', s).replace('__E__', a.date).replace('__ACC__', ACC)
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'oplog.js'), 'w').write(js)
    json.dump({'date': a.date, 'start': s, 'ids': ids}, open(os.path.join(a.out, 'ids.json'), 'w'))
    print(json.dumps({'date': a.date, 'start': s, 'accounts': len(advs), 'mats': len(ids), 'chunks': (len(ids) + 69) // 70, 'page': PAGE}, ensure_ascii=False))
    print('ids_js: window.__opIds = ' + json.dumps(ids) + '; __opIds.length')


if __name__ == '__main__':
    main()
