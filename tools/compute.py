"""Daily 素材分析 numbers for one data day D.

Usage:
  python3 tools/compute.py --sheet <投放数据_分日 dump.json> --date YYYY-MM-DD --out results.json

<dump.json> is the Google Sheets get_values result for '投放数据_分日'!A1:AB
({"values": [[header...], [row...], ...]}). Columns are found by header name.

Windows (D = the report day, usually yesterday):
- spend columns use D itself;
- 次留率 / 次留成本 use activations on D-3..D-1 with their 次留. Since 11/4 the sheet holds 转化数 and
  深度转化数 (计费时间), both booked on the billing day; load_rows moves ret one day later so the code
  below can keep reading D's cohort from D+1. D's own activations are not complete yet.
- 连续 3 留率 / 成本 use activations on D-5..D-3: the「3日留存」column (AB, from 10/16) is booked
  on the activation day and needs about 3 days to settle, so D-2..D are left out. It is 巨量's
  retention_3d, which we report only when D1, D2 and D3 are all opened. It is not the exact-day
  D3 in the Daily Insight report.
"""
import argparse, datetime as dt, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scripts_lib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TH = {'scale': 1000, 'min': 500, 'act': 30, 'drop': 200, 'top': 500, 'rank': 1000, 'low': 0.8, 'high': 1.25,
      'judge_act': 50, 'stuck_n': 3, 'stuck_cost': 200}  # 判差和「判差还在花」的门槛（Reina 11/4 定）
L1_SHORT = {'AI 个人助理综述': 'AI 综述', '工作沟通与协作': '工作', '个人日程与事务助理': '日程', '学习与成长': '学习',
            '购物与生活服务': '购物', '健康与运动': '健康', '信息检索与追踪': '信息追踪', '出行与旅行': '出行',
            '财务与投资': '理财', '随身记事与个人资料管理': '记事'}
WEEK = '一二三四五六日'

# 库外 materials matched to a UC by what the video actually shows (Reina 10/28).
FUZZY = [('在微信里直接跟Today对话', 'PS03'), ('记住个人偏好推荐礼物', 'NT01'), ('工作要求梳理与执行步骤拆解', 'WK02')]


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
ZJH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zijianhao.json')
ZJH = (json.load(open(ZJH_PATH)).get('ids') or {}) if os.path.exists(ZJH_PATH) else {}
ZJH_NAME = '唯西自建号'


def kind_of(src, track, name, mid=None, kl=True):
    """素材类型 = 来源 · 改法（原片 / 只剪辑 / 换开头 / 全片重配 / AI 重拍）；唯西自建号单独一类。
    改法以 tools/gaifa.json（对过字幕的）为准；没对过的二剪写「二剪（未核对）」。kl=True 时名字里有「扩量」再加「· 扩量」。"""
    src, track, name = (src or '').strip(), (track or '').strip(), name or ''
    if (mid and mid in ZJH) or src in (ZJH_NAME, '自建号'):
        # 唯西自建号（Reina 11/9）：视频挂在星广任务里，来源会写星广，按 tools/zijianhao.json 的素材ID 单独算一类
        return ZJH_NAME
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
                    'l1': g('l1'), 'l2': g('l2'), 'uc': g('uc'), 'src': opt('来源'), 'track': opt('追踪类型'),
                    'r3': num(opt('3日留存')), 'has3': '3日留存' in col and opt('3日留存') != ''})
    return shift_ret(out)


def shift_ret(rows):
    """11/4 起表里激活 = 转化数（计费时间），次留 = 深度转化数（计费时间），都记在计费当天（Reina 定）。
    这里和 week.py 的算法都按「次留记在第二天」写的（D 天的 cohort 看 D+1 的 ret），
    所以读表时把 ret 统一往后挪一天，算出来的就是 D 天深度转化数 ÷ D 天转化数。
    最新一天的 ret 还没回传完，挪出去以后不用。"""
    if not rows:
        return rows
    last = max(r['date'] for r in rows)
    extra = []
    for r in rows:
        v, r['ret'] = r['ret'], 0
        nd = (dt.date.fromisoformat(r['date']) + dt.timedelta(days=1)).isoformat()
        if v and nd <= last:
            extra.append({**r, 'date': nd, 'cost': 0, 'act': 0, 'ret': v, 'r3': 0, 'has3': False})
    return sorted(rows + extra, key=lambda r: r['date'])


