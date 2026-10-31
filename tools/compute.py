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
import argparse, datetime as dt, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TH = {'scale': 1000, 'min': 500, 'act': 30, 'drop': 200, 'top': 500, 'low': 0.8, 'high': 1.25}
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


def pick_video(lk, now=None):
    """投放视频：唯西日报的永久链接优先；没有就用巨量的（签名链接，过期前 1 小时就不用）。"""
    import time
    if lk.get('video'):
        return lk['video']
    if lk.get('type') == '预览' and lk.get('link'):
        return lk['link']
    if lk.get('jl') and int(lk.get('jl_exp', 0)) > (now or time.time()) + 3600:
        return lk['jl']
    return ''


GAIFA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gaifa.json')
GAIFA = json.load(open(GAIFA_PATH)) if os.path.exists(GAIFA_PATH) else {}


def kind_of(src, track, name, mid=None, kl=True):
    """素材类型 = 来源 · 改法（原片 / 只剪辑 / 换开头 / 全片重配 / AI 重拍）。
    改法以 tools/gaifa.json（对过字幕的）为准；没对过的二剪写「二剪（未核对）」。kl=True 时名字里有「扩量」再加「· 扩量」。"""
    src, track, name = (src or '').strip(), (track or '').strip(), name or ''
    if src == 'AIGC' or 'AI短剧' in track:
        base = 'AI 短剧'
        dft = 'AI 重拍' if '照真人' in name else ('改法未核对' if '扩量' in name else '原片')
    elif src in ('KOC', 'KOL'):
        base = src
        dft = '二剪（未核对）' if ('二创' in track or '二创' in name or '扩量' in name) else '原片'
    else:
        base, dft = (src or '未标'), ''
    g = (GAIFA.get(mid) or {}).get('gaifa') if mid else None
    k = base + (' · ' + (g or dft) if (g or dft) else '')
    return k + (' · 扩量' if kl and '扩量' in name else '')


def base_name(n):
    n = re.sub(r'^推送视频_', '', n.strip())
    n = re.sub(r'\s*\(\d+\)$', '', n)
    n = re.sub(r'[_-]合规修改$', '', n)
    n = re.sub(r'_20\d{6}$', '', n)
    return n


def parent_of(n):
    b = base_name(n)
    i = b.rfind('_扩量')
    return b[:i].rstrip('_') if i > 0 else ''


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
        opt = lambda h: r[col[h]] if h in col and col[h] < len(r) else ''
        out.append({'date': g('date'), 'platform': g('platform'), 'id': g('id'), 'name': g('name'),
                    'cost': num(g('cost')), 'act': num(g('act')), 'ret': num(g('ret')),
                    'l1': g('l1'), 'l2': g('l2'), 'uc': g('uc'), 'src': opt('来源'), 'track': opt('追踪类型')})
    return out


# 七、核心 insight 和下一步：use case 分层（Reina 10/31 定的逻辑）
# T1 能放量 + 次留好 → 主攻，多做变式；T2 中等量 + 次留好 → 次优先，小步加量；
# T3 能放量但次留不达标 → 做变式压成本，次留率低的推产品承接；其余是观察。
# 每天按前 5 个报告日各算一遍分层，用来看今天的变化（进出 T1）和一直成立的（连续几天在同一层）。
PLAN_TH = {'big': 0.03, 'mid': 0.008, 'act': 60, 'nice': 1.10, 'days': 5}
NO_PLAN = ('待对应', '客供', '库外', '')
CH_NAME = {'ai': 'AI', 'ec': '二创', 'yp': '原片'}


def chan_of(src, track, name):
    src, track, name = (src or '').strip(), (track or '').strip(), name or ''
    if src == 'AIGC' or 'AI短剧' in track:
        return 'ai'
    if src in ('KOC', 'KOL'):
        return 'ec' if ('二创' in track or '二创' in name or '扩量' in name) else 'yp'
    return ''


