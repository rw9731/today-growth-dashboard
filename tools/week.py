"""Weekly 素材周报 numbers for the week that starts on Monday M (Mon..Sun).

Usage:
  python3 tools/week.py --sheet <投放数据_分日 dump.json> --week YYYY-MM-DD --out week.json

--week is the Monday. Columns are found by header name ('投放数据_分日'!A1:AB).

Windows (W0 = Monday … W6 = Sunday):
- 消耗、在跑条数、新上素材：W0..W6；
- 次留率 / 次留成本：W0..W5 激活的人，次留记在回访那天（W1..W6），成本也只算 W0..W5；
- 连续 3 留率 / 成本：W0..W3 激活的人（AB 列「3日留存」按激活日记，是巨量回传的 D1、D2、D3 每天都打开，不是第 3 天当天回来）。
上一周用同样的口径算，用来比。
"""
import argparse, datetime as dt, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute as C  # noqa: E402
import scripts_lib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# 周报门槛（Reina 11/1：好的 use case、头部素材的消耗门槛比日报高）
WTH = {
    'uc_big_share': 0.03, 'uc_big_min': 20000,   # 能放量：周消耗 ≥ 全盘 3% 且 ≥ ¥20,000
    'uc_mid_share': 0.01, 'uc_act': 150,          # 次优先：周消耗 ≥ 全盘 1%、周激活 ≥ 150
    'nice': 1.10,                                 # 次优先的次留成本可以到全盘 1.1 倍
    'top_day': 2000,                              # 头部素材：这周有一天消耗 ≥ ¥2,000（Reina 11/2 定，不限条数）
    'top_share': 0.01, 'top_min': 5000,           # 拖后腿的素材：周消耗 ≥ 全盘 1% 且 ≥ ¥5,000
    'tag_act': 50,                                # 第四部分标「不好」至少要 50 个激活
    'top_act': 100,                               # 头部素材至少 100 个激活才判断次留
    'bad_cap': 8,                                 # 拖后腿最多几条
    'bad_rate': 0.85, 'bad_cpr': 1.20,            # 表现差：次留率 < 全盘 85% 或 次留成本 > 全盘 1.2 倍
    'run': 1000,
    'scope': 2000,                                # 周报要读全片脚本的范围：周消耗 ≥ ¥2,000                                  # 新素材「跑起来」= 本周消耗 ≥ ¥1,000
    'act': 30,
}
CH = {'ai': 'AI 短剧', 'ec': '二创', 'yp': '真人原片'}


