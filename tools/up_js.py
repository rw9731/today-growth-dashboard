"""Make the browser snippet that lists every material uploaded to 巨量 on day D (Reina 11/9：上新按上传算).

Usage:
  python3 tools/up_js.py --date D --out /tmp/linkjs

Writes up.js. Run it with the built-in browser's javascript_tool on the 巨量素材页
https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 (要已登录巨量；网址里有 login 就停).
It returns a short JSON string; save it as notes/uploads-D.json, then run compute.py with --uploads notes/uploads-D.json.

上传时间 = 素材ID 里带的时间（ID 右移 32 位是 unix 秒），各账户都一样；账户里的 created_at 是推到这个账户的时间，只用来决定翻到哪页停。
只读：只调素材列表接口，不点任何按钮。
"""
import argparse, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = 'https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825'

JS = r"""{ const D = %s, HUBS = %s;
const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
const mc = async (adv, body) => { const r = await fetch('/material_center/api/v1/management/video/material_list?aadvid=' + adv, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json', 'x-csrftoken': csrf}, body: JSON.stringify(body)}); return r.json(); };
const upDay = (id) => new Date((Number(BigInt(id) >> 32n) + 8 * 3600) * 1000).toISOString().slice(0, 10);
const items = {}; let req = 0, pages = {};
for (const adv of HUBS) {
  for (let p = 1; p < 40; p++) {
    const j = await mc(adv, {statistic_start_time: D + ' 00:00:00', statistic_end_time: D + ' 23:59:59', need_summation: false, page: p, limit: 50}); req++;
    const ms = (j.data && j.data.materials) || [];
    for (const m of ms) if (upDay(m.material_id) === D && !items[m.material_id]) items[m.material_id] = [m.title || '', m.is_cost ? 1 : 0];
    pages[adv] = p;
    // 推到账户的时间不会早于上传时间：整页都早于 D 就不用再翻
    if (!ms.length || ms.every((m) => (m.created_at || '').slice(0, 10) < D) || !(j.data && j.data.page_info && j.data.page_info.has_more)) break;
  }
}
JSON.stringify({date: D, hubs: HUBS, req, pages, n: Object.keys(items).length, items});
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    hubs = json.load(open(os.path.join(HERE, 'jl_hubs.json')))
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'up.js'), 'w').write(f'// 在这个页面跑（要已登录巨量）：{PAGE}\n' + JS % (json.dumps(a.date), json.dumps(hubs)))
    print(json.dumps({'date': a.date, 'hubs': len(hubs), 'page': PAGE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