def tiers_for(allrows, ucs, Dd, th):
    """报告日 Dd 的 use case 分层：消耗看 Dd-3..Dd 四天，次留看 Dd-3..Dd-1 激活。数据不够返回 None。"""
    D = [(Dd - dt.timedelta(days=k)).isoformat() for k in (3, 2, 1, 0)]
    W = D[:3]
    NEXT = {D[i]: D[i + 1] for i in range(3)}
    R = [r for r in allrows if r['date'] in D]
    if not any(r['date'] == D[0] for r in R) or not any(r['date'] == D[3] for r in R):
        return None
    S = lambda rows, d, k: sum(r[k] for r in rows if r['date'] == d)

    def stats(rows):
        c = sum(S(rows, d, 'cost') for d in W)
        a = sum(S(rows, d, 'act') for d in W)
        rt = sum(S(rows, NEXT[d], 'ret') for d in W)
        ok = a >= th['act']
        return {'spend4': sum(r['cost'] for r in rows), 'cost_w': c, 'act_w': a,
                'rate': rt / a if ok else None, 'cpr': c / rt if ok and rt else None}

    g = stats(R)
    rate_w, cpr_w = g['rate'] or 0, g['cpr'] or 1e9
    tot4 = g['spend4'] or 1
    by_uc = defaultdict(list)
    for r in R:
        if r['uc'] in NO_PLAN or r['uc'] not in ucs or '旧编号' in ucs[r['uc']].get('short', ''):
            continue
        by_uc[r['uc']].append(r)
    out = {}
    for uc, rs in by_uc.items():
        s = stats(rs)
        if s['spend4'] <= 0:
            continue
        s.update({'uc': uc, 'short': ucs[uc]['short'], 'l1': ucs[uc]['l1'], 'share4': s['spend4'] / tot4,
                  'cost27': S(rs, D[3], 'cost'), 'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0})})
        s['ch'] = {c: stats([r for r in rs if chan_of(r['src'], r['track'], r['name']) == c]) for c in CH_NAME}
        rate, cpr = s['rate'], s['cpr']
        good = rate is not None and cpr is not None and rate >= rate_w and cpr <= cpr_w
        nice = rate is not None and cpr is not None and rate >= rate_w and cpr <= PLAN_TH['nice'] * cpr_w
        big = s['share4'] >= PLAN_TH['big']
        mid = s['share4'] >= PLAN_TH['mid'] and s['act_w'] >= PLAN_TH['act']
        s['tier'] = 'T1' if big and good else 'T3' if big else 'T2' if mid and nice else 'T0'
        flag = ''
        if s['tier'] == 'T3' and rate is not None:
            if rate >= 0.95 * rate_w and cpr is not None and cpr <= 1.05 * cpr_w:
                flag = '差一点进 T1'
            elif rate < 0.9 * rate_w:
                flag = '次留率低'
            else:
                flag = '次留成本偏高'
        s['flag'] = flag
        out[uc] = s
    return {'uc': out, 'rate_w': rate_w, 'cpr_w': cpr_w, 'tot4': tot4, 'date': D[3]}


def build_plan(allrows, ucs, Dd, kt, th):
    n = PLAN_TH['days']
    hist = [tiers_for(allrows, ucs, Dd - dt.timedelta(days=k), th) for k in range(n - 1, -1, -1)]  # 最早到今天
    days = [h['date'] for h in hist if h]
    hist = [h for h in hist if h]
    cur = hist[-1]
    rows = []
    for uc, s in cur['uc'].items():
        seq = [h['uc'][uc]['tier'] if uc in h['uc'] else '' for h in hist]
        streak = 0
        for t in reversed(seq):
            if t == seq[-1]:
                streak += 1
            else:
                break
        prev = seq[-2] if len(seq) > 1 else ''
        s['hist'] = seq
        s['streak'] = streak
        s['prev'] = prev
        s['change'] = '' if not prev or prev == s['tier'] else prev + ' → ' + s['tier']
        if not prev and len(seq) > 1:
            s['change'] = '新出现'
        if len(hist) > 1 and uc in hist[-2]['uc']:
            p = hist[-2]['uc'][uc]
            s['d_rate'] = (s['rate'] - p['rate']) if s['rate'] is not None and p['rate'] is not None else None
            s['d_cpr'] = (s['cpr'] - p['cpr']) if s['cpr'] is not None and p['cpr'] is not None else None
        else:
            s['d_rate'] = s['d_cpr'] = None
        rows.append(s)
    # 前一天在层里、今天不见了的（四天消耗归零）
    gone = []
    if len(hist) > 1:
        for uc, p in hist[-2]['uc'].items():
            if uc not in cur['uc'] and p['tier'] != 'T0':
                gone.append({'uc': uc, 'short': p['short'], 'prev': p['tier']})
    order = {'T1': 0, 'T2': 1, 'T3': 2, 'T0': 3}
    rows.sort(key=lambda r: (order[r['tier']], -r['spend4']))
    meta = {'th': PLAN_TH, 'rate_w': cur['rate_w'], 'cpr_w': cur['cpr_w'], 'tot4': cur['tot4'], 'days': days, 'gone': gone,
            'ch_names': CH_NAME}

    # 剪辑手法：按改法合并（不分 KOC / KOL）
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
    for k in kt:
        ps = k['kind'].split(' · ')
        if ps[0] == 'AI 短剧':
            key = 'AI 短剧 · ' + (ps[1] if len(ps) > 1 else '原片')
        elif ps[0] in ('KOC', 'KOL'):
            key = '真人原片' if len(ps) > 1 and ps[1] == '原片' else (ps[1] if len(ps) > 1 else '')
        else:
            continue
        x = agg[key]
        x[0] += k['cost_w']; x[1] += k['act_w']; x[2] += (k['rate'] or 0) * k['act_w'] if k['rate'] is not None else 0
        x[3] += k['cost27']; x[4] += k['n27']
    method = []
    for key, (c, a, rt, c27, n_) in agg.items():
        ok = a >= th['act'] and rt
        method.append({'method': key, 'cost_w': c, 'act_w': a, 'rate': rt / a if ok else None, 'cpr': c / rt if ok else None,
                       'cost27': c27, 'n27': n_})
    method.sort(key=lambda x: -x['cost_w'])
    return {'uc': rows, 'meta': meta, 'method': method}


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
            if len(r) > 1 and r[0] and r[1].startswith('http'):
                e = links.setdefault(r[0], {})
                e.setdefault('video', r[1])
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
            return '次留好但贵'
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
    order = ['能放量 + 次留好', '次留好、量还小', '次留好但贵', '拖后腿', '一般']
    mat = []
    for i, rs in by_id.items():
        c, a_, rt = win(rs)
        c27 = S(rs, D[3], 'cost')
        f = first.get(i, '')
        # 三天花够、激活够的打标签；昨天花了 ¥500 以上但还没次留的也放进来（新上线 / 激活太少）
        if a_ >= th['act'] and (c >= th['min'] or c27 >= th['top']):
            rate = rt / a_
            cpr = c / rt if rt else None
            g = label(rate, cpr, c, '能放量 + 次留好', '次留好、量还小')
        elif c27 >= th['top']:
            rate = cpr = None
            g = '新上线' if f >= D[2] else '激活太少'
        else:
            continue
        uc = rs[0]['uc']
        lk = links.get(i, {})
        ltype = lk.get('type', '')
        video = pick_video(lk)
        link = '' if ltype == '预览' else lk.get('link', '')
        mat.append({'id': i, 'group': g, 'name': names.get(i, i), 'first': f, 'is_new': f >= th['week'], 'l1': rs[0]['l1'],
                    'kind': kind_of(rs[0]['src'], rs[0]['track'], names.get(i, i), i),
                    'l2': rs[0]['l2'], 'uc': uc, 'short': ucs.get(uc, {}).get('short', ''), 'cost_w': c, 'act_w': a_,
                    'rate': rate, 'cpr': cpr, 'cost27': S(rs, D[3], 'cost'), 'act27': S(rs, D[3], 'act'),
                    'link': link, 'link_type': ltype if link else '', 'video': video})
    mat.sort(key=lambda x: -x['cost27'])  # 严格按昨天消耗排，分组看标签
    good = [m for m in mat if m['group'] in ('能放量 + 次留好', '次留好、量还小')]

    # 扩量素材和它的原素材比：原素材按截至 D-1 激活的全部 cohort 算
    by_base = defaultdict(set)
    for i, n in names.items():
        by_base[base_name(n)].add(i)
    hist = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
    for r in allrows:
        if r['date'] <= D[3]:
            x = hist[r['id']][r['date']]
            x[0] += r['cost']; x[1] += r['act']; x[2] += r['ret']
    # 全盘每天的次留率（按激活日），用来给原素材算「同期全盘」
    day_act, day_ret = defaultdict(float), defaultdict(float)
    for r in allrows:
        day_act[r['date']] += r['act']; day_ret[r['date']] += r['ret']
    nxt = lambda d: (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
    day_rate = {d: day_ret[nxt(d)] / a for d, a in day_act.items() if a and nxt(d) <= D[3]}
    def cohort(ids):
        c = a_ = rt = base = 0.0
        for i in ids:
            for d, x in hist[i].items():
                nd = nxt(d)
                if nd <= D[3]:
                    c += x[0]; a_ += x[1]; rt += hist[i][nd][2] if nd in hist[i] else 0
                    base += x[1] * day_rate.get(d, 0)
        return c, a_, rt, (base / a_ if a_ else None)
    kl = []
    for m in good:
        par = parent_of(m['name'])
        if not par:
            continue
        src_ids = by_base.get(par, set()) - {m['id']}
        c, a_, rt, base = cohort(src_ids)
        kl.append({'id': m['id'], 'name': m['name'], 'kind': m['kind'], 'uc': m['uc'], 'short': m['short'], 'group': m['group'],
                   'rate': m['rate'], 'cpr': m['cpr'], 'cost_w': m['cost_w'], 'act_w': m['act_w'], 'cost27': m['cost27'], 'act27': m['act27'],
                   'src_name': par, 'src_ids': sorted(src_ids), 'src_n': len(src_ids), 'src_cost': c, 'src_act': a_,
                   'src_rate': rt / a_ if a_ >= th['act'] else None, 'src_cpr': c / rt if a_ >= th['act'] and rt else None,
                   'src_base': base, 'src_first': min((first[i] for i in src_ids if i in first), default='')})
    kl.sort(key=lambda x: -x['cost27'])

    gs = {'n_scale': sum(m['group'] == '能放量 + 次留好' for m in mat), 'n_pot': sum(m['group'] == '次留好、量还小' for m in mat),
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
                    'rate': rate, 'cpr': cpr, 'cost27': c27, 'act27': S(rs, D[3], 'act'), 'n_good': sum(1 for m in good if m['uc'] == uc)})
    uct.sort(key=lambda x: -x['cost27'])

    # 素材类型
    kind_id = {}
    for r in R:
        kind_id.setdefault(r['id'], kind_of(r['src'], r['track'], names.get(r['id'], r['id']), r['id'], kl=False))
    by_k = defaultdict(list)
    for r in R:
        by_k[kind_id[r['id']]].append(r)
    kt = []
    for k, rs in by_k.items():
        c, a_, rt = win(rs)
        c27 = S(rs, D[3], 'cost')
        if not (c > 0 or c27 > 0):
            continue
        ok = a_ >= th['act']
        rate = rt / a_ if ok else None
        cpr = (c / rt) if ok and rt else None
        st = label(rate, cpr, c, '能放量 + 次留好', '次留好、量还小') if ok else '激活太少'
        kt.append({'kind': k, 'status': st, 'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0}),
                   'cost27': c27, 'share27': c27 / t27, 'cost26': S(rs, D[2], 'cost'), 'act27': S(rs, D[3], 'act'),
                   'cost_w': c, 'act_w': a_, 'rate': rate, 'cpr': cpr, 'n_good': sum(1 for m in good if kind_id.get(m['id']) == k)})
    kt.sort(key=lambda x: -x['cost27'])

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
               'cost27': S(rs, D[3], 'cost'), 'act27': S(rs, D[3], 'act'), 'rate': r27 / a26 if ok else None, 'cpr': (S(rs, D[2], 'cost') / r27) if ok and r27 else None}
        for d, k in zip(D, ['share24', 'share25', 'share26', 'share27']):
            row[k] = None if bd > d else (S(rs, d, 'cost') / tot[d] if tot[d] else None)
        coh.append(row)
    gb = lambda d: next((x for x in coh if x['first'] == d), {})
    nz = lambda v: v or 0
    wk = [x for x in coh if x['first'] >= th['week']]
    shift = {'week27': sum(nz(x['share27']) for x in wk), 'week26': sum(nz(x['share26']) for x in wk) if D[2] >= th['week'] else None,
             'rate_new': gb(D[2]).get('rate'), 'new_share26': gb(D[2]).get('share26'), 'new_share27': gb(D[2]).get('share27')}

    plan = build_plan(allrows, ucs, Dd, kt, th)

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
    out = {'meta': [meta], 'th': [th], 'overview': [o], 'by_l1': bl, 'mat': [m for m in mat if m['group'] != '一般' or m['cost27'] >= th['top']], 'goodstats': [gs], 'kl': kl,
           'uc_tbl': uct, 'kind_tbl': kt, 'ucstats': [{'n_uc': sum(u['status'] == '能放量 + 次留好' for u in uct)}], 'cohort': coh, 'shift': [shift],
           'plan_uc': plan['uc'], 'plan_meta': [plan['meta']], 'plan_method': plan['method']}
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'D': D[3], 'rows': len(R), 'cost_D': round(o['cost27']), 'rate_w': o['rate_w'] and round(o['rate_w'], 4),
                      'cpr_w': o['cpr_w'] and round(o['cpr_w'], 1), 'good_uc': out['ucstats'][0]['n_uc'], 'scale': gs['n_scale'],
                      'pot': gs['n_pot'], 'unknown_uc': unknown, 'no_video': sum(1 for m in mat if not m['video']), 'kl': len(kl)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
