"""回补 T-2 那天日报的「当天次留」（Reina 11/11）。

X 天出的日报里，次留率只能看 X-3..X-1 激活的人；X 当天激活的人要等 X+1 的次留回传完，T = X+2 上午才看得到。
所以每天出 D（= T-1）的日报时，顺手把 X = D-1 那天日报的消耗排行补上「当天次留率 / 当天次留成本」两列。

用法：python3 tools/rt_backfill.py --sheet <分日文件> --date X
  - 分日表要有 X+1 的数（和 compute.py 一样用 load_rows，次留已挪到第二天，X 的 cohort 看 X+1 的 ret）。
  - 写 notes/rtday-X.json（compute.py 重跑 X 时会读），并改 X/index.html 里嵌的结果、按当前模板重画；X 是最新一天时也改 index.html。
口径：X 当天激活、X 当天消耗、X 当天激活的人第二天的次留（深度转化数）。次留率 = 次留 ÷ 激活，次留成本 = X 消耗 ÷ 次留。
激活不到 TH['act']（30）的照样显示，但灰字带激活数、不上色（样本小）；够 30 的和全盘同一天比上色。
"""
import argparse, datetime as dt, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import compute, build  # noqa: E402


def calc(sheet, X):
    nx = (dt.date.fromisoformat(X) + dt.timedelta(days=1)).isoformat()
    rows = compute.load_rows(sheet)
    have = {r['date'] for r in rows if r['cost'] > 0 or r['act'] > 0}
    if nx not in have:
        sys.exit(f'NO_DATA {nx}：分日表还没有 {X} 第二天的数，{X} 的当天次留还不能回补')
    act, ret, cost = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in rows:
        if r['date'] == X:
            act[r['id']] += r['act']; cost[r['id']] += r['cost']
        elif r['date'] == nx:
            ret[r['id']] += r['ret']
    A, Rt, C = sum(act.values()), sum(ret.values()), sum(cost.values())
    items = {i: [round(act[i]), round(ret[i]), round(cost[i], 2)] for i in set(act) | set(cost) if act[i] > 0 or cost[i] > 0}
    # 二、按 use case（Reina 11/13）：每个 use case 的当天次留，和到 X 为止最近 7 天每天的次留率（悬浮折线用）
    ucs = json.load(open(os.path.join(HERE, 'ucs.json')))
    Xd = dt.date.fromisoformat(X)
    d7 = [(Xd - dt.timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    st, av = compute.uc_cohort_days(rows, ucs, d7)
    uc = {u: [round(v[0]), round(v[1]), round(v[2], 2)] for (u, d), v in st.items() if d == X and u != '__all__' and (v[0] or v[2])}
    r7 = {u: compute.rate_series(st, u, d7, av) for u in {k[0] for k in st}}
    return {'date': X, 'fields': ['X 激活', 'X 激活的次留', 'X 消耗'], 'act': round(A), 'ret': round(Rt), 'cost': round(C, 2),
            'rate': Rt / A if A else None, 'cpr': C / Rt if Rt else None, 'items': items, 'uc': uc, 'rate7': r7}


def apply(res, note, th_act):
    """把 notes/rtday-X.json 写进结果：mat 每条加 rtd_act / rtd_rate / rtd_cpr，全盘放 rtday_meta。"""
    items = note.get('items', {})
    for m in res.get('mat', []):
        x = items.get(str(m.get('id')))
        for f in ('rtd_act', 'rtd_rate', 'rtd_cpr', 'rtd_small'):
            m.pop(f, None)
        if not x:
            m['rtd_act'] = 0
            continue
        a, r, c = x
        m['rtd_act'] = a
        if a > 0:
            m['rtd_rate'] = r / a
            m['rtd_cpr'] = c / r if r else None
        m['rtd_small'] = a < th_act
    res['rtday_meta'] = [{'date': note['date'], 'rate': note.get('rate'), 'cpr': note.get('cpr'), 'act': note.get('act')}]
    # 二、按 use case 的当天次留和 7 天折线（Reina 11/13）；旧的 rtday 文件没有这两项就不动
    ucn, r7 = note.get('uc'), note.get('rate7')
    for u in res.get('uc_tbl', []):
        if r7 and u.get('uc') in r7:
            u['rate7'] = r7[u['uc']]
        if ucn is None:
            continue
        for f in ('rtd_act', 'rtd_rate', 'rtd_cpr', 'rtd_small'):
            u.pop(f, None)
        a, r, c = ucn.get(u.get('uc'), [0, 0, 0])
        u['rtd_act'] = a
        if a > 0:
            u['rtd_rate'] = r / a
            u['rtd_cpr'] = c / r if r else None
        u['rtd_small'] = a < th_act
    if r7 and '__all__' in r7:
        res['rate7_all'] = [{'s': r7['__all__']}]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--date', required=True, help='要回补的日报日期 X（通常是 D-1）')
    a = ap.parse_args()
    X = a.date
    note = calc(a.sheet, X)
    p = os.path.join(ROOT, 'notes', f'rtday-{X}.json')
    json.dump(note, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
    page = os.path.join(ROOT, X, 'index.html')
    if not os.path.exists(page):
        print(json.dumps({'saved': p, 'page': None}, ensure_ascii=False))
        return
    h = open(page).read()
    m = re.search(r'<script type="application/json" id="results">(.*?)</script>', h, re.S)
    res = json.loads(m.group(1).replace('<\\/', '</'))
    th_act = (res.get('th') or [{}])[0].get('act', compute.TH['act'])
    apply(res, note, th_act)
    tpl = open(os.path.join(HERE, 'template.html')).read()
    meta = res['meta'][0]
    open(page, 'w').write(build.render(tpl, res, meta, '../'))
    reports = json.load(open(os.path.join(ROOT, 'reports.json')))
    latest = reports and reports[0]['date'] == X
    if latest:
        open(os.path.join(ROOT, 'index.html'), 'w').write(build.render(tpl, res, meta, './'))
    n = sum(1 for x in res.get('mat', []) if x.get('rtd_rate') is not None)
    print(json.dumps({'saved': p, 'page': page, 'latest': bool(latest), 'rate_all': note['rate'], 'cpr_all': note['cpr'], 'mat_with_rate': n}, ensure_ascii=False))


if __name__ == '__main__':
    main()
