"""Daily 素材分析 numbers for one data day D.

Usage:
  python3 tools/compute.py --sheet <投放数据_分日 dump.json> --date YYYY-MM-DD --out results.json

<dump.json> is the Google Sheets get_values result for '投放数据_分日'!A1:AA
({"values": [[header...], [row...], ...]}). Columns are found by header name.

Windows (D = the report day, usually yesterday):
- spend columns use D itself;
- 次留率 / 次留成本 use activations on D-3..D-1 with their next-day 次留
  (巨量 books 次留 on the callback day, so D's own activations are not complete yet).
"""
import argparse, datetime as dt, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TH = {'scale': 1000, 'min': 500, 'act': 30, 'drop': 200, 'low': 0.8, 'high': 1.25}
L1_SHORT = {'AI 个人助理综述': 'AI 综述', '工作沟通与协作': '工作', '个人日程与事务助理': '日程', '学习与成长': '学习',
            '购物与生活服务': '购物', '健康与运动': '健康', '信息检索与追踪': '信息追踪', '出行与旅行': '出行',
            '财务与投资': '理财', '随身记事与个人资料管理': '记事'}
WEEK = '一二三四五六日'

# 库外 materials matched to a UC by what the video actually shows (Reina 10/28).
FUZZY = [('在微信里直接跟Today对话', 'PS01'), ('记住个人偏好推荐礼物', 'NT01'), ('工作要求梳理与执行步骤拆解', 'WK02')]


def lab(d):
    return f'{d.month}/{d.day}'