def iso(d):
    return d.isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--week', required=True, help='Monday, YYYY-MM-DD')
    ap.add_argument('--out', required=True)
    ap.add_argument('--partial', action='store_true', help='预览用：周日数据还没出也算（不发布）')
    a = ap.parse_args()

    M = dt.date.fromisoformat(a.week)
    if M.weekday() != 0:
        sys.exit('--week must be a Monday')
    W = [iso(M + dt.timedelta(days=k)) for k in range(7)]
    P = [iso(M - dt.timedelta(days=7 - k)) for k in range(7)]  # 上一周

    ucs = json.load(open(os.path.join(HERE, 'ucs.json')))
    links = json.load(open(os.path.join(HERE, 'links.json')))
    allrows = C.load_rows(a.sheet)
    have = {r['date'] for r in allrows}
    if W[6] not in have and not a.partial:
        sys.exit(f'NO_DATA {W[6]}: sheet ends at {max(have)}')

    for r in allrows:
        if r['uc'] == '库外':
            for key, uc in C.FUZZY:
                if key in r['name'] and uc in ucs:
                    r['uc'], r['l1'], r['l2'] = uc, ucs[uc]['l1'], ucs[uc]['l2']
                    break
    first, names = {}, {}
    for r in allrows:
        if r['cost'] > 0 and (r['id'] not in first or r['date'] < first[r['id']]):
            first[r['id']] = r['date']
        if r['name']:
            names[r['id']] = r['name']
    kind = {}
    for r in allrows:
        kind.setdefault(r['id'], C.kind_of(r['src'], r['track'], names.get(r['id'], r['id']), r['id'], kl=False))
    chan = {r['id']: C.chan_of(r['src'], r['track'], names.get(r['id'], '')) for r in allrows}

    nxt = lambda d: iso(dt.date.fromisoformat(d) + dt.timedelta(days=1))
    by_day = defaultdict(list)
    for r in allrows:
        by_day[r['date']].append(r)
    have3 = {d for d in have if any(r['has3'] for r in by_day[d])}
    last = max(have)
    d3ok = lambda d: d in have3 and iso(dt.date.fromisoformat(d) + dt.timedelta(days=3)) <= last

    def stats(rows, days):
        """一组行（任意筛选后的）在一周 days 里的数。rows 要包含 days 之后一天（次留回访日）。"""
        rd = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # date -> cost, act, ret, r3
        for r in rows:
            x = rd[r['date']]
            x[0] += r['cost']; x[1] += r['act']; x[2] += r['ret']; x[3] += r['r3']
        spend = sum(rd[d][0] for d in days)
        act = sum(rd[d][1] for d in days)
        d2 = [d for d in days[:6] if nxt(d) in have]          # 次留要等回访那天的数
        a2 = sum(rd[d][1] for d in d2); c2 = sum(rd[d][0] for d in d2); ret = sum(rd[nxt(d)][2] for d in d2)
        d3 = [d for d in days[:4] if d3ok(d)]                 # 3 留要激活后满 3 天
        ok3 = bool(d3)
        a3 = sum(rd[d][1] for d in d3); c3 = sum(rd[d][0] for d in d3); r3 = sum(rd[d][3] for d in d3)
        ok = a2 >= WTH['act']
        o3 = ok3 and a3 >= WTH['act']
        return {'spend': spend, 'act': act, 'cpa': spend / act if act else None, 'act_r': a2, 'cost_r': c2,
                'rate': ret / a2 if ok else None, 'cpr': c2 / ret if ok and ret else None,
                'act3': a3, 'rate3': r3 / a3 if o3 else None, 'cpr3': c3 / r3 if o3 and r3 else None,
                'days': [round(rd[d][0], 2) for d in days]}

    span = lambda days: set(days) | {nxt(days[-1])}
    RW = [r for r in allrows if r['date'] in span(W)]
    RP = [r for r in allrows if r['date'] in span(P)]

    g, gp = stats(RW, W), stats(RP, P)
    tot = g['spend'] or 1
    rw, cw = g['rate'] or 0, g['cpr'] or 1e9
    r3w, c3w = g['rate3'], g['cpr3']
    ids_w = {r['id'] for r in RW if r['date'] in W and r['cost'] > 0}
    ids_p = {r['id'] for r in RP if r['date'] in P and r['cost'] > 0}
    new_w = {i for i in ids_w if first.get(i, '') >= W[0]}
    new_p = {i for i in ids_p if P[0] <= first.get(i, '') <= P[6]}
    o = {'spend': g['spend'], 'act': g['act'], 'cpa': g['cpa'], 'rate': g['rate'], 'cpr': g['cpr'], 'rate3': r3w, 'cpr3': c3w,
         'n_run': len(ids_w), 'n_new': len(new_w),
         'p_spend': gp['spend'], 'p_act': gp['act'], 'p_cpa': gp['cpa'], 'p_rate': gp['rate'], 'p_cpr': gp['cpr'],
         'p_rate3': gp['rate3'], 'p_cpr3': gp['cpr3'], 'p_n_run': len(ids_p), 'p_n_new': len(new_p)}

    # 两周按天：消耗、激活、次留率（按激活日）、3 留率（按激活日）
    daily = []
    for d in P + W:
        rs = by_day[d]
        act = sum(r['act'] for r in rs)
        ret_n = sum(r['ret'] for r in by_day.get(nxt(d), [])) if nxt(d) in have else None
        r3 = sum(r['r3'] for r in rs)
        mature3 = d3ok(d)
        daily.append({'date': d, 'week': 'this' if d in W else 'prev', 'spend': sum(r['cost'] for r in rs), 'act': act,
                      'rate': ret_n / act if act and ret_n is not None and act >= WTH['act'] else None,
                      'rate3': r3 / act if act and mature3 else None})

    # use case
    by_uc = defaultdict(list)
    for r in RW + [x for x in RP if x["date"] not in span(W)]:
        by_uc[r['uc']].append(r)
    uct = []
    for uc, rs in by_uc.items():
        if uc in C.NO_PLAN or uc not in ucs or '旧编号' in ucs[uc].get('short', ''):
            continue
        s = stats(rs, W)
        if s['spend'] <= 0:
            continue
        sp = stats(rs, P)
        share = s['spend'] / tot
        good = s['rate'] is not None and s['cpr'] is not None and s['rate'] >= rw and s['cpr'] <= cw
        nice = s['rate'] is not None and s['cpr'] is not None and s['rate'] >= rw and s['cpr'] <= WTH['nice'] * cw
        big = share >= WTH['uc_big_share'] and s['spend'] >= WTH['uc_big_min']
        mid = share >= WTH['uc_mid_share'] and s['act_r'] >= WTH['uc_act']
        tier = 'T1' if big and good else 'T3' if big else 'T2' if mid and nice else 'T0'
        flag = ''
        if tier == 'T3' and s['rate'] is not None:
            if s['rate'] >= 0.95 * rw and s['cpr'] is not None and s['cpr'] <= 1.05 * cw:
                flag = '差一点进 T1'
            elif s['rate'] < 0.9 * rw:
                flag = '次留率低'
            else:
                flag = '次留成本偏高'
        ids = {r['id'] for r in rs if r['date'] in W and r['cost'] > 0}
        ch = {}
        for c in CH:
            x = stats([r for r in rs if chan.get(r['id']) == c], W)
            if x['spend'] > 0:
                ch[c] = {'share': x['spend'] / s['spend'], 'rate': x['rate'], 'cpr': x['cpr'], 'act_r': x['act_r']}
        uct.append({'uc': uc, 'short': ucs[uc]['short'], 'l1': ucs[uc]['l1'], 'tier': tier, 'flag': flag, 'share': share,
                    'n_run': len(ids), 'n_new': len(ids & new_w), **{k: s[k] for k in ('spend', 'act', 'act_r', 'rate', 'cpr', 'act3', 'rate3', 'cpr3', 'days')},
                    'p_spend': sp['spend'], 'p_rate': sp['rate'], 'p_cpr': sp['cpr'], 'ch': ch})
    order = {'T1': 0, 'T2': 1, 'T3': 2, 'T0': 3}
    uct.sort(key=lambda u: (order[u['tier']], -u['spend']))

    # 一级分类
    by_l1 = defaultdict(list)
    for r in RW + [x for x in RP if x["date"] not in span(W)]:
        by_l1[r['l1'] or '未分类'].append(r)
    l1t = []
    for k, rs in by_l1.items():
        s = stats(rs, W)
        if s['spend'] <= 0:
            continue
        sp = stats(rs, P)
        ids = {r['id'] for r in rs if r['date'] in W and r['cost'] > 0}
        l1t.append({'l1': k, 'share': s['spend'] / tot, 'n_run': len(ids), 'n_new': len(ids & new_w),
                    **{x: s[x] for x in ('spend', 'act_r', 'rate', 'cpr', 'act3', 'rate3', 'cpr3', 'days')},
                    'p_spend': sp['spend'], 'p_rate': sp['rate'], 'p_cpr': sp['cpr']})
    l1t.sort(key=lambda x: -x['spend'])

    # 素材
    by_id = defaultdict(list)
    for r in RW:
        by_id[r['id']].append(r)
    top_bar = max(WTH['top_min'], WTH['top_share'] * tot)
    SCRIPTS = scripts_lib.load()
    scope, pat_items = [], []
    for i, rs in by_id.items():
        s = stats(rs, W)
        if s['spend'] >= WTH['scope']:
            scope.append({'id': i, 'name': names.get(i, i), 'spend': round(s['spend'])})
        pat_items.append({'id': i, 'cost': s['cost_r'], 'act': s['act_r'], 'ret': (s['cost_r'] / s['cpr']) if s['cpr'] else (s['rate'] or 0) * s['act_r']})
    scope.sort(key=lambda x: -x['spend'])
    patterns = scripts_lib.patterns(pat_items, SCRIPTS, WTH['act'])
    mats = []
    for i, rs in by_id.items():
        s = stats(rs, W)
        if s['spend'] < top_bar and max(s['days']) < WTH['top_day']:
            continue
        uc = rs[0]['uc']
        lk = links.get(i, {})
        ltype = lk.get('type', '')
        link = '' if ltype == '预览' else lk.get('link', '')
        good = max(s['days']) >= WTH['top_day'] and s['act_r'] >= WTH['top_act'] and s['rate'] is not None and s['cpr'] is not None and s['rate'] >= rw and s['cpr'] <= cw
        bad = s['spend'] >= top_bar and s['rate'] is not None and (s['rate'] < WTH['bad_rate'] * rw or (s['cpr'] or 1e9) > WTH['bad_cpr'] * cw)
        # 比全盘多花的钱：这条的次留如果按全盘次留成本买，要花多少；多出来的就是浪费
        excess = s['cost_r'] - s['cost_r'] / s['cpr'] * cw if s['cpr'] else None
        mats.append({'id': i, 'name': names.get(i, i), 'kind': C.kind_of(rs[0]['src'], rs[0]['track'], names.get(i, i), i),
                     'chan': chan.get(i, ''), 'uc': uc, 'short': ucs.get(uc, {}).get('short', ''), 'l1': rs[0]['l1'],
                     'first': first.get(i, ''), 'is_new': first.get(i, '') >= W[0],
                     **{k: s[k] for k in ('spend', 'act', 'act_r', 'rate', 'cpr', 'act3', 'rate3', 'cpr3', 'days')},
                     'share': s['spend'] / tot, 'good': good, 'bad': bad, 'excess': excess,
                     'video': C.pick_video(lk), 'link': link, 'link_type': ltype if link else '',
                     'script': scripts_lib.summary(SCRIPTS.get(i))})
    good_all = sorted([m for m in mats if m['good']], key=lambda m: -m['spend'])
    top = good_all
    for m in top:
        # 二创候选（给写周报的人参考，最后挑哪几条以 notes 为准）：次留率高全盘 5% 以上、次留成本低 10% 以上。
        # 连续 3 留不进这条规则：它对不是天天用的 use case 偏低。
        m['pick'] = bool(m['rate'] >= 1.05 * rw and m['cpr'] <= 0.9 * cw)
    bad = sorted([m for m in mats if m['bad']], key=lambda m: -(m['excess'] or 0))[:WTH['bad_cap']]
    # 第四部分（Reina 11/4：素材太少，要好和不好的标签）：这周有一天消耗到门槛或周消耗过线的全部列出，每条打标签。
    # 好 = 激活 ≥ 100，次留率不低于、次留成本不高于全盘；不好 = 激活 ≥ 50，次留率低于全盘 85% 或次留成本超过全盘 1.2 倍。
    def tag_of(m):
        if m['act_r'] < WTH['tag_act'] or m['rate'] is None:
            return '样本小'
        if m['rate'] < WTH['bad_rate'] * rw or (m['cpr'] or 1e9) > WTH['bad_cpr'] * cw:
            return '不好'
        if m['rate'] >= rw and (m['cpr'] or 1e9) <= cw:
            return '好' if m['act_r'] >= WTH['top_act'] else '样本小'
        return '一般'
    for m in mats:
        m['tag'] = tag_of(m)
    heads = sorted(mats, key=lambda m: -m['spend'])

    # 素材类型 + 本周产出
    by_k = defaultdict(list)
    for r in RW + [x for x in RP if x["date"] not in span(W)]:
        by_k[kind[r['id']]].append(r)
    good_ids = {m['id'] for m in good_all}
    week_spend = defaultdict(float)
    for r in RW:
        if r['date'] in W:
            week_spend[r['id']] += r['cost']
    kt = []
    for k, rs in by_k.items():
        s = stats(rs, W)
        nw = {i for i in new_w if kind[i] == k}
        np_ = {i for i in new_p if kind[i] == k}
        if s['spend'] <= 0 and not nw:
            continue
        kt.append({'kind': k, 'share': s['spend'] / tot, **{x: s[x] for x in ('spend', 'act_r', 'rate', 'cpr', 'act3', 'rate3', 'cpr3')},
                   'n_run': len({r['id'] for r in rs if r['date'] in W and r['cost'] > 0}),
                   'n_new': len(nw), 'n_new_run': sum(1 for i in nw if week_spend[i] >= WTH['run']),
                   'n_new_top': len(nw & good_ids), 'new_spend': sum(week_spend[i] for i in nw), 'p_n_new': len(np_)})
    kt.sort(key=lambda x: -x['spend'])

    # 按天上新（按渠道）
    prod = []
    for d in W:
        row = {'date': d}
        for c in list(CH) + ['']:
            row[c or 'other'] = sum(1 for i in new_w if first[i] == d and chan.get(i, '') == c)
        prod.append(row)

    # 按改法合并（和日报一样）
    agg = defaultdict(list)
    for r in RW:
        ps = kind[r['id']].split(' · ')
        if ps[0] == 'AI 短剧':
            key = 'AI 短剧 · ' + (ps[1] if len(ps) > 1 else '原片')
        elif ps[0] in ('KOC', 'KOL'):
            key = '真人原片' if len(ps) > 1 and ps[1] == '原片' else (ps[1] if len(ps) > 1 else '')
        else:
            continue
        agg[key].append(r)
    method = []
    for k, rs in agg.items():
        s = stats(rs, W)
        method.append({'method': k, **{x: s[x] for x in ('spend', 'act_r', 'rate', 'cpr', 'rate3', 'cpr3')},
                       'n_new': sum(1 for i in new_w if any(r['id'] == i for r in rs))})
    method.sort(key=lambda x: -x['spend'])

    # 周中和周末（周一到周五 / 周六周日）。次留要等回访日，所以周日激活的不算；3 留周末激活的还没满 3 天。
    pick = lambda st: {x: st[x] for x in ('spend', 'act', 'cpa', 'act_r', 'rate', 'cpr', 'act3', 'rate3')}
    WD, WE = W[:5], W[5:]
    def split(rs):
        return {'wd': pick(stats(rs, WD)), 'we': pick(stats(rs, WE))}
    wk = {'w': split(RW), 'p': {'wd': pick(stats(RP, P[:5])), 'we': pick(stats(RP, P[5:]))},
          'fri': pick(stats(RW, [W[4]])), 'sat': pick(stats(RW, [W[5]])),
          'l1': [{'l1': k, 'share': x['share'], **split(by_l1[k]), 'p_wd': pick(stats(by_l1[k], P[:5])), 'p_we': pick(stats(by_l1[k], P[5:]))} for k, x in ((y['l1'], y) for y in l1t) if x['share'] >= 0.005],
          'top': [{'id': m['id'], 'name': m['name'], 'uc': m['uc'], 'short': m['short'], **split(by_id[m['id']])} for m in top]}

    # 按素材上线天数拆（Reina 11/2：查周末为什么差）。次留的回访行按前一天的上线天数归。
    def age_of(i, d):
        return (dt.date.fromisoformat(d) - dt.date.fromisoformat(first[i])).days if i in first else None
    def band_rows(lo, hi, rows):
        out = []
        for r in rows:
            a0 = age_of(r['id'], r['date'])
            if a0 is not None and lo <= a0 <= hi:
                out.append({**r, 'ret': 0, 'r3': 0})
            a1 = a0 - 1 if a0 is not None else None
            if a1 is not None and lo <= a1 <= hi:
                out.append({**r, 'cost': 0, 'act': 0, 'r3': 0})
        return out
    wk['age'] = [{'label': lb, **split(band_rows(lo, hi, RW))} for lb, lo, hi in (('上线 3 天内', 0, 3), ('上线 4 到 7 天', 4, 7), ('上线 8 天以上', 8, 9999))]
    # 同一批素材过周末：按首投日分批，留存只看当天激活的人
    def batch(a, b):
        ids = {i for i, f in first.items() if a <= f <= b}
        return ids, [r for r in allrows if r['id'] in ids]
    days = W[:7]
    wk['batch'] = []
    for f in days:
        ids, rs = batch(f, f)
        wk['batch'].append({'first': f, 'n': len(ids), 'by_day': {d: pick(stats(rs, [d])) for d in days if d >= f}})
    ids0, rs0 = batch(W[0], W[2])
    ids1, rs1 = batch(P[0], P[4])
    wk['carry'] = {'this': {'n': len(ids0), 'thu': pick(stats(rs0, [W[3]])), 'fri': pick(stats(rs0, [W[4]])), 'sat': pick(stats(rs0, [W[5]]))},
                   'last': {'n': len(ids1), 'before': pick(stats(rs1, P[3:5])), 'weekend': pick(stats(rs1, P[5:7])), 'after': pick(stats(rs1, W[:2]))}}

    lab = lambda s: f'{int(s[5:7])}/{int(s[8:10])}'
    meta = {'week': W[0], 'end': W[6], 'label': f'{lab(W[0])}–{lab(W[6])}', 'p_label': f'{lab(P[0])}–{lab(P[6])}',
            'w_ret': f'{lab(W[0])}–{lab(W[5])}', 'w_ret3': f'{lab(W[0])}–{lab(W[3])}', 'built': dt.date.today().isoformat(),
            'top_bar': top_bar, 'uc_bar': max(WTH['uc_big_min'], WTH['uc_big_share'] * tot), 'n_good_all': len(good_all)}
    out = {'meta': [meta], 'th': [WTH], 'overview': [o], 'daily': daily, 'uc': uct, 'l1': l1t, 'top': top, 'bad': bad, 'heads': heads, 'kind': kt,
           'wk': [wk], 'prod': prod, 'method': method, 'scope': scope, 'patterns': [patterns]}
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'week': meta['label'], 'spend': round(o['spend']), 'p_spend': round(o['p_spend']),
                      'rate': o['rate'] and round(o['rate'], 4), 'cpr': o['cpr'] and round(o['cpr'], 1),
                      'rate3': r3w and round(r3w, 4), 'n_new': o['n_new'], 'T1': [u['uc'] for u in uct if u['tier'] == 'T1'],
                      'top': len(top), 'good_all': len(good_all), 'scope': len(scope), 'scripted': sum(1 for x in scope if x['id'] in SCRIPTS), 'bad': len(bad), 'top_bar': round(top_bar),
                      'no_video': sum(1 for m in top + bad if not m['video'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
