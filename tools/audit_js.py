"""巨量素材审核标签（Reina 11/12）：冷启三类排查里的「内容硬伤」用巨量自己的审核结果做证据（前置拒审-极端相似、禁投、限投、各类违规）。

用法：
1. python3 tools/audit_js.py --date D > /tmp/linkjs/audit.js
2. 在 https://ad.oceanengine.com/material_center/management/video?aadvid=1879653859950867 （只看不点）用 javascript_tool 跑 audit.js 全文，返回 started；
   反复跑 `await __audWait()` 到 st 是 done（约 1 分钟），再跑 `JSON.stringify(__aud.out)`，返回值存成 /tmp/linkjs/audit.json（从会话记录里解析，不手抄）。
3. python3 tools/audit_js.py --date D --save /tmp/linkjs/audit.json → notes/jl-audit-D.json，compute.py 读 D 及以前最近的一份。
只调素材列表查询接口，不点任何按钮。
"""
import argparse, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ADVS = ['1879653859950867', '1879468289371656', '1879447996766343', '1878223927194825']
JS = r"""{ const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
const base = {statistic_start_time: '__D0__ 00:00:00', statistic_end_time: '__D__ 23:59:59', need_summation: false};
window.__aud = {st: 'run', n: 0, out: {}, err: []};
(async () => { for (const adv of __ADVS__) { for (let p = 1; p < 60; p++) { try {
  const r = await fetch('/material_center/api/v1/management/video/material_list?aadvid=' + adv, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json', 'x-csrftoken': csrf}, body: JSON.stringify({...base, page: p, limit: 50, fields: ['stat_cost']})});
  const j = await r.json(); const ms = (j.data && j.data.materials) || [];
  for (const m of ms) { __aud.n++; const t = (m.results || []).map((x) => x.tpl_list).filter(Boolean).join(''); if (t) __aud.out[m.material_id] = t; }
  if (!(j.data && j.data.page_info && j.data.page_info.has_more)) break; } catch (e) { __aud.err.push(adv + ':' + p + ':' + e.message); break; } } }
  __aud.st = 'done'; })();
window.__audWait = async () => { for (let i = 0; i < 40 && __aud.st !== 'done'; i++) await new Promise((z) => setTimeout(z, 1000)); return {st: __aud.st, n: __aud.n, tagged: Object.keys(__aud.out).length, err: __aud.err}; };
'started'; }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--save')
    a = ap.parse_args()
    if a.save:
        x = json.loads(open(a.save).read().strip())
        x = json.loads(x) if isinstance(x, str) else x
        out = {'date': a.date, 'source': '巨量素材中心视频库 material_list 的审核结果 results[].tpl_list，账户 ' + '、'.join(ADVS), 'items': x}
        p = os.path.join(os.path.dirname(HERE), 'notes', f'jl-audit-{a.date}.json')
        json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
        print(p, len(x))
        return
    import datetime as dt
    d0 = (dt.date.fromisoformat(a.date) - dt.timedelta(days=30)).isoformat()
    print(JS.replace('__D0__', d0).replace('__D__', a.date).replace('__ADVS__', json.dumps(ADVS)))


if __name__ == '__main__':
    main()
