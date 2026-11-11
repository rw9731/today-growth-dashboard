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
TH = {'scale': 1000, 'min': 500, 'act': 30, 'drop': 200, 'top': 500, 'rank': 300, 'low': 0.8, 'high': 1.25,
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


def up_day(i):
    """素材ID 里带的上传时间（右移 32 位是 unix 秒），按北京时间取日期。"""
    try:
        return (dt.datetime.utcfromtimestamp(int(i) >> 32) + dt.timedelta(hours=8)).date().isoformat()
    except (ValueError, OverflowError, OSError):
        return ''


def up_time(i):
    try:
        return (dt.datetime.utcfromtimestamp(int(i) >> 32) + dt.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    except (ValueError, OverflowError, OSError):
        return ''


def made_day(name):
    """素材名最后的日期当制作日（20261106 或 261106）；没有就空。"""
    m = re.findall(r'(?<!\d)(20\d{6}|2[5-9]\d{4})(?!\d)', name or '')
    if not m:
        return ''
    x = m[-1] if len(m[-1]) == 8 else '20' + m[-1]
    try:
        return dt.date(int(x[:4]), int(x[4:6]), int(x[6:])).isoformat()
    except ValueError:
        return ''


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
    ap.add_argument('--uploads', help='up_js.py 读出来的巨量当天上传清单（默认 notes/uploads-D.json），用来补上没花钱的新素材')
    ap.add_argument('--acct', help='acct_save.py 存的素材 × 账户汇总（默认 notes/acct-D.json），用来算投放账户数和账户跑起来率')
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
        # 三天花够、激活够的打标签；昨天花到消耗排行门槛但还没次留的也放进来（新上线 / 样本不够）
        top_in = min(th['top'], th['rank'])  # 消耗排行要列的都放进来（Reina 11/11：门槛降到 ¥300 后 ¥300–500 的被漏掉了）
        if a_ >= th['act'] and (c >= th['min'] or c27 >= top_in):
            rate = rt / a_
            cpr = c / rt if rt else None
            g = label(rate, cpr, c)
        elif c27 >= top_in:
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

    # 昨天上新 = D 上传到巨量的全部素材（Reina 11/9 改成按上传算，团队要看 制作 -> 上传 -> 消耗）。
    # 上传时间取素材ID 里带的时间；没花钱的素材投放表里没有，从巨量素材库清单（notes/uploads-D.json）补。
    up_path = a.uploads or os.path.join(os.path.dirname(HERE), 'notes', f'uploads-{D[3]}.json')
    upl = json.load(open(up_path)) if os.path.exists(up_path) else None
    rows_by_id = defaultdict(list)
    for r in allrows:
        if r['date'] <= D[3]:
            rows_by_id[r['id']].append(r)
    U = {i for i in rows_by_id if up_day(i) == D[3]} | set((upl or {}).get('items', {}))
    newd = []
    for i in U:
        rs = rows_by_id.get(i, [])
        name = names.get(i) or (upl or {}).get('items', {}).get(i, i)
        rd = [r for r in rs if r['date'] == D[3]]
        lk = links.get(i, {})
        ltype = lk.get('type', '')
        link = '' if ltype == '预览' else lk.get('link', '')
        if rs:
            uc, l1, src, track = rs[0]['uc'], rs[0]['l1'], rs[0]['src'], rs[0]['track']
        else:
            mu = [c for c in re.findall(r'(?<![A-Z])([A-Z]{2}\d{2})(?!\d)', name) if c in ucs]
            uc = mu[0] if mu else '库外'
            l1 = ucs.get(uc, {}).get('l1', '')
            low = name.lower().replace('_', ' ')
            src = 'KOC' if 'today koc' in low or 'todaykoc' in low else 'KOL' if 'today kol' in low or 'todaykol' in low else 'AIGC'
            track = ''
        newd.append({'id': i, 'name': name, 'kind': kind_of(src, track, name, i), 'uc': uc, 'short': ucs.get(uc, {}).get('short', ''), 'l1': l1,
                     'made': made_day(name), 'up': up_time(i), 'first': first.get(i, ''),
                     'cost27': sum(r['cost'] for r in rd), 'act27': sum(r['act'] for r in rd),
                     'link': link, 'link_type': ltype if link else '', 'video': pick_video(lk)})
    # 之前上传、D 才第一次花钱的，只在汇总里按上传日数一下
    early = defaultdict(lambda: [0, 0.0])
    for i, f in first.items():
        if f == D[3] and up_day(i) < D[3]:
            e = early[up_day(i)]
            e[0] += 1
            e[1] += sum(r['cost'] for r in rows_by_id[i] if r['date'] == D[3])
    newd_meta = {'uploads': bool(upl), 'up_n': (upl or {}).get('n'), 'early': [{'up': d, 'n': n, 'cost27': c} for d, (n, c) in sorted(early.items())]}
    # 没找到视频的「推送视频_X」用同一条成片 X 的视频（推送是同一个视频换了素材 ID）
    strip = lambda n: re.sub(r'_20\d{6}$', '', n.replace('推送视频_', '', 1)).strip()
    by_strip = defaultdict(list)
    for i, n in names.items():
        by_strip[strip(n)].append(i)
    for m in newd:
        if m['video']:
            continue
        for j in by_strip.get(strip(m['name']), []):
            v = pick_video(links.get(j, {}))
            if j != m['id'] and v:
                m['video'] = v
                break
    newd.sort(key=lambda x: (-x['cost27'], x['up']))

    # 被建和带量（Reina 11/9 放进日报第五节）：投放账户数 = 有展示的账户数（近似被建次数的下限）；
    # 账户跑起来 = 该账户首次展示后 3 天内花到 ¥100；带量 = 投放表里首次消耗起头 3 天、7 天的消耗、单日最高、第几天过 ¥1,000。
    acct_path = a.acct or os.path.join(os.path.dirname(HERE), 'notes', f'acct-{D[3]}.json')
    acct = json.load(open(acct_path)) if os.path.exists(acct_path) else None
    AI = (acct or {}).get('items', {})
    for m in newd:
        x = AI.get(m['id'])
        m['acc_show'] = x[1] if x else (0 if acct else None)
        m['acc_d'] = x[6] if x else (0 if acct else None)
    # 集中度（Reina 11/11）：D 当天单项目最高消耗、占这条素材 D 总消耗多少、在几个项目里花了钱（conc_js.py 按项目拆）。
    conc_path = os.path.join(os.path.dirname(HERE), 'notes', f'conc-{D[3]}.json')
    conc = json.load(open(conc_path)).get('items', {}) if os.path.exists(conc_path) else None
    if conc is not None:
        for m in mat:
            x = conc.get(m['id'])
            if x and x[0] > 0:
                m['conc_top'], m['conc_share'], m['conc_n'] = x[1], round(x[1] / x[0], 3), x[2]
    # 当天次留（Reina 11/11）：D 当天激活的人的次留要 T+2 才看得到，由下一天出日报时 rt_backfill.py 回补成 notes/rtday-D.json；重跑 D 时带上
    rtd_path = os.path.join(os.path.dirname(HERE), 'notes', f'rtday-{D[3]}.json')
    rtd_note = json.load(open(rtd_path)) if os.path.exists(rtd_path) else None
    cost_by = defaultdict(lambda: defaultdict(float))
    for r in allrows:
        if r['date'] <= D[3]:
            cost_by[r['id']][r['date']] += r['cost']
    rdays = [(Dd - dt.timedelta(days=k)).isoformat() for k in range(9, -1, -1)]
    recent = []
    for i, dd in cost_by.items():
        u = up_day(i)
        if u not in rdays:
            continue
        spent = sorted(d for d, c in dd.items() if c > 0)
        if not spent:
            continue
        f = spent[0]
        obs = (Dd - dt.date.fromisoformat(f)).days + 1
        seq = [dd.get((dt.date.fromisoformat(f) + dt.timedelta(days=k)).isoformat(), 0.0) for k in range(min(obs, 14))]
        r0 = rows_by_id[i][0] if rows_by_id.get(i) else None
        nm = names.get(i, i)
        x = AI.get(i)
        lk = links.get(i, {})
        recent.append({'id': i, 'name': nm, 'kind': kind_of(r0['src'], r0['track'], nm, i).split(' · ')[0] if r0 else '',
                       'uc': r0['uc'] if r0 else '', 'short': ucs.get(r0['uc'], {}).get('short', '') if r0 else '',
                       'made': made_day(nm), 'up': up_time(i), 'first': f, 'obs': obs,
                       'c3': round(sum(seq[:3])) if obs >= 3 else None, 'c7': round(sum(seq[:7])) if obs >= 7 else None,
                       'peak': round(max(seq)), 'd1k': next((k + 1 for k, c in enumerate(seq) if c >= 1000), None), 'tot': round(sum(dd.values())),
                       'acc_show': x[1] if x else None, 'acc_spend': x[2] if x else None, 'acc_100': x[3] if x else None,
                       'acc_ok': bool(x) and (Dd - dt.date.fromisoformat(x[0])).days >= 2,
                       'video': pick_video(lk), 'link': '' if lk.get('type') == '预览' else lk.get('link', ''), 'link_type': lk.get('type', '')})
    recent.sort(key=lambda m: (-(m['c3'] or 0), -m['tot']))

    # 冷启（Reina 11/11，朱艺涛提的牵引指标）：看上传当天起 4 天（上传当天 + 后 3 天）的激活，过「近 4 周上传素材同一窗口激活」的 80 分位，算过冷启。
    # 窗口按上传日算，不按首次消耗日：上传后 3 天还没花起来本身就是没过冷启。上传日 + 3 天的数出来以后这批就定了。
    # 分母 = 这天上传的全部素材：巨量素材库清单 notes/uploads-日期.json ∪ 投放表里有消耗的 ∪ 工作台有展示的。
    CSW = 4
    act_by, ret_by = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    day_tot = defaultdict(float)
    for r in allrows:
        if r['date'] <= D[3]:
            act_by[r['id']][r['date']] += r['act']
            ret_by[r['id']][r['date']] += r['ret']
            day_tot[r['date']] += r['cost']
    first_sp = {i: min(d for d, c in dd.items() if c > 0) for i, dd in cost_by.items() if any(c > 0 for c in dd.values())}
    D1 = (Dd - dt.timedelta(days=1)).isoformat()
    nx = lambda k: (dt.date.fromisoformat(k) + dt.timedelta(days=1)).isoformat()

    def win3(i, u):
        u0 = dt.date.fromisoformat(u)
        ks = [(u0 + dt.timedelta(days=k)).isoformat() for k in range(CSW)]
        a3 = sum(act_by[i].get(k, 0) for k in ks if k <= D[3])
        c3 = sum(cost_by[i].get(k, 0) for k in ks if k <= D[3])
        ar = sum(act_by[i].get(k, 0) for k in ks if k <= D1)
        rr = sum(ret_by[i].get(nx(k), 0) for k in ks if k <= D1)  # 分日表里 X 激活的次留记在 X+1 那行
        return a3, c3, (rr / ar if ar else None), ar, ks[-1] <= D[3]
    # 门槛按每个上传日自己的 cohort 定（Reina 11/11）：用上传日前 30 天到前 4 天上传、花过钱的素材（窗口都已走完），
    # B = 它们窗口激活的 80 分位（主口径）；C = 它们窗口激活占当时全盘激活比例的 80 分位 × 这批窗口里全盘激活（去掉预算影响）。
    q = lambda L, p_: sorted(L)[int(len(L) * p_)] if L else None
    day_act = defaultdict(float)
    for r in allrows:
        if r['date'] <= D[3]:
            day_act[r['date']] += r['act']
    mkt_act = lambda u: sum(day_act.get((dt.date.fromisoformat(u) + dt.timedelta(days=k)).isoformat(), 0) for k in range(CSW))
    spent_w = {i: win3(i, up_day(i))[:2] for i in first_sp if up_day(i)}
    _thc = {}

    def cs_thr(u):
        if u in _thc:
            return _thc[u]
        u0 = dt.date.fromisoformat(u)
        f0, f1 = (u0 - dt.timedelta(days=30)).isoformat(), (u0 - dt.timedelta(days=4)).isoformat()
        bw = [(a_, c_, up_day(i)) for i, (a_, c_) in spent_w.items() if f0 <= up_day(i) <= f1]
        if not bw:
            _thc[u] = None
            return None
        th_b = max(1, round(q([x[0] for x in bw], 0.8)))
        sh = q([x[0] / mkt_act(x[2]) for x in bw if mkt_act(x[2])], 0.8)
        mk = mkt_act(u)
        _thc[u] = {'b': th_b, 'c': max(1, round(sh * mk)) if sh and mk else None, 'share': sh, 'mkt': round(mk),
                   'from': f0, 'to': f1, 'n': len(bw), 'med': q([x[0] for x in bw], 0.5), 'c80': round(q([x[1] for x in bw], 0.8))}
        return _thc[u]
    upl_names, upl_days = {}, set()
    for k in range(60):
        dd_ = (Dd - dt.timedelta(days=k)).isoformat()
        up_ = os.path.join(os.path.dirname(HERE), 'notes', f'uploads-{dd_}.json')
        if os.path.exists(up_):
            upl_days.add(dd_)
            for i, v in json.load(open(up_)).get('items', {}).items():
                upl_names[i] = v[0] if isinstance(v, list) else v

    def root_of(n):
        n = re.sub(r'^推送视频_', '', n or '').strip()
        m = re.match(r'(.+?)-\s*([A-Z]{1,3}\d{2})-\s*(?:[A-Za-z]+-)?\d{1,2}(?!\d)', n)
        if m:
            return re.sub(r'^.*?[-_]', '', m.group(1)).strip(' -_') + '（' + m.group(2) + '）' if '-' in m.group(1) else m.group(1) + '（' + m.group(2) + '）'
        m = re.search(r'_(?:today ?)?(?:koc|kol)_(.+?)_(?:二创|精剪|精简|扩量)', n, re.I)
        if m:
            return m.group(1).replace('_', ' ').strip()
        n = n.split('_扩量')[0]
        return re.sub(r'[_-]\s*(20)?\d{6}.*$', '', n).strip(' -_')
    every = set(cost_by) | set(upl_names) | set(AI)
    nm_of = lambda i: names.get(i) or upl_names.get(i) or i
    roots_by_day = defaultdict(lambda: defaultdict(int))
    for i in every:
        roots_by_day[up_day(i)][root_of(nm_of(i))] += 1
    rec_by = {m['id']: m for m in recent}
    cs_mats = []
    for u in rdays:
        THU = cs_thr(u)
        ids = {i for i in every if up_day(i) == u}
        for i in ids:
            n = nm_of(i)
            r0 = rows_by_id[i][0] if rows_by_id.get(i) else None
            if r0:
                uc, src, track = r0['uc'], r0['src'], r0['track']
            else:
                mu = [c for c in re.findall(r'(?<![A-Z])([A-Z]{2}\d{2})(?!\d)', n) if c in ucs]
                uc = mu[0] if mu else '库外'
                low = n.lower().replace('_', ' ')
                src = 'KOC' if 'today koc' in low or 'todaykoc' in low else 'KOL' if 'today kol' in low or 'todaykol' in low else 'AIGC'
                track = ''
            rt = root_of(n)
            prev = sum(roots_by_day[(dt.date.fromisoformat(u) - dt.timedelta(days=k)).isoformat()].get(rt, 0) for k in range(1, 15))
            x = AI.get(i)
            e = {'id': i, 'name': n, 'up': up_time(i), 'kind': kind_of(src, track, n, i, kl=False), 'uc': uc, 'short': ucs.get(uc, {}).get('short', ''),
                 'root': rt, 'same': roots_by_day[u][rt], 'prev14': prev,
                 'acc_show': x[1] if x else None, 'acc_100': x[3] if x else None}
            a3, c3, r3, ar, done = win3(i, u)
            e.update({'first': first_sp.get(i, ''), 'a3': round(a3), 'c3': round(c3), 'r3': r3, 'ar3': round(ar),
                      'st': 'pass' if THU and a3 >= THU['b'] else ('fail' if done else 'wait'),
                      'st_c': 'pass' if THU and THU['c'] and a3 >= THU['c'] else ('fail' if done else 'wait')})
            if i not in first_sp or first_sp[i] > (dt.date.fromisoformat(u) + dt.timedelta(days=CSW - 1)).isoformat():
                e['nospend'] = True  # 窗口里一分钱没花
            m = rec_by.get(i)
            lk = links.get(i, {})
            e['video'] = (m or {}).get('video') or pick_video(lk)
            cs_mats.append(e)
    batches = []
    for u in rdays:
        g = [m for m in recent if m['up'][:10] == u]
        cg = [m for m in cs_mats if m['up'][:10] == u]
        if not g and not cg:
            continue
        sh = [m for m in g if m['acc_show']]
        s_show = sum(m['acc_show'] for m in sh)
        full = (Dd - dt.date.fromisoformat(u)).days >= 2
        c3s = [m['c3'] for m in g if m['c3'] is not None]
        npass, nfail, nwait = (sum(1 for m in cg if m['st'] == k) for k in ('pass', 'fail', 'wait'))
        cpass, cwait = (sum(1 for m in cg if m.get('st_c') == k) for k in ('pass', 'wait'))
        THU = cs_thr(u) or {}
        batches.append({'up': u, 'n': len(g), 'full': full, 'acc_mean': round(s_show / len(sh), 1) if sh else None,
                        'pass': (sum(m['acc_100'] for m in sh) / s_show) if s_show and full else None,
                        'any': (sum(1 for m in g if (m['acc_100'] or 0) > 0) / len(g)) if full and acct and g else None,
                        'c3_med': sorted(c3s)[len(c3s) // 2] if full and c3s else None,
                        'k1': sum(1 for m in g if m['d1k']) / len(g) if g else 0, 'tot': sum(m['tot'] for m in g),
                        'n_up': len(cg), 'upl': u in upl_days, 'cs_pass': npass, 'cs_fail': nfail, 'cs_wait': nwait,
                        'cs': npass / len(cg) if cg and not nwait else None, 'cs_sofar': npass / len(cg) if cg else None,
                        'win_end': (dt.date.fromisoformat(u) + dt.timedelta(days=CSW - 1)).isoformat(),
                        'mkt': round(sum(day_tot.get((dt.date.fromisoformat(u) + dt.timedelta(days=k)).isoformat(), 0) for k in range(CSW) if (dt.date.fromisoformat(u) + dt.timedelta(days=k)) <= Dd) / max(1, min(CSW, (Dd - dt.date.fromisoformat(u)).days + 1))),
                        'mkt_prev': round(sum(day_tot.get((dt.date.fromisoformat(u) - dt.timedelta(days=k)).isoformat(), 0) for k in range(1, 8)) / 7),
                        'th': THU.get('b'), 'th_c': THU.get('c'), 'th_share': THU.get('share'), 'th_mkt': THU.get('mkt'), 'th_from': THU.get('from'), 'th_to': THU.get('to'),
                        'th_n': THU.get('n'), 'th_med': THU.get('med'), 'th_c80': THU.get('c80'),
                        'cs_pass_c': cpass, 'cs_c': cpass / len(cg) if cg and not cwait else None, 'cs_c_sofar': cpass / len(cg) if cg else None})
    newd_meta['cs_th'] = (cs_thr(D[3]) or {}).get('b')
    newd_meta['cs_win'] = CSW
    pj_path = os.path.join(os.path.dirname(HERE), 'notes', f'proj-{D[3]}.json')  # proj_save.py：新素材建进几个项目、项目里怎么分钱
    pjd = json.load(open(pj_path)) if os.path.exists(pj_path) else None
    if pjd:
        PJ, MP = pjd.pop('projects', []), pjd.pop('mat_proj', {})
        # 同原片或同场景的其他版本在同一批项目里花了多少（看二剪、扩量是不是被自己的原片或别的版本挤掉）
        root_c = {}
        for m in cs_mats:  # 冷启素材都在最近 10 天，mat_proj 存了最近 14 天上传的
            ks_ = MP.get(m['id'], [])
            m['npj'] = len(ks_)
            sib, own, top = 0.0, 0.0, defaultdict(float)
            for k in ks_:
                for mid, c in PJ[k][2]:
                    if mid == m['id']:
                        own += c
                        continue
                    if mid not in root_c:
                        root_c[mid] = root_of(nm_of(mid))
                    if root_c[mid] == m['root']:
                        sib += c
                        top[mid] += c
            if sib > 0:
                t_ = max(top, key=top.get)
                m['sib'] = [round(sib), round(own), nm_of(t_), round(top[t_]), up_day(t_)]
        for b in batches:
            cg = [m for m in cs_mats if m['up'][:10] == b['up'] and 'npj' in m]
            lo, hi = [m for m in cg if m['a3'] < 10], [m for m in cg if m['a3'] >= 10]
            if not lo:
                continue
            med = lambda L: sorted(L)[len(L) // 2] if L else None
            ks = {k for m in lo for k in MP.get(m['id'], [])}
            # 钱去了哪：冷启窗口那几天（上传当天 + 后 3 天，到 D 为止）全盘的钱，按素材上传日分新老（用投放分日表，按天准）
            wd = [(dt.date.fromisoformat(b['up']) + dt.timedelta(days=k)).isoformat() for k in range(CSW)]
            wd = [d_ for d_ in wd if d_ <= D[3]]
            sp = defaultdict(float)
            for i_, dd_ in cost_by.items():
                c_ = sum(dd_.get(d_, 0) for d_ in wd)
                if c_ > 0:
                    sp[i_] = c_
            tot_ = sum(sp.values())
            old_ = sum(c for i_, c in sp.items() if up_day(i_) < b['up'])
            self_ = sum(c for i_, c in sp.items() if up_day(i_) == b['up'])
            top_old = sorted(((c, i_) for i_, c in sp.items() if up_day(i_) < b['up']), reverse=True)[:3]
            b['why_low'] = {'n': len(lo), 'npj_lo': med([m['npj'] for m in lo]), 'npj_hi': med([m['npj'] for m in hi]), 'zero': sum(1 for m in lo if not m['npj']),
                            'n_proj': len(ks), 'mats_med': med([PJ[k][1] for k in ks]), 'old_share': round(old_ / tot_, 3) if tot_ else None, 'self_share': round(self_ / tot_, 3) if tot_ else None, 'win_tot': round(tot_),
                            'top_old': [[nm_of(i_), round(c), up_day(i_)] for c, i_ in top_old], 'days': [wd[0], wd[-1]]}
    newd_meta['proj'] = pjd
    newd_meta['acct'] = bool(acct)
    newd_meta['acct_err'] = (acct or {}).get('err', [])


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

    # 单日批次（按首次消耗日期）
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
        s = f"本周（{lab(dt.date.fromisoformat(th['week']))} 起）首次消耗的素材昨天占消耗的 {b(P0(shift['week27']))}"
        if shift['week26'] is not None:
            s += f"（{lab(days[2])} 是 {b(P0(shift['week26']))}）"
        bd3 = gb(D[3])
        if bd3 and nz(bd3.get('share27')) > shift['week27'] / 2:
            s += f"，主要是 {lab(days[3])} 首次消耗的"
        take.append(s + '。')
    nb = gb(D[2])
    if nb.get('rate') is not None:
        rated = [x for x in coh if x['rate'] is not None]
        best = max(rated, key=lambda x: x['rate'])['first'] == D[2] if rated else False
        s = f"{lab(days[2])} 首次消耗那批次留率 {b(P0(nb['rate']))}"
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
    # 次留一般的只留消耗排行要列的（Reina 11/11：门槛降到 ¥300 后 ¥300–500 的次留一般被漏掉了）
    out = {'meta': [meta], 'th': [th], 'overview': [o], 'by_l1': bl, 'mat': [m for m in mat if not any(k in m['group'] for k in ('次留一般',)) or m['cost27'] >= min(th['top'], th['rank'])], 'goodstats': [gs], 'kl': kl,
           'uc_tbl': uct, 'kind_tbl': kt, 'ucstats': [{'n_uc': sum(u['status'] == '能放量 + 次留好' for u in uct)}], 'cohort': coh, 'shift': [shift], 'newd': newd, 'newd_meta': [newd_meta], 'ramp_batches': batches, 'ramp_mats': recent, 'cs_mats': cs_mats,
           'plan_uc': plan['uc'], 'plan_meta': [plan['meta']], 'plan_method': plan['method'], 'patterns': [patterns]}
    if rtd_note:
        import rt_backfill
        rt_backfill.apply(out, rtd_note, th['act'])
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'D': D[3], 'rows': len(R), 'cost_D': round(o['cost27']), 'rate_w': o['rate_w'] and round(o['rate_w'], 4),
                      'cpr_w': o['cpr_w'] and round(o['cpr_w'], 1), 'rate3_w': o['rate3_w'] and round(o['rate3_w'], 4),
                      'cpr3_w': o['cpr3_w'] and round(o['cpr3_w'], 1), 'good_uc': out['ucstats'][0]['n_uc'], 'scale': gs['n_scale'],
                      'pot': gs['n_pot'], 'scripts': len(SCRIPTS), 'pattern_n': patterns['n'], 'unknown_uc': unknown, 'no_video': sum(1 for m in mat if not m['video']), 'kl': len(kl), 'new_D': len(newd), 'new_D_spent': sum(1 for m in newd if m['first']), 'uploads_file': bool(upl),
                      'uc_lib_check': '',
                      'uc_banned': [k for k, v in ucs.items() if any(w in v.get('short', '') for w in ucs.get('_meta', {}).get('banned', []))]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