def num(s):
    s = str(s or '').replace('¥', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_rows(path):
    vals = json.load(open(path))['values']
    head = vals[0]
    col = {h: i for i, h in enumerate(head)}
    need = {'date': '日期', 'platform': '平台', 'id': '素材ID', 'name': '素材名', 'cost': '消耗', 'act': '激活',
            'ret': '次留', 'l1': '一级分类', 'l2': '二级分类', 'uc': 'UC_ID'}
    miss = [v for v in need.values() if v not in col]
    if miss:
        sys.exit('missing columns: ' + ', '.join(miss))
    out = []
    for r in vals[1:]:
        if not r or not r[0]:
            continue
        g = lambda k: r[col[need[k]]] if col[need[k]] < len(r) else ''
        out.append({'date': g('date'), 'platform': g('platform'), 'id': g('id'), 'name': g('name'),
                    'cost': num(g('cost')), 'act': num(g('act')), 'ret': num(g('ret')),
                    'l1': g('l1'), 'l2': g('l2'), 'uc': g('uc')})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--linklib', help="get_values dump of '素材链接库'!A1:D (optional preview links)")
    a = ap.parse_args()

    Dd = dt.date.fromisoformat(a.date)
    days = [Dd - dt.timedelta(days=k) for k in (3, 2, 1, 0)]
    D = [d.isoformat() for d in days]
    W = D[:3]
    NEXT = {D[i]: D[i + 1] for i in range(3)}
    monday = (Dd - dt.timedelta(days=Dd.weekday())).isoformat()
    th = dict(TH, week=monday)

    ucs = json.load(open(os.path.join(HERE, 'ucs.json')))
    links = json.load(open(os.path.join(HERE, 'links.json')))
    if a.linklib:
        for r in json.load(open(a.linklib))['values'][1:]:
            if len(r) > 1 and r[0] and r[1].startswith('http') and r[0] not in links:
                links[r[0]] = {'link': r[1], 'type': '预览'}
    allrows = load_rows(a.sheet)
    have = {r['date'] for r in allrows}
    if D[3] not in have:
        sys.exit(f'NO_DATA {D[3]}: sheet ends at {max(have)}')

    first, names = {}, {}
    for r in allrows:
        if r['cost'] > 0 and r['date'] <= D[3] and (r['id'] not in first or r['date'] < first[r['id']]):
            first[r['id']] = r['date']
        if r['name']:
            names[r['id']] = r['name']
    R = [r for r in allrows if r['date'] in D]
    for r in R:
        r['fuzzy'] = False
        if r['uc'] == '库外':
            for key, uc in FUZZY:
                if key in r['name'] and uc in ucs:
                    r['uc'], r['l1'], r['l2'], r['fuzzy'] = uc, ucs[uc]['l1'], ucs[uc]['l2'], True
                    break
    unknown = sorted({r['uc'] for r in R if r['uc'] not in ucs})

    S = lambda rows, d, k, p=None: sum(r[k] for r in rows if r['date'] == d and (p is None or r['platform'] == p))

    def win(rows):
        return (sum(S(rows, d, 'cost') for d in W), sum(S(rows, d, 'act') for d in W),
                sum(S(rows, NEXT[d], 'ret') for d in W))

    cw, aw, rw = win(R)
    o = {'cost27': S(R, D[3], 'cost'), 'cost26': S(R, D[2], 'cost'), 'act27': S(R, D[3], 'act'), 'act26': S(R, D[2], 'act'),
         'ios27': S(R, D[3], 'cost', 'iOS'), 'n27': len({r['id'] for r in R if r['date'] == D[3] and r['cost'] > 0}),
         'rate_w': rw / aw if aw else None, 'cpr_w': cw / rw if rw else None}
    o['cpa27'] = o['cost27'] / o['act27'] if o['act27'] else None
    o['cpa26'] = o['cost26'] / o['act26'] if o['act26'] else None
    o['cpa25'] = S(R, D[1], 'cost') / S(R, D[1], 'act') if S(R, D[1], 'act') else None
    for i, n in [(0, 'rate24'), (1, 'rate25'), (2, 'rate26')]:
        a_ = S(R, D[i], 'act')
        o[n] = S(R, D[i + 1], 'ret') / a_ if a_ else None
    o['cpr25'] = S(R, D[1], 'cost') / S(R, D[2], 'ret') if S(R, D[2], 'ret') else None
    o['cpr26'] = S(R, D[2], 'cost') / S(R, D[3], 'ret') if S(R, D[3], 'ret') else None

    def label(rate, cpr, cost, big, small):
        pricey = cpr is None or cpr > th['high'] * o['cpr_w']
        if rate >= o['rate_w'] and cpr is not None and cpr <= o['cpr_w']:
            return big if cost > th['scale'] else small
        if rate >= o['rate_w'] and pricey:
            return '留存好但贵'
        if rate < th['low'] * o['rate_w'] or pricey:
            return '拖后腿'
        return '一般'

    # 一级
    t27 = S(R, D[3], 'cost') or 1
    bl = []
    for l1 in dict.fromkeys(r['l1'] for r in R):
        rs = [r for r in R if r['l1'] == l1]
        run = lambda d: len({r['id'] for r in rs if r['date'] == d and r['cost'] > 0})
        day_rate = lambda i: (S(rs, D[i + 1], 'ret') / S(rs, D[i], 'act')) if S(rs, D[i], 'act') >= th['act'] else None
        c, a_, rt = win(rs)
        ok = a_ >= th['act']
        bl.append({'l1': l1, 'n27': run(D[3]), 'n26': run(D[2]), 'cost27': S(rs, D[3], 'cost'), 'share27': S(rs, D[3], 'cost') / t27,
                   'act27': S(rs, D[3], 'act'), 'cpa27': (S(rs, D[3], 'cost') / S(rs, D[3], 'act')) if S(rs, D[3], 'act') else None,
                   'cost26': S(rs, D[2], 'cost'), 'rate': rt / a_ if ok else None, 'cpr': (c / rt) if ok and rt else None,
                   'rate24': day_rate(0), 'rate25': day_rate(1), 'rate26': day_rate(2)})
    bl.sort(key=lambda x: -x['cost27'])

    # 素材
    by_id = defaultdict(list)
    for r in R:
        by_id[r['id']].append(r)
    order = ['能放量', '潜力', '留存好但贵', '拖后腿', '一般']
    mat = []
    for i, rs in by_id.items():
        c, a_, rt = win(rs)
        if not (c >= th['min'] and a_ >= th['act']):
            continue
        rate = rt / a_
        cpr = c / rt if rt else None
        g = label(rate, cpr, c, '能放量', '潜力')
        f = first.get(i, '')
        uc = rs[0]['uc']
        lk = links.get(i, {})
        mat.append({'id': i, 'group': g, 'name': names.get(i, i), 'first': f, 'is_new': f >= th['week'], 'l1': rs[0]['l1'],
                    'l2': rs[0]['l2'], 'uc': uc, 'short': ucs.get(uc, {}).get('short', ''), 'cost_w': c, 'act_w': a_,
                    'rate': rate, 'cpr': cpr, 'cost27': S(rs, D[3], 'cost'), 'link': lk.get('link', ''), 'link_type': lk.get('type', '')})
    mat.sort(key=lambda x: -x['cost27'])  # 严格按昨天消耗排，分组看标签
    good = [m for m in mat if m['group'] in ('能放量', '潜力')]
    gs = {'n_scale': sum(m['group'] == '能放量' for m in mat), 'n_pot': sum(m['group'] == '潜力' for m in mat),
          'n_drop': sum(m['cost27'] < th['drop'] for m in good)}

    # use case
    by_uc = defaultdict(list)
    for r in R:
        by_uc[r['uc']].append(r)
    uct = []
    for uc, rs in by_uc.items():
        c, a_, rt = win(rs)
        c27 = S(rs, D[3], 'cost')
        if not (c > 0 or c27 > 0):
            continue
        ok = a_ >= th['act']
        rate = rt / a_ if ok else None
        cpr = (c / rt) if ok and rt else None
        st = label(rate, cpr, c, '能放量 + 次留好', '次留好、量还小') if ok else '激活太少'
        uct.append({'uc': uc, 'status': st, 'short': ucs.get(uc, {}).get('short', ''), 'l1': rs[0]['l1'],
                    'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0}), 'cost_w': c, 'act_w': a_,
                    'rate': rate, 'cpr': cpr, 'cost27': c27, 'n_good': sum(1 for m in good if m['uc'] == uc)})
    uct.sort(key=lambda x: -x['cost27'])

    # 单日上线批次
    tot = {d: S(R, d, 'cost') for d in D}
    coh = []
    for bd in sorted({first[r['id']] for r in R if r['id'] in first}, reverse=True):
        rs = [r for r in R if first.get(r['id'], '') == bd]
        if sum(S(rs, d, 'cost') for d in D) <= 0.5:
            continue
        a26, r27 = S(rs, D[2], 'act'), S(rs, D[3], 'ret')
        ok = a26 >= th['act']
        row = {'batch': lab(dt.date.fromisoformat(bd)), 'first': bd, 'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0}),
               'cost27': S(rs, D[3], 'cost'), 'rate': r27 / a26 if ok else None, 'cpr': (S(rs, D[2], 'cost') / r27) if ok and r27 else None}
        for d, k in zip(D, ['share24', 'share25', 'share26', 'share27']):
            row[k] = None if bd > d else (S(rs, d, 'cost') / tot[d] if tot[d] else None)
        coh.append(row)
    gb = lambda d: next((x for x in coh if x['first'] == d), {})
    nz = lambda v: v or 0
    wk = [x for x in coh if x['first'] >= th['week']]
    shift = {'week27': sum(nz(x['share27']) for x in wk), 'week26': sum(nz(x['share26']) for x in wk) if D[2] >= th['week'] else None,
             'rate_new': gb(D[2]).get('rate'), 'new_share26': gb(D[2]).get('share26'), 'new_share27': gb(D[2]).get('share27')}

    # 文字结论（按数据自动写，只陈述事实）
    P0 = lambda v: '—' if v is None else f'{v * 100:.0f}%'
    Y = lambda v: '—' if v is None else f'¥{v:,.0f}'
    b = lambda s: f'<b>{s}</b>'
    take = [f"能放量 + 次留好的 use case 有 {b(sum(u['status'] == '能放量 + 次留好' for u in uct))} 个，"
            f"素材 {b(gs['n_scale'])} 条，另有 {b(gs['n_pot'])} 条次留好但量还小。"]
    if gs['n_drop']:
        take.append(f"这些好素材里 {b(gs['n_drop'])} 条昨天花不到 {b(Y(th['drop']))}，没接上量。")
    if wk:
        s = f"本周（{lab(dt.date.fromisoformat(th['week']))} 起）上线的新素材昨天占消耗的 {b(P0(shift['week27']))}"
        if shift['week26'] is not None:
            s += f"（{lab(days[2])} 是 {b(P0(shift['week26']))}）"
        bd3 = gb(D[3])
        if bd3 and nz(bd3.get('share27')) > shift['week27'] / 2:
            s += f"，主要是 {lab(days[3])} 刚上的"
        take.append(s + '。')
    nb = gb(D[2])
    if nb.get('rate') is not None:
        rated = [x for x in coh if x['rate'] is not None]
        best = max(rated, key=lambda x: x['rate'])['first'] == D[2] if rated else False
        s = f"{lab(days[2])} 上线那批次留率 {b(P0(nb['rate']))}"
        s += '，是最好的一批' if best else ''
        s += f"，消耗占比从 {b(P0(nb.get('share26')))} 到 {b(P0(nb.get('share27')))}。"
        take.append(s)
    fell = o['cost27'] < o['cost26']
    moved = sorted([x for x in bl if (x['cost26'] - x['cost27'] if fell else x['cost27'] - x['cost26']) > 0],
                   key=lambda x: -abs(x['cost26'] - x['cost27']))[:3]
    l1_note = (f"比 {lab(days[2])} {'掉' if fell else '涨'}得最多的是" + '、'.join(L1_SHORT.get(x['l1'], x['l1']) for x in moved) + '。') if moved else ''

    meta = {'date': D[3], 'D': lab(days[3]), 'D1': lab(days[2]), 'D2': lab(days[1]), 'D3': lab(days[0]),
            'W': f'{lab(days[0])}–{days[2].day}' if days[0].month == days[2].month else f'{lab(days[0])}–{lab(days[2])}',
            'T': lab(Dd + dt.timedelta(days=1)), 'weekday': '周' + WEEK[Dd.weekday()], 'week': lab(dt.date.fromisoformat(th['week'])),
            'take': ''.join(take), 'l1_note': l1_note, 'built': dt.date.today().isoformat()}
    out = {'meta': [meta], 'th': [th], 'overview': [o], 'by_l1': bl, 'mat': [m for m in mat if m['group'] != '一般'], 'goodstats': [gs],
           'uc_tbl': uct, 'ucstats': [{'n_uc': sum(u['status'] == '能放量 + 次留好' for u in uct)}], 'cohort': coh, 'shift': [shift]}
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'D': D[3], 'rows': len(R), 'cost_D': round(o['cost27']), 'rate_w': o['rate_w'] and round(o['rate_w'], 4),
                      'cpr_w': o['cpr_w'] and round(o['cpr_w'], 1), 'good_uc': out['ucstats'][0]['n_uc'], 'scale': gs['n_scale'],
                      'pot': gs['n_pot'], 'unknown_uc': unknown, 'no_link_good': sum(1 for m in good if not m['link'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