# 八、核心 insight 和下一步：use case 分层（Reina 10/31 定的逻辑）
# T1 能放量 + 次留好 → 主攻，多做变式；T2 中等量 + 次留好 → 次优先，小步加量；
# T3 能放量但次留不达标 → 做变式压成本，次留率低的推产品承接；其余是观察。
# 每天按前 5 个报告日各算一遍分层，用来看今天的变化（进出 T1）和一直成立的（连续几天在同一层）。
GOOD_RATE = 0  # 次留好 = 次留率和次留成本都比大盘均值好（Yitao、Reina 11/4 定）。之后要提高要求就把最低线写在这里
PLAN_TH = {'big': 0.03, 'mid': 0.008, 'act': 60, 'nice': 1.00, 'days': 5}
NO_PLAN = ('待对应', '客供', '库外', '')
CH_NAME = {'ai': 'AI', 'ec': '二创', 'yp': '原片'}


def bad_streak(allrows, Dd, th):
    """每条素材连续判差几天（Reina 11/4 定）。

    D 激活的人 D+1 才有次留，表 D+2 上午才看得到，所以 x 这天上午能看的是 x-4 到 x-2 激活的人。
    判差：这 3 天激活合计 >= judge_act，且次留率 < 同期全盘的 low 倍，或次留成本 > 同期全盘的 high 倍。
    报告日 D 的页面在 D+1 上午看，从 D+1 上午往回数。返回 {素材ID: {bad_n, bad_first, bad_after, bad_up}}。
    """
    one = dt.timedelta(days=1)
    cost, act, ret = defaultdict(float), defaultdict(float), defaultdict(float)
    tc, ta, tr = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in allrows:
        d = dt.date.fromisoformat(r['date'])
        cost[r['id'], d] += r['cost']; act[r['id'], d] += r['act']; ret[r['id'], d] += r['ret']
        tc[d] += r['cost']; ta[d] += r['act']; tr[d] += r['ret']

    def is_bad(i, x):
        ds = [x - one * k for k in (4, 3, 2)]
        c = sum(cost[i, d] for d in ds); a = sum(act[i, d] for d in ds); rt = sum(ret[i, d + one] for d in ds)
        C = sum(tc[d] for d in ds); A = sum(ta[d] for d in ds); R = sum(tr[d + one] for d in ds)
        if a < th['judge_act'] or not A or not R:
            return False
        return rt / a < th['low'] * R / A or not rt or c / rt > th['high'] * C / R

    out = {}
    for i in {r['id'] for r in allrows}:
        n, x = 0, Dd + one
        while n < 60 and is_bad(i, x):
            n += 1
            x -= one
        if not n:
            continue
        first = x + one  # 第一次判差那天上午
        after = sum(cost[i, first + one * k] for k in range((Dd - first).days + 1))
        on_first = cost[i, first]
        out[i] = {'bad_n': n, 'bad_first': first.isoformat(), 'bad_after': round(after, 2),
                  'bad_up': n >= 2 and cost[i, Dd] >= 500 and cost[i, Dd] >= 1.5 * on_first}
    return out


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
        bar = max(rate_w, GOOD_RATE)
        good = rate is not None and cpr is not None and rate >= bar and cpr <= cpr_w
        nice = rate is not None and cpr is not None and rate >= bar and cpr <= PLAN_TH['nice'] * cpr_w
        big = s['share4'] >= PLAN_TH['big']
        mid = s['share4'] >= PLAN_TH['mid'] and s['act_w'] >= PLAN_TH['act']
        s['tier'] = 'T1' if big and good else 'T3' if big else 'T2' if mid and nice else 'T0'
        flag = ''
        if s['tier'] == 'T3' and rate is not None:
            if rate >= 0.95 * bar and cpr is not None and cpr <= 1.05 * cpr_w:
                flag = '差一点进 T1'
            elif rate < 0.9 * rate_w:
                flag = '次留率低'
            elif rate < bar:
                flag = '次留率低于全盘'
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
    agg3 = defaultdict(lambda: [0.0, 0.0, 0.0])
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
        y = agg3[key]; y[0] += k.get('cost3', 0); y[1] += k.get('act3', 0); y[2] += k.get('ret3', 0)
    method = []
    for key, (c, a, rt, c27, n_) in agg.items():
        ok = a >= th['act'] and rt
        c3, a3, r3 = agg3[key]
        ok3 = a3 >= th['act'] and r3
        method.append({'method': key, 'cost_w': c, 'act_w': a, 'rate': rt / a if ok else None, 'cpr': c / rt if ok else None,
                       'cost27': c27, 'n27': n_, 'act3': a3, 'rate3': r3 / a3 if ok3 else None, 'cpr3': c3 / r3 if ok3 else None})
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
    days3 = [Dd - dt.timedelta(days=k) for k in (5, 4, 3)]
    W3 = [d.isoformat() for d in days3]
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
    R3 = [r for r in allrows if r['date'] in W3]
    for r in R + R3:
        r['fuzzy'] = False
        if r['uc'] == '库外':
            for key, uc in FUZZY:
                if key in r['name'] and uc in ucs:
                    r['uc'], r['l1'], r['l2'], r['fuzzy'] = uc, ucs[uc]['l1'], ucs[uc]['l2'], True
                    break
    unknown = sorted({r['uc'] for r in R if r['uc'] not in ucs})
    have3 = {d for d in W3 if any(r['has3'] for r in R3 if r['date'] == d)}

    def w3(rows):
        """连续 3 留：D-5..D-3 激活的人，消耗 / 激活 / 3日留存都按激活日。三天里有没出数的天就不算。"""
        rows = [r for r in rows if r['date'] in have3]
        c, a_, r3 = sum(r['cost'] for r in rows), sum(r['act'] for r in rows), sum(r['r3'] for r in rows)
        ok = len(have3) == 3 and a_ >= th['act']
        return {'cost3': c, 'act3': a_, 'ret3': r3, 'rate3': r3 / a_ if ok else None, 'cpr3': c / r3 if ok and r3 else None}

    def group3(key):
        g = defaultdict(list)
        for r in R3:
            g[key(r)].append(r)
        return {k: w3(v) for k, v in g.items()}
    NO3 = {'cost3': 0, 'act3': 0, 'ret3': 0, 'rate3': None, 'cpr3': None}

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
    g3 = w3(R3)
    o['rate3_w'], o['cpr3_w'], o['act3'] = g3['rate3'], g3['cpr3'], g3['act3']
    o['rate3_days'] = [(sum(r['r3'] for r in R3 if r['date'] == d) / a_) if d in have3 and (a_ := sum(r['act'] for r in R3 if r['date'] == d)) else None for d in W3]

    def ret_word(rate, cpr):
        # 标签 = 量 + 次留，日报周报统一（Reina 11/4）。次留好 = 次留率和次留成本都比大盘均值好。
        if rate is None:
            return None
        bar = max(o['rate_w'], GOOD_RATE)
        if rate >= bar and cpr is not None and cpr <= o['cpr_w']:
            return '次留好'
        if rate < th['low'] * o['rate_w'] or cpr is None or cpr > th['high'] * o['cpr_w']:
            return '次留差'
        return '次留一般'

    def label(rate, cpr, cost):
        # 素材：三天消耗过 scale 算能放量
        w = ret_word(rate, cpr)
        return ('能放量' if cost > th['scale'] else '量小') + ' + ' + w if w else '样本不够'

    def share_label(rate, cpr, spend4):
        # use case、素材类型：四天消耗占全盘 3% 以上算能放量
        w = ret_word(rate, cpr)
        if not w:
            return '样本不够'
        return ('能放量' if spend4 / ((cw + o['cost27']) or 1) >= PLAN_TH['big'] else '量小') + ' + ' + w

    # 一级
    t27 = S(R, D[3], 'cost') or 1
    bl = []
    l1_3 = group3(lambda r: r['l1'])
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
        bl[-1].update(l1_3.get(l1, NO3))
    bl.sort(key=lambda x: -x['cost27'])

    # 素材
    by_id = defaultdict(list)
    for r in R:
        by_id[r['id']].append(r)
    mat = []
    id_3 = group3(lambda r: r['id'])
    SCRIPTS = scripts_lib.load()
    # 脚本规律：三天激活够的素材，按脚本特征分组
    pat_items = []
    for i, rs in by_id.items():
        c_, a__, rt_ = win(rs)
        pat_items.append({'id': i, 'cost': c_, 'act': a__, 'ret': rt_})
    patterns = scripts_lib.patterns(pat_items, SCRIPTS, th['act'])
    for i, rs in by_id.items():
        c, a_, rt = win(rs)
        c27 = S(rs, D[3], 'cost')
        f = first.get(i, '')
        # 三天花够、激活够的打标签；昨天花了 ¥500 以上但还没次留的也放进来（新上线 / 激活太少）
        if a_ >= th['act'] and (c >= th['min'] or c27 >= th['top']):
            rate = rt / a_
            cpr = c / rt if rt else None
            g = label(rate, cpr, c)
        elif c27 >= th['top']:
            rate = cpr = None
            g = '新上线' if f >= D[2] else '样本不够'
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
        mat[-1].update(id_3.get(i, NO3))
        mat[-1]['script'] = scripts_lib.summary(SCRIPTS.get(i))
    mat.sort(key=lambda x: -x['cost27'])  # 严格按昨天消耗排，分组看标签
    good = [m for m in mat if m['group'] in ('能放量 + 次留好', '量小 + 次留好')]

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

    gs = {'n_scale': sum(m['group'] == '能放量 + 次留好' for m in mat), 'n_pot': sum(m['group'] == '量小 + 次留好' for m in mat),
          'n_drop': sum(m['cost27'] < th['drop'] for m in good)}

    # use case
    by_uc = defaultdict(list)
    for r in R:
        by_uc[r['uc']].append(r)
    uct = []
    uc_3 = group3(lambda r: r['uc'])
    for uc, rs in by_uc.items():
        c, a_, rt = win(rs)
        c27 = S(rs, D[3], 'cost')
        if not (c > 0 or c27 > 0):
            continue
        ok = a_ >= th['act']
        rate = rt / a_ if ok else None
        cpr = (c / rt) if ok and rt else None
        st = share_label(rate, cpr, c + c27)
        uct.append({'uc': uc, 'status': st, 'short': ucs.get(uc, {}).get('short', ''), 'l1': rs[0]['l1'],
                    'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0}), 'cost_w': c, 'act_w': a_,
                    'rate': rate, 'cpr': cpr, 'cost27': c27, 'act27': S(rs, D[3], 'act'), 'n_good': sum(1 for m in good if m['uc'] == uc)})
        uct[-1].update(uc_3.get(uc, NO3))
    uct.sort(key=lambda x: -x['cost27'])
    # 每个 use case 最近 7 天消耗（Reina 11/4 定，二、按 use case 的柱状图）
    d7 = [(Dd - dt.timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    cost7 = defaultdict(float)
    for r in allrows:
        if r['date'] not in d7:
            continue
        uc = r['uc']
        if uc == '库外':
            for key, u in FUZZY:
                if key in r['name'] and u in ucs:
                    uc = u
                    break
        cost7[(uc, r['date'])] += r['cost']
    for u in uct:
        u['days7'] = [[f'{int(d[5:7])}/{int(d[8:])}', round(cost7[(u['uc'], d)], 2)] for d in d7]
    # 每条素材最近 7 天消耗（Reina 11/4 定，四、昨天消耗排行的柱状图）
    cost7_m = defaultdict(float)
    for r in allrows:
        if r['date'] in d7:
            cost7_m[(r['id'], r['date'])] += r['cost']
    for m in mat:
        m['days7'] = [[f'{int(d[5:7])}/{int(d[8:])}', round(cost7_m[(m['id'], d)], 2)] for d in d7]
    streak = bad_streak(allrows, Dd, th)
    for m in mat:
        m.update(streak.get(m['id'], {}))

    # 昨天上新：D 第一次有消耗的全部素材，不设消耗门槛（Reina 11/9）
    newd = []
    for i, rs in by_id.items():
        if first.get(i) != D[3]:
            continue
        rd = [r for r in rs if r['date'] == D[3]]
        lk = links.get(i, {})
        ltype = lk.get('type', '')
        link = '' if ltype == '预览' else lk.get('link', '')
        uc = rs[0]['uc']
        newd.append({'id': i, 'name': names.get(i, i), 'kind': kind_of(rs[0]['src'], rs[0]['track'], names.get(i, i), i),
                     'uc': uc, 'short': ucs.get(uc, {}).get('short', ''), 'l1': rs[0]['l1'],
                     'cost27': sum(r['cost'] for r in rd), 'act27': sum(r['act'] for r in rd),
                     'ios': sum(r['cost'] for r in rd if r['platform'] == 'iOS'),
                     'link': link, 'link_type': ltype if link else '', 'video': pick_video(lk)})
    newd.sort(key=lambda x: -x['cost27'])

    # 素材类型
    kind_id = {}
    for r in R + R3:
        kind_id.setdefault(r['id'], kind_of(r['src'], r['track'], names.get(r['id'], r['id']), r['id'], kl=False))
    kind_3 = group3(lambda r: kind_id[r['id']])
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
        st = share_label(rate, cpr, c + c27)
        kt.append({'kind': k, 'status': st, 'n27': len({r['id'] for r in rs if r['date'] == D[3] and r['cost'] > 0}),
                   'cost27': c27, 'share27': c27 / t27, 'cost26': S(rs, D[2], 'cost'), 'act27': S(rs, D[3], 'act'),
                   'cost_w': c, 'act_w': a_, 'rate': rate, 'cpr': cpr, 'n_good': sum(1 for m in good if kind_id.get(m['id']) == k)})
        kt[-1].update(kind_3.get(k, NO3))
    kt.sort(key=lambda x: -x['cost27'])
    if not any(k['kind'] == ZJH_NAME for k in kt):
        # 唯西自建号一直列出来（Reina 11/9），没花钱时写「还没消耗」
        kt.append({'kind': ZJH_NAME, 'status': '还没消耗', 'n27': 0, 'cost27': 0.0, 'share27': 0.0, 'cost26': 0.0, 'act27': 0,
                   'cost_w': 0.0, 'act_w': 0, 'rate': None, 'cpr': None, 'n_good': 0, **NO3})

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
    for x in plan['uc']:
        x.update({k: v for k, v in uc_3.get(x['uc'], NO3).items() if k in ('act3', 'rate3', 'cpr3')})

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
            'W3': f'{lab(days3[0])}–{days3[2].day}' if days3[0].month == days3[2].month else f'{lab(days3[0])}–{lab(days3[2])}',
            'take': ''.join(take), 'l1_note': l1_note, 'built': dt.date.today().isoformat()}
    out = {'meta': [meta], 'th': [th], 'overview': [o], 'by_l1': bl, 'mat': [m for m in mat if not any(k in m['group'] for k in ('次留一般',)) or m['cost27'] >= th['top']], 'goodstats': [gs], 'kl': kl,
           'uc_tbl': uct, 'kind_tbl': kt, 'ucstats': [{'n_uc': sum(u['status'] == '能放量 + 次留好' for u in uct)}], 'cohort': coh, 'shift': [shift], 'newd': newd,
           'plan_uc': plan['uc'], 'plan_meta': [plan['meta']], 'plan_method': plan['method'], 'patterns': [patterns]}
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'D': D[3], 'rows': len(R), 'cost_D': round(o['cost27']), 'rate_w': o['rate_w'] and round(o['rate_w'], 4),
                      'cpr_w': o['cpr_w'] and round(o['cpr_w'], 1), 'rate3_w': o['rate3_w'] and round(o['rate3_w'], 4),
                      'cpr3_w': o['cpr3_w'] and round(o['cpr3_w'], 1), 'good_uc': out['ucstats'][0]['n_uc'], 'scale': gs['n_scale'],
                      'pot': gs['n_pot'], 'scripts': len(SCRIPTS), 'pattern_n': patterns['n'], 'unknown_uc': unknown, 'no_video': sum(1 for m in mat if not m['video']), 'kl': len(kl), 'new_D': len(newd),
                      'uc_lib_check': '',
                      'uc_banned': [k for k, v in ucs.items() if any(w in v.get('short', '') for w in ucs.get('_meta', {}).get('banned', []))]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
