"""Make the browser snippet that lists every material uploaded to 巨量 on day D (Reina 11/9：上新按上传算).

11/18 改（Reina 要求修）：原来只查 tools/jl_hubs.json 里 3 个素材库账户，11/16 起大部分素材推到别的账户，
11/17 只读到 6 条（实际 70 条）。改成巨量升级版工作台素材库接口 /api/ebp/video/list，查「归属组织」和
「共享给组织」两个列表，一次拿全组织的素材。

Usage:
  python3 tools/up_js.py --date D --out /tmp/linkjs

Writes up.js. 在巨量升级版工作台页面跑（要已登录；跳到登录页就停）：
https://business.oceanengine.com/ebp/material/management/video?ebpid=1878449164572746
（第三节之三的视频分析页 https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746 也行，同域名即可。）

1. javascript_tool 跑 up.js 全文（返回 up started）。
2. 反复跑 await __upWait()，直到 st 是 done（error 就看 err）。整个过程一般 1 到 3 分钟。
3. 依次跑 __upGet(0)、__upGet(1)……每次返回值原样存成 /tmp/linkjs/up_k.json（k 换成数字），直到 d 是空字符串。
4. python3 tools/up_save.py --date D /tmp/linkjs/up_*.json，写 notes/uploads-D.json。

上传日 = 素材ID 右移 32 位是 unix 秒，加 8 小时。create_time 是素材进组织的时间（不早于上传），列表按它倒序，
一页最后一条的 create_time 早于 D 就不用再翻。名字带「闪糖」的是同组织另一个产品的素材，不算。
接口会悄悄限流：code 0 但 list 为空、total 还很大，等 10 秒重试同一页（最多 6 次）。
只读：只调列表接口，不点任何按钮。
"""
import argparse, json, os

PAGE = 'https://business.oceanengine.com/ebp/material/management/video?ebpid=1878449164572746'

JS = r"""{ const D = %s, EBP = '1878449164572746', SKIP = /闪糖/;
const csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
const upDay = (id) => new Date((Number(BigInt(id) >> 32n) + 8 * 3600) * 1000).toISOString().slice(0, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
window.__up = {st: 'run', err: '', req: 0, retry: 0, pages: {}, total: {}, items: {}, skipped: 0, out: ''};
const list = async (pool, page) => {
  const b = {startTime: D + ' 00:00:00', endTime: D + ' 23:59:59', limit: 50, page, orderBy: 'create_time', orderType: 1, fields: ['stat_cost', 'show_cnt'], imageModes: [], materialProperties: [], isDirectAccountGroup: false};
  b[pool === 'own' ? 'filterEbpId' : 'filterAuthEbpId'] = EBP;
  const r = await fetch('/api/ebp/video/list?ebpid=' + EBP, {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json', 'accept': 'application/json, text/plain, */*', 'x-csrftoken': csrf}, body: JSON.stringify(b)});
  __up.req++; return r.json();
};
(async () => { try {
  for (const pool of ['own', 'auth']) {
    for (let p = 1; p < 200; p++) {
      let j, ls = [], tot = 0;
      for (let k = 0; k < 7; k++) {
        j = await list(pool, p);
        if (j.code !== 0) throw new Error(pool + ' p' + p + ' code ' + j.code + ' ' + (j.msg || ''));
        ls = (j.data && j.data.list) || []; tot = (j.data && j.data.pagination && j.data.pagination.total) || 0;
        if (ls.length || (p - 1) * 50 >= tot) break;
        __up.retry++; await sleep(10000);
      }
      __up.pages[pool] = p; __up.total[pool] = tot;
      if (!ls.length && (p - 1) * 50 < tot) throw new Error(pool + ' p' + p + ' 限流重试 6 次还是空');
      for (const m of ls) {
        const id = String(m.material_id), nm = m.file_name || '';
        if (upDay(id) !== D || __up.items[id]) continue;
        if (SKIP.test(nm)) { __up.skipped++; continue; }
        __up.items[id] = nm;
      }
      const last = ls.length ? String(ls[ls.length - 1].create_time || '').slice(0, 10) : '';
      if (!ls.length || p * 50 >= tot || (last && last < D)) break;
      await sleep(1500);
    }
  }
  __up.out = JSON.stringify({date: D, source: '巨量升级版工作台素材库（api/ebp/video/list，归属和共享两个列表）', n: Object.keys(__up.items).length, skipped: __up.skipped, items: __up.items});
  __up.st = 'done';
} catch (e) { __up.st = 'error'; __up.err = String(e); } })();
window.__upWait = async () => { for (let i = 0; i < 35 && __up.st === 'run'; i++) await sleep(1000); return JSON.stringify({st: __up.st, err: __up.err, n: Object.keys(__up.items).length, skipped: __up.skipped, req: __up.req, retry: __up.retry, pages: __up.pages, total: __up.total}); };
window.__upGet = (k) => JSON.stringify({k, d: __up.out.slice(k * 800, (k + 1) * 800)});
'up started';
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'up.js'), 'w').write(f'// 在这个页面跑（要已登录巨量升级版工作台）：{PAGE}\n' + JS % json.dumps(a.date))
    print(json.dumps({'date': a.date, 'page': PAGE, 'next': 'await __upWait() 到 done，再 __upGet(k) 存 up_k.json，最后 tools/up_save.py'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
