"""Make the browser snippet that fetches ad videos straight from 巨量 (Ocean Engine).

Usage:
  python3 tools/jl_js.py /tmp/results.json --out /tmp/linkjs

Writes jl.js. Run it with the built-in browser's javascript_tool on any
https://ad.oceanengine.com page (Reina has to be logged in to 巨量 there). It starts a
background job and returns at once; then run `await __jlWait()` until it says done, and
`__jlGet(0)`, `__jlGet(1)`, ... (8 videos per call) until it returns []. Save the
concatenated objects as /tmp/linkjs/jl.json and run tools/links_merge.py.

How it finds a video: the same 素材 ID is pushed to many ad accounts, and a few accounts
(tools/jl_hubs.json, updated by links_merge.py) hold almost all of them. The job lists those
accounts' video libraries first, then searches the remaining IDs account by account (at most
100 searches). 巨量 video links are signed and stop working after about 2 days, so 唯西日报's
permanent link stays first when there is one; links_merge.py refreshes the 巨量 ones daily.
"""
import argparse, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = 'https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825'

JS = r"""{ const NEED = %s, HUBS = %s, START = %s;
window.__jl = {st: 'run', res: {}, hits: {}, n: 0};
const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
const mc = async (adv, body) => { const r = await fetch('/material_center/api/v1/management/video/material_list?aadvid=' + adv, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json', 'x-csrftoken': csrf}, body: JSON.stringify(body)}); __jl.n++; return r.json(); };
const base = {statistic_start_time: START + ' 00:00:00', statistic_end_time: new Date().toISOString().slice(0, 10) + ' 23:59:59', need_summation: false};
const need = new Set(NEED);
const take = (adv, m) => { if (!need.has(m.material_id) || __jl.res[m.material_id] || !m.video_url) return; const exp = parseInt(new URL(m.video_url).pathname.split('/')[2], 16) || 0; __jl.res[m.material_id] = {u: m.video_url, exp, t: m.title, d: m.duration}; __jl.hits[adv] = (__jl.hits[adv] || 0) + 1; };
(async () => { try {
  for (const adv of HUBS) { for (let p = 1; p < 30; p++) { const j = await mc(adv, {...base, page: p, limit: 50}); const ms = (j.data && j.data.materials) || []; ms.forEach((m) => take(adv, m)); if (!(j.data && j.data.page_info && j.data.page_info.has_more)) break; } }
  let miss = NEED.filter((i) => !__jl.res[i]);
  if (miss.length) {
    let accs = []; for (let p = 1; p < 30; p++) { const r = await fetch('/ad/api/navigator/advertiser/list?page=' + p + '&limit=50&keyword=&aadvid=' + HUBS[0], {credentials: 'include'}); const j = await r.json(); const l = (j.data && j.data.user_account_infos) || []; accs.push(...l); if (l.length < 50) break; }
    accs = accs.filter((a) => !HUBS.includes(a.id)).sort((a, b) => Number(b.create_time) - Number(a.create_time));
    let tries = 0;
    for (const a of accs) { if (!miss.length || tries >= 100) break; for (const mid of miss.slice(0, 5)) { tries++; const j = await mc(a.id, {...base, page: 1, limit: 10, key_word: mid}); ((j.data && j.data.materials) || []).forEach((m) => take(a.id, m)); } miss = miss.filter((i) => !__jl.res[i]); }
  }
  __jl.miss = NEED.filter((i) => !__jl.res[i]); __jl.st = 'done';
} catch (e) { __jl.st = 'error'; __jl.err = String(e); } })();
window.__jlWait = async () => { for (let i = 0; i < 40 && __jl.st === 'run'; i++) await new Promise((r) => setTimeout(r, 1000)); return JSON.stringify({st: __jl.st, err: __jl.err, found: Object.keys(__jl.res).length, need: NEED.length, miss: (__jl.miss || []).length, requests: __jl.n, hits: __jl.hits}); };
window.__jlGet = (k) => JSON.stringify(Object.entries(__jl.res).slice(k * 8, k * 8 + 8).map(([id, v]) => ({id, ...v})));
}
'jl started'"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    res = json.load(open(a.results))
    links = json.load(open(os.path.join(HERE, 'links.json')))
    hubs = json.load(open(os.path.join(HERE, 'jl_hubs.json')))
    now = time.time()
    ids = {m['id'] for m in res['mat']} | {i for k in res.get('kl', []) for i in k.get('src_ids', [])}
    # 往期页面上还在用巨量链接的也一起刷新（巨量链接 2 天过期）
    ids |= {i for i, lk in links.items() if lk.get('jl') and not lk.get('video')}
    need = sorted(ids)[:400]
    start = time.strftime('%Y-%m-%d', time.gmtime(now - 60 * 86400))
    os.makedirs(a.out, exist_ok=True)
    js = JS % (json.dumps(need), json.dumps(hubs), json.dumps(start))
    open(os.path.join(a.out, 'jl.js'), 'w').write(f'// 在这个页面跑（要已登录巨量）：{PAGE}\n' + js)
    print(json.dumps({'need': len(need), 'hubs': len(hubs), 'page': PAGE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
