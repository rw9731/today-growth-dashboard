"""排产衔接检查的数据部分（Reina 11/11）：找出最近三天在起量、表现好的 use case 和素材，
以及最新一批过了冷启的新素材，给定时任务「排产衔接检查」去对 A、B 组后面几天的排期。

用法：python3 tools/align_check.py --sheet <投放数据_分日 get_values 文件> --date D [--page D/index.html] --out /tmp/align/data.json

口径：
- 消耗看 D-2..D 三天（近 3 天），对比 D-6..D-3 四天（前 4 天）。
- 次留按 cohort：近 3 天看 D-3..D-1 激活的次留（D-1 的次留早上还没回传完，偏低约 1 个点），
  load_rows 已把次留挪到第二天那一行，所以 cohort X 的次留在 X+1 行。
- 全盘（market）同口径。
- 起量 + 表现好的 use case：近 3 天消耗占比 ≥ 2%，比前 4 天占比高 ≥ 1 个点且 ≥ 1.3 倍，
  近 3 天 cohort 激活 ≥ 50，次留 ≥ 全盘，次留成本 ≤ 全盘 + 3 元。
  只是起量、留存没到全盘的放进 rising_watch。
- 可当头部模板的素材（近 3 天跑出来的）：同一条素材（按素材名去掉推送/修改后缀合并）近 3 天消耗 ≥ ¥2,000，
  cohort 激活 ≥ 80，次留 ≥ 全盘，次留成本 ≤ 全盘 + 3 元；或首花在近 7 天、累计消耗 ≥ ¥3,000、激活 ≥ 100、同样过全盘。
- 冷启：页面 cs_mats 里窗口已走完的最近 3 个上传日，st == pass 的素材。
"""
import argparse, json, os, re, sys
from collections import defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute  # noqa: E402


def d2s(d):
    return d.isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--page')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    D = date.fromisoformat(a.date)
    rows = compute.load_rows(a.sheet)
    days = {r['date'] for r in rows}
    if d2s(D) not in days:
        print('NO_DATA')
        return
    s3 = {d2s(D - timedelta(k)) for k in range(0, 3)}
    p4 = {d2s(D - timedelta(k)) for k in range(3, 7)}
    c3 = {d2s(D - timedelta(k)) for k in range(1, 4)}          # cohort 日
    c3r = {d2s(date.fromisoformat(x) + timedelta(1)) for x in c3}  # 这些 cohort 的次留所在行

    def agg(sel):
        o = {'cost3': 0.0, 'costp': 0.0, 'act': 0.0, 'ret': 0.0, 'costc': 0.0}
        for r in sel:
            if r['date'] in s3:
                o['cost3'] += r['cost']
            if r['date'] in p4:
                o['costp'] += r['cost']
            if r['date'] in c3:
                o['act'] += r['act']
                o['costc'] += r['cost']
            if r['date'] in c3r:
                o['ret'] += r['ret']
        o['rate'] = o['ret'] / o['act'] if o['act'] else None
        o['cpr'] = o['costc'] / o['ret'] if o['ret'] else None
        return o

    mk = agg(rows)
    by_uc = defaultdict(list)
    for r in rows:
        by_uc[r['uc'] or '未标'].append(r)
    ucs = []
    for u, rs in by_uc.items():
        o = agg(rs)
        o['uc'] = u
        o['l1'] = next((r['l1'] for r in rs if r['l1']), '')
        o['share3'] = o['cost3'] / mk['cost3'] if mk['cost3'] else 0
        o['sharep'] = o['costp'] / mk['costp'] if mk['costp'] else 0
        o['daily'] = [[d2s(D - timedelta(k)), round(sum(r['cost'] for r in rs if r['date'] == d2s(D - timedelta(k))))] for k in range(6, -1, -1)]
        up = o['share3'] >= 0.02 and o['share3'] - o['sharep'] >= 0.01 and (o['sharep'] == 0 or o['share3'] / o['sharep'] >= 1.3)
        good = o['act'] >= 50 and o['rate'] is not None and o['rate'] >= mk['rate'] and o['cpr'] is not None and o['cpr'] <= mk['cpr'] + 3
        o['flag'] = 'rising_good' if up and good else ('rising_watch' if up else ('steady_good' if good and o['share3'] >= 0.03 else ''))
        ucs.append(o)
    ucs.sort(key=lambda x: -x['cost3'])

    # 素材：按素材名合并推送版、修改版
    first = {}
    for r in rows:
        if r['cost'] > 0:
            first[r['id']] = min(first.get(r['id'], r['date']), r['date'])
    by_m = defaultdict(list)
    for r in rows:
        by_m[compute.base_name(r['name'])].append(r)
    tpl = []
    for n, rs in by_m.items():
        o = agg(rs)
        f = min((first[r['id']] for r in rs if r['id'] in first), default=None)
        tot = sum(r['cost'] for r in rs)
        acts = sum(r['act'] for r in rs)
        good = o['rate'] is not None and o['rate'] >= mk['rate'] and o['cpr'] is not None and o['cpr'] <= mk['cpr'] + 3
        a_hit = o['cost3'] >= 2000 and o['act'] >= 80 and good
        b_hit = False
        if f and f >= d2s(D - timedelta(6)) and tot >= 3000 and acts >= 100:
            fr = [r for r in rs if r['date'] >= f]
            act_all = sum(r['act'] for r in fr if r['date'] <= d2s(D - timedelta(1)))
            ret_all = sum(r['ret'] for r in fr if r['date'] <= d2s(D))
            cost_all = sum(r['cost'] for r in fr if r['date'] <= d2s(D - timedelta(1)))
            if act_all and ret_all and ret_all / act_all >= mk['rate'] and cost_all / ret_all <= mk['cpr'] + 3:
                b_hit = True
        if a_hit or b_hit:
            tpl.append({'name': n, 'uc': next((r['uc'] for r in rs if r['uc']), ''), 'first': f, 'cost3': round(o['cost3']),
                        'cost_all': round(tot), 'act3': o['act'], 'rate3': o['rate'], 'cpr3': o['cpr'],
                        'ids': sorted({r['id'] for r in rs}), 'why': 'near3' if a_hit else 'new7'})
    tpl.sort(key=lambda x: -x['cost3'])

    cs = {}
    if a.page and os.path.exists(a.page):
        h = open(a.page).read()
        m = re.search(r'<script type="application/json" id="results">(.*?)</script>', h, re.S)
        res = json.loads(m.group(1).replace('<\\/', '</'))
        cm = res.get('cs_mats') or []
        done = sorted({x['up'][:10] for x in cm if x.get('st') in ('pass', 'fail')})
        if done:
            # 窗口已走完的最近 3 个上传日里过了冷启的素材（最新一天可能一条都没过）
            us = done[-3:]
            cs = {'up': us[-1], 'days': us, 'n': {u: sum(1 for x in cm if x['up'][:10] == u) for u in us},
                  'pass': [dict({k: x.get(k) for k in ('name', 'uc', 'short', 'root', 'a3', 'r3', 'video')}, up=x['up'][:10]) for x in cm if x['up'][:10] in us and x.get('st') == 'pass']}
    out = {'D': d2s(D), 'window': {'cost3': sorted(s3), 'prev4': sorted(p4), 'cohort3': sorted(c3)},
           'market': mk, 'ucs': ucs, 'templates': tpl, 'cs_latest': cs}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1, default=float)
    rg = [u['uc'] for u in ucs if u['flag'] == 'rising_good']
    rw = [u['uc'] for u in ucs if u['flag'] == 'rising_watch']
    print(json.dumps({'market_rate': mk['rate'], 'market_cpr': mk['cpr'], 'rising_good': rg, 'rising_watch': rw,
                      'templates': [t['name'][:40] for t in tpl[:8]], 'cs_up': cs.get('up'), 'cs_pass': len(cs.get('pass', []))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
