"""排期看板的数：从「投放数据_分日」算 spend.json、roi.json。

用法：
  python3 tools/schedule_data.py --sheet <分日文件> --date D --out-dir /tmp/sched [--today T] [--map <素材映射文件>]

<分日文件> 是 '投放数据_分日'!A1:AB 的 get_values 结果，按表头名找列。D = 数据日（一般是昨天），T = 看板当天（默认 D+1）。
<素材映射文件> 是 '素材映射'!A1:J 的 get_values 结果，PS03 三部分按 J 列「子方向（PS03）」分（Reina 11/4 定，按表读，不按名字猜）。
不给这个文件时才按素材名分，只用来对手算的旧版。
表里还没有 D 时打印 NO_DATA，退出码 2。

口径（Reina 11/4 定，排期看板用）：
- 批次日期 = 素材第一次上传巨量：int(素材ID)>>32 是秒，加 8 小时取日期。同名的推送版、修改版算同一条（去掉前缀和后缀后 union），取最早。
- spend：UC × 天 × 批次新旧 4 桶（上传 0–3、4–7、8–14、15 天以上）。n = 当天上传且花过钱的条数。
  c7 = D-6 到 D 的消耗；rate、cpr 看 D-6 到 D-1（次留看到 D-1）。
  结构和手算的那版一样：U[uc] = [c7, rate, cpr, 激活, "n,n,…", "桶;桶;…"]，桶的单位是 ¥10。
- PS03 三部分放在 U 的 PS03（接娃和班级群）、微信（消息排清单）、孩子（孩子的具体问题）。merged.PS03 是三部分合起来的数，页面表里用它。
  表里还是库外、靠 FUZZY 归到 PS03 的素材（字幕还没读）按消息排清单算；映射里 PS03 没标子方向的算接娃和班级群，会打 WARNING。
- roi：这批 = 首花在 D-7 到 D-2 的素材。y 每条产出 = 前 3 天消耗按全盘一天 ¥15 万折算后的条均。其余字段见 roi_row。
"""
import argparse, datetime as dt, json, os, re, sys
from math import comb
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ONE_DAY = 150000      # 每条产出按全盘一天 ¥15 万折算
HIT = 2000            # 放量：单日 ≥ ¥2,000
ALIVE = 100           # 最近 2 天还在花：日均 ≥ ¥100
RAMP = 200            # 起量日：第一次单日 ≥ ¥200
STABLE = dt.date(2026, 10, 29)  # 全盘 10/30 起稳定在一天 ¥15 万以上。10/28 那批赶上预算放开，43 条 39 条跑起来，后面的批次到不了，不进每条能花多少的样本
# 每条素材首花后第 k 天相对前 3 天日均的比例，k 超出后保持最后一个值。首花 10/29 起：首花当天约是第二天的一半（AI ¥173 对 ¥436，二创 ¥99 对 ¥189）；
# AI 第 2–3 天还在涨，第 4 天掉一半；二创第二天最高，第 2 天掉到 6 成。只有一周数据，11/7 看满 7 天后再校准
CURVE = {'AI': (.55, 1.05, 1.4, 1.7, .75), '二创': (.7, 1.4, .9, .9, .9)}
MIN_GAP = 500                   # 这天预计净跌不到这个数不预警
WARN_UC, WARN_ALL = .1, .05     # 也不到这个方向（全盘）现在消耗的这个比例，不预警
DROP = 0.5            # 预计下降比例：到第 4 天的素材预计掉一半。10/22–11/1 回测，日均 ≥¥1,000 的到第 4 天那两天还剩 59%，除全盘后 40%（Reina 11/5 定，跑两周再校准）
WX_NAME = '在微信里直接跟Today对话'
KID_NAMES = ('给孩子的具体问题', 'F04')
UNMARKED = []         # PS03 里花过钱、映射没标子方向的素材
SUB_KEY = {'接娃和班级群': 'PS03', '消息排清单': '微信', '孩子的具体问题': '孩子'}
# 库外素材按内容归的 use case，和 compute.py 的 FUZZY 一样（Reina 10/28、11/4）
FUZZY = [('在微信里直接跟Today对话', 'PS03'), ('记住个人偏好推荐礼物', 'NT01'), ('工作要求梳理与执行步骤拆解', 'WK02')]
SUFFIX = re.compile(r'(\s*[(（]\d+[)）]|[-_]?合规修改|[-_]?修改版?|[-_]改动)$')
CODE = re.compile(r'[A-Z]{1,2}\d{2}-\d{2}-[a-z]+-\d{8}$')


def num(s):
    s = str(s or '').replace('¥', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def values(path):
    d = json.load(open(path, encoding='utf-8'))
    return d['values'] if isinstance(d, dict) else d


def upload_day(mid):
    return (dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(mid) >> 32, hours=8)).date()


def canon(name):
    """去掉推送版、修改版的前后缀，剩下的算同一条。"""
    n = re.sub(r'^推送视频_', '', name.strip())
    while True:
        m = SUFFIX.search(n)
        if not m:
            return n
        n = n[:m.start()]


def load_rows(path):
    v = values(path)
    h = v[0]
    col = {k: h.index(k) for k in ('日期', '素材ID', '素材名', '消耗', '激活', '次留', 'UC_ID')}
    c_src = h.index('来源') if '来源' in h else None
    c_plat = h.index('平台') if '平台' in h else None
    rows = []
    for r in v[1:]:
        r = r + [''] * (len(h) - len(r))
        if not r[col['日期']] or not r[col['素材ID']]:
            continue
        uc = (r[col['UC_ID']] or '').strip()
        name = (r[col['素材名']] or '').strip()
        fuzzy = False
        if uc == '库外':
            for key, u in FUZZY:
                if key in name:
                    uc, fuzzy = u, True
                    break
        rows.append(dict(d=dt.date.fromisoformat(r[col['日期']][:10]), id=str(r[col['素材ID']]).strip(), name=name, c=num(r[col['消耗']]),
                         a=num(r[col['激活']]), r=num(r[col['次留']]), uc=uc, fuzzy=fuzzy, src=(r[c_src] or '').strip() if c_src is not None else '', p=(r[c_plat] or '').strip() if c_plat is not None else ''))
    return rows


def load_sub_map(path):
    """素材映射里标了子方向的素材：{素材ID: 接娃和班级群 / 消息排清单 / 孩子的具体问题}。表头是「子方向（PS03）」。"""
    if not path:
        return None
    v = values(path)
    h = [str(x).strip() for x in v[0]]
    ic = next((i for i, x in enumerate(h) if x.startswith('子方向')), None)
    if ic is None or '素材ID' not in h:
        print('WARNING 素材映射里没有子方向列，PS03 三部分按素材名分')
        return None
    ii = h.index('素材ID')
    out, odd = {}, set()
    for r in v[1:]:
        r = list(r) + [''] * (len(h) - len(r))
        val = str(r[ic]).strip()
        if val in SUB_KEY:
            out[str(r[ii]).strip()] = val
        elif val:
            odd.add(val)
    if odd:
        print('WARNING 素材映射的子方向有不认识的值：' + '、'.join(sorted(odd)))
    return out


def bucket(age):
    return 0 if age <= 3 else 1 if age <= 7 else 2 if age <= 14 else 3


def enc_day(seg):
    """¥10 为单位。全 0 写空；只有第一桶且个位是 0 时写「值去掉一个 0」，和手算那版的编码一样。"""
    x = [int(round(v / 10)) for v in seg]
    if not any(x):
        return ''
    if not any(x[1:]) and x[0] % 10 == 0:
        return str(x[0] // 10)
    return ','.join(str(v) for v in x)


def pct(r, a):
    return round(r / a * 100, 1) if a else None


def cost_per(c, r):
    return round(c / r) if r else None


class Fam:
    """同一条素材（推送版、修改版合起来）。"""
    def __init__(self):
        self.ids, self.names = set(), set()
        self.c, self.a, self.r = Counter(), Counter(), Counter()
        self.by_uc = Counter()
        self.src = Counter()
        self.sub = None
        self.from_fuzzy = False

    def key_uc(self):
        return self.by_uc.most_common(1)[0][0]


def families(rows, sub_map):
    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for r in rows:
        par[find('i:' + r['id'])] = find('n:' + canon(r['name']))
        m = CODE.search(canon(r['name']))
        if m:  # 同一个脚本编号（如 A18-06-cw-20261023）换过名字也是同一条片子
            par[find('i:' + r['id'])] = find('c:' + m.group(0))
    fams = defaultdict(Fam)
    of = {}
    for r in rows:
        f = fams[find('i:' + r['id'])]
        of[r['id']] = f
        f.ids.add(r['id'])
        f.names.add(r['name'])
        f.c[r['d']] += r['c']
        f.a[r['d']] += r['a']
        f.r[r['d']] += r['r']
        f.by_uc[r['uc']] += r['c']
        f.src[r['src']] += 1
        f.from_fuzzy = f.from_fuzzy or r['fuzzy']
    start = min(r['d'] for r in rows)
    for f in fams.values():
        f.upload = min(upload_day(i) for i in f.ids)
        spent = sorted(d for d, v in f.c.items() if v > 0)
        f.first = spent[0] if spent else None
        f.spent = bool(spent)
        # 批次按首花（Reina 11/5 定，和日报一致）。分日表最早一天就花了钱的，真正的首花在表外，用上传日
        f.batch = f.first if f.first and f.first > start else f.upload
        f.uc = f.key_uc()
        f.kind = 'AI' if f.src.most_common(1)[0][0] == 'AIGC' else '二创'  # 只分两类：AI 片（含二剪）和真人片的二创
        f.sub = sub_of(f, sub_map)
    return list(fams.values()), of


def sub_of(f, sub_map):
    """PS03 分三部分，别的 use case 就是自己。有映射按映射，没读字幕的库外微信线算消息排清单。"""
    if f.uc != 'PS03':
        return f.uc
    names = ' '.join(f.names)
    if sub_map is not None:
        for i in f.ids:
            if i in sub_map:
                return SUB_KEY[sub_map[i]]
        if f.from_fuzzy and WX_NAME in names:
            return '微信'
        if f.spent:
            UNMARKED.append(f)
        return 'PS03'
    if WX_NAME in names:
        return '微信'
    if any(k in names for k in KID_NAMES):
        return '孩子'
    return 'PS03'


def spend_uc(rows, fams, of, days, D):
    """同一条素材的钱按 UC_ID 那行算，这样加起来和表里一致。"""
    idx = {d: i for i, d in enumerate(days)}
    seg = defaultdict(lambda: [[0.0] * 4 for _ in days])
    run = defaultdict(lambda: [[set() for _ in range(4)] for _ in days])  # 在跑：当天花了钱的素材，按批次
    ret = defaultdict(lambda: [[0.0] * 8 for _ in days])  # 当天激活、次留，按批次：激活0、次留0、激活1、次留1……
    seven = Counter()
    win = defaultdict(lambda: [0.0, 0.0, 0.0])  # 消耗、激活、次留
    d6, d1 = D - dt.timedelta(days=6), D - dt.timedelta(days=1)
    for r in rows:
        f = of[r['id']]
        u = sub_of_row(r, f)
        if r['d'] in idx:
            b = bucket((r['d'] - f.batch).days)
            seg[u][idx[r['d']]][b] += r['c']
            if r['c'] > 0:
                run[u][idx[r['d']]][b].add(id(f))
            ret[u][idx[r['d']]][b * 2] += r['a']
            ret[u][idx[r['d']]][b * 2 + 1] += r['r']
        if d6 <= r['d'] <= D:
            seven[u] += r['c']
        if d6 <= r['d'] <= d1:
            w = win[u]
            w[0] += r['c']
            w[1] += r['a']
            w[2] += r['r']
    cnt = defaultdict(lambda: [0] * len(days))
    for f in fams:
        if f.spent and f.batch in idx:
            cnt[f.sub][idx[f.batch]] += 1
    return seg, seven, win, cnt, run, ret


def sub_of_row(r, f):
    return f.sub if r['uc'] == f.uc else r['uc']


def spend_row(u, seg, seven, win, cnt, n_days):
    w = win[u]
    s = seg[u] if u in seg else [[0.0] * 4 for _ in range(n_days)]
    return [round(seven[u]), pct(w[2], w[1]), cost_per(w[0], w[2]), int(w[1]),
            ','.join(str(x) for x in cnt[u]), ';'.join(enc_day(x) for x in s)]


def merge_seg(seg, keys, n_days):
    out = [[0.0] * 4 for _ in range(n_days)]
    for k in keys:
        if k in seg:
            for i in range(n_days):
                for j in range(4):
                    out[i][j] += seg[k][i][j]
    return out


def make_spend(rows, fams, of, D):
    days = [D - dt.timedelta(days=13 - i) for i in range(14)]
    seg, seven, win, cnt, run, ret = spend_uc(rows, fams, of, days, D)
    n = len(days)
    t = [[sum(seg[u][i][j] for u in seg) for j in range(4)] for i in range(n)]
    tw = [sum(win[u][k] for u in win) for k in range(3)]
    tn = [sum(cnt[u][i] for u in cnt) for i in range(n)]
    us = sorted(set(seg) | set(seven) | set(win) | set(cnt), key=lambda u: -seven[u])
    out = dict(days=[d.strftime('%m-%d') for d in days], t7=round(sum(seven.values())), rate=pct(tw[2], tw[1]), cpr=cost_per(tw[0], tw[2]),
               T=dict(s=';'.join(enc_day(x) for x in t), n=','.join(str(x) for x in tn)),
               U={u: spend_row(u, seg, seven, win, cnt, n) for u in us})
    enc_run = lambda m: ';'.join(','.join(str(len(x)) for x in day) for day in m)
    union = lambda us: [[set().union(*[run[u][i][j] for u in us if u in run]) if any(u in run for u in us) else set() for j in range(4)] for i in range(n)]
    out['run'] = {u: enc_run(run[u]) for u in run}
    out['T']['k'] = enc_run(union(list(run)))
    enc_ret = lambda m: ';'.join(','.join(str(int(round(v))) for v in day) if any(day) else '' for day in m)
    add_ret = lambda us: [[sum(ret[u][i][j] for u in us if u in ret) for j in range(8)] for i in range(n)]
    out['ret'] = {u: enc_ret(ret[u]) for u in ret}
    out['T']['ret'] = enc_ret(add_ret(list(ret)))
    keys = list(SUB_KEY.values())
    if any(k in out['U'] for k in keys):
        out['run_merged'] = {'PS03': enc_run(union(keys))}
        out['ret_merged'] = {'PS03': enc_ret(add_ret(keys))}
        w = [sum(win[k][i] for k in keys) for i in range(3)]
        c = [sum(cnt[k][i] for k in keys) for i in range(n)]
        s = merge_seg(seg, keys, n)
        out['merged'] = {'PS03': [round(sum(seven[k] for k in keys)), pct(w[2], w[1]), cost_per(w[0], w[2]), int(w[1]),
                                  ','.join(str(x) for x in c), ';'.join(enc_day(x) for x in s)]}
    return out


def day_avg(fams, tot):
    """每天大盘在跑素材平均每条花多少：全盘消耗 ÷ 当天花了钱的条数。"""
    run = Counter()
    for f in fams:
        for x, v in f.c.items():
            if v > 0:
                run[x] += 1
    return {x: tot[x] / n for x, n in run.items() if tot.get(x)}


def is_up(f, avg, D):
    """跑起来：首花第二天，花得比当天大盘平均每条多。跟当天大盘比，不定绝对值（Reina 11/5）。
    首花 10/29–11/1 的 179 条：过线 38 条（21%），之后单日到大盘平均 3 倍的 55%，占 71% 的钱；没过的 141 条 8%。
    只看第二天，当天冲一下第二天就掉的不算。还没有第二天的先看当天。"""
    x = f.first + dt.timedelta(days=1)
    x = x if x <= D else f.first
    return x in avg and f.c[x] >= avg[x]


def first_three_est(f, tot, D):
    """单条跑量用的前 3 天消耗。首花在 D-1 的只有两天，第 3 天按回测曲线估，这样前天上的那批也算得进来。"""
    v = first_three(f, tot)
    if (D - f.first).days >= 2:
        return v
    c = CURVE[f.kind]
    return v * (c[0] + c[1] + c[2]) / (c[0] + c[1])


def first_three(f, tot):
    """前 3 天消耗，每天按全盘一天 ¥15 万折算。"""
    v = 0.0
    for k in range(3):
        d = f.first + dt.timedelta(days=k)
        if tot.get(d):
            v += f.c[d] * ONE_DAY / tot[d]
    return v


def retention(fs, d1):
    c = a = r = 0.0
    for f in fs:
        for d in f.c:
            if d <= d1:
                c += f.c[d]
                a += f.a[d]
                r += f.r[d]
    return pct(r, a), cost_per(c, r)


def still_up(f, D, T):
    """接下来到第 4 天预计会掉的素材：起量（第一次单日 ≥ ¥200）在最近 6 天内、峰值在最近 2 天；或者首花到 T 还不满 4 天。
    D 时才第 0–1 天的还在起量，不算下降，算进供给（roi_row 的 n01）。
    返回 (预计下降额 = 最近 2 天日均 × DROP, 到第 4 天的日期)，不算的返回 None。"""
    last2 = (f.c[D] + f.c[D - dt.timedelta(days=1)]) / 2
    if last2 < ALIVE or not f.first or f.first >= D - dt.timedelta(days=1):
        return None
    dates = sorted(d for d, v in f.c.items() if d <= D and v > 0)
    peak_day = max(dates, key=lambda d: f.c[d])
    ramp = next((d for d in dates if f.c[d] >= RAMP), None)
    rising = peak_day >= D - dt.timedelta(days=1) and ramp and ramp >= D - dt.timedelta(days=5)
    new = f.first >= T - dt.timedelta(days=4)
    if not (rising or new):
        return None
    return last2 * DROP, max(T, f.first + dt.timedelta(days=4))


def roi_row(fs, batch_fs, tot, D, T, new14, total_new, c7, c7_total, y_fs=None):
    y_fs = batch_fs if y_fs is None else y_fs
    ys = sorted(first_three_est(f, tot, D) for f in y_fs)
    n = len(ys)
    s = sum(ys)
    rate, cpr = retention(batch_fs, D - dt.timedelta(days=1))
    d1 = D - dt.timedelta(days=1)
    lvl = sum((f.c[D] + f.c[d1]) / 2 for f in fs if (f.c[D] + f.c[d1]) / 2 >= ALIVE)
    chips = Counter()
    for f in fs:
        x = still_up(f, D, T)
        if x:
            chips[x[1].strftime('%m-%d')] += x[0]
    R = sum(chips.values())
    fresh = [f for f in fs if f.first and f.first >= D - dt.timedelta(days=1) and f.c[D] + f.c[d1] > 0]  # 第 0–1 天已上线、还在起量
    n01 = len(fresh)
    win = lambda a, b: sum(f.c[D - dt.timedelta(days=k)] for f in fs for k in range(a, b + 1))
    tw = lambda a, b: sum(tot.get(D - dt.timedelta(days=k), 0) for k in range(a, b + 1))
    mom = (win(0, 2) / tw(0, 2) - win(3, 5) / tw(3, 5)) * 100 if tw(0, 2) and tw(3, 5) else 0  # 最近 3 天占比减前 3 天占比
    yt = {}
    for t in CURVE:
        g = sorted((first_three(f, tot) for f in batch_fs if f.kind == t), reverse=True)
        yt[t] = dict(n=len(g), y=round(sum(g) / len(g)) if g else 0, yx=round(sum(g[1:]) / (len(g) - 1)) if len(g) > 1 else 0)
    fresh_t = {t: dict(Counter(f.first.strftime('%m-%d') for f in fresh if f.kind == t)) for t in CURVE}
    fresh_act = {t: round(sum(f.c[d] * ONE_DAY / tot[d] for f in fresh if f.kind == t for d in (d1, D) if tot.get(d))) for t in CURVE}
    return dict(yt=yt, fresh=fresh_t, fresh_act=fresh_act, n14=new14, n=n, y=round(s / n) if n else 0, yx=round((s - ys[-1]) / (n - 1)) if n > 1 else 0, top=round(ys[-1] / s, 2) if s else 0,
                hit=sum(1 for f in y_fs if max(f.c.values()) >= HIT), rate=rate, cpr=cpr,
                sh=round(c7 / c7_total * 100, 1) if c7_total else 0, np=round(new14 / total_new * 100, 1) if total_new else 0,
                mom=round(mom, 1), lvl=round(lvl), R=round(R), Dn=round(lvl) - round(R), n01=n01, chips={k: round(v) for k, v in sorted(chips.items())})


def flow(x, gt, t0, launches, days):
    """每天预计补上来多少、掉下去多少，只用来判断哪天要预警。是估计，不当预测展示。
    launches 是 {类型: {首花日: 条数}}。每条素材的钱按 CURVE 走，涨的算补，回落的算掉。
    每条每天 = 这个方向这类素材前 3 天日均（不足 5 条用这类素材全盘的），按现在全盘一天的钱折算。
    前两天刚上的素材按实际跑量校正：实际比预期低多少，后面补的也按比例少算。老素材掉的是 still_up 算的 chips。"""
    T = days[0]
    one = dt.timedelta(days=1)
    key = lambda d: d.strftime('%m-%d')
    parse = lambda s: dt.date(T.year, int(s[:2]), int(s[3:]))
    up, down = Counter(), Counter()
    for k, v in x['chips'].items():
        down[k] += v
    def add(first, n, p, curve, scale=1):
        for k, c in enumerate(curve):
            d = first + one * k
            if d >= T:
                move = n * p * scale * (c - (curve[k - 1] if k else 0))
                (up if move > 0 else down)[key(d)] += abs(move)
    for t, curve in CURVE.items():
        own = x['yt'][t]
        p15 = (own['y'] if own['n'] >= 5 else gt[t]['y']) / 3
        p = p15 * t0 / ONE_DAY
        for first, n in launches.get(t, {}).items():
            add(first, n, p, curve)
        fresh = [(parse(s), n) for s, n in x.get('fresh', {}).get(t, {}).items()]
        want = sum(n * p15 * sum(c for k, c in enumerate(curve) if first + one * k < T) for first, n in fresh)
        scale = min(1.5, x['fresh_act'][t] / want) if want else 1
        for first, n in fresh:
            add(first, n, p, curve, scale)
    keys = [key(d) for d in days]
    line = max(MIN_GAP, WARN_UC * x['lvl'])
    return dict(up={k: round(up[k]) for k in keys}, down={k: round(down[k]) for k in keys}, warn={k: round(down[k] - up[k]) for k in keys if x['lvl'] >= 1000 and down[k] - up[k] > line})


def total_warn(X, t0):
    """全盘这一行的预警：各方向合起来算。"""
    keys = sorted({k for x in X.values() for k in x['up']})
    net = {k: sum(x['down'][k] - x['up'][k] for x in X.values()) for k in keys}
    return {k: round(v) for k, v in net.items() if v > max(MIN_GAP, WARN_ALL * t0)}


def base_name(n):
    n = re.sub(r'^推送视频_', '', n.strip())
    n = re.sub(r'\s*\(\d+\)$', '', n)
    n = re.sub(r'[_-]合规修改$', '', n)
    return re.sub(r'_20\d{6}$', '', n)


def base_of(f, by_base, stat):
    """这条素材的底稿：扩量的上一版；二创的原片；都没有就用同一个脚本编号里激活够、次留最好的一条。"""
    for n in sorted(f.names, key=len):
        b = base_name(n)
        for parent, how in ((b[:b.rfind('_扩量')].rstrip('_') if '_扩量' in b else '', '底稿'), (re.split(r'[_-]二创', b)[0] if '二创' in b else '', '原片')):
            g = by_base.get(parent)
            if g and g is not f:
                return g, how
    for n in sorted(f.names, key=len):
        m = re.match(r'(.*-[A-Z]{1,2}\d{2})-', base_name(n))
        if m:
            same = [g for g in {id(x): x for k, x in by_base.items() if k.startswith(m.group(1) + '-')}.values() if g is not f and stat(g)[0] >= 50]
            if same:
                return max(same, key=lambda g: stat(g)[1] or 0), '同脚本'
    for n in sorted(f.names, key=len):
        stem = re.split(r'[_-](?:二创|扩量)', base_name(n))[0]
        same = [g for g in {id(x): x for k, x in by_base.items() if k.startswith(stem)}.values() if g is not f and stat(g)[0] >= 50]
        if same and stem != base_name(n):
            return max(same, key=lambda g: stat(g)[1] or 0), '同原片'
    return None, ''


def recover(fams, tot, D):
    """每天回收前 3 天放出去的素材。一条素材的钱很偏，几条素材的平均值高低多半是碰巧有没有爆款，所以看「跑起来几条」。
    跑起来见 is_up。按方向和类型分开看，AI 和二创差很多。
    预期 = 这个方向这类素材之前跑起来的比例（不足 5 条用这类素材全盘的）。碰巧这么低、这么高的概率不到 10% 才标。"""
    one = dt.timedelta(days=1)
    norm = lambda f, d: f.c[d] * ONE_DAY / tot[d] if tot.get(d) else 0
    avg = day_avg(fams, tot)
    up = lambda f: is_up(f, avg, D)
    per_day = lambda f: sum(norm(f, f.first + one * a) for a in range(min(3, (D - f.first).days) + 1)) / (min(3, (D - f.first).days) + 1)
    name = lambda f: min((n for n in f.names if not n.startswith('推送视频_')), key=len, default=next(iter(f.names)))
    part = {v: k for k, v in SUB_KEY.items()}
    lo = D - one * 3
    prior = [f for f in fams if f.first and f.spent and max(STABLE, lo - one * 10) <= f.first < lo]
    fresh = [f for f in fams if f.first and f.spent and lo <= f.first < D]
    rows = []
    share = lambda g: sum(1 for f in g if up(f)) / len(g)
    by = defaultdict(list)
    for f in fresh:
        by[f.sub, f.kind].append(f)
    win = lambda fs, a, b: sum(f.c[D - one * k] for f in fs for k in range(a, b + 1))
    tw = lambda a, b: sum(tot.get(D - one * k, 0) for k in range(a, b + 1))
    for (u, t), fs in by.items():
        if len(fs) < 3:
            continue
        old = [f for f in prior if f.sub == u and f.kind == t]
        base = old if len(old) >= 5 else [f for f in prior if f.kind == t]
        p = share(base) if base else .5
        n, k = len(fs), sum(1 for f in fs if up(f))
        cdf = lambda m: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(m + 1))
        tag = '符合'
        if n < 5:
            tag = '样本少'
        elif cdf(k) < .1:
            group = [f for f in fams if f.sub == u]
            sh = lambda a, b: win(group, a, b) / tw(a, b) if tw(a, b) else 0
            n7 = sum(1 for f in group if f.first and f.first >= D - one * 6)
            tag = '可能见顶' if sh(0, 2) <= sh(3, 5) and n7 >= 10 else '不及预期'
        elif k >= n / 2 and 1 - cdf(k - 1) < .1:
            tag = '超预期'
        best = max(fs, key=per_day)
        ra, cp = retention(fs, D - one)
        act = sum(f.a[d] for f in fs for d in f.a if d <= D - one)
        days = Counter(f.first.strftime('%m-%d') for f in fs)
        rows.append(dict(u=u, part=part.get(u), t=t, n=n, k=k, e=round(n * p, 1), days=dict(sorted(days.items())), per=round(sum(per_day(f) for f in fs) / n), tag=tag,
                         rate=ra if act >= 30 else None, cpr=cp if act >= 30 else None, best=name(best) if up(best) else None, best_v=round(per_day(best))))
    # 留存明显差的素材，配上底稿去看片。比同样这些天的全盘，不比老素材：老素材是筛过的，全盘每天的次留也在变
    d1 = D - one
    A0, R0 = Counter(), Counter()
    for f in fams:
        for x in f.a:
            A0[x] += f.a[x]
            R0[x] += f.r[x]
    def stat(f):
        c, a, r = (sum(m[x] for x in m if x <= d1) for m in (f.c, f.a, f.r))
        return a, round(r / a * 100, 1) if a else None, round(c / r) if r else None
    by_base = {}
    for f in fams:
        for n in f.names:
            by_base[base_name(n)] = f
    bad = []
    for f in fams:
        if not f.first or not D - one * 7 <= f.first < D:
            continue
        a, rate, cpr = stat(f)
        if a < 100:
            continue
        same_day = sum(f.a[x] * R0[x] / A0[x] for x in f.a if x <= d1 and A0[x])
        gap = rate - same_day / a * 100
        if gap <= -5:
            g, how = base_of(f, by_base, stat)
            item = dict(id=sorted(f.ids)[0], name=name(f), u=f.sub, part=part.get(f.sub), t=f.kind, first=f.first.strftime('%m-%d'), act=round(a), rate=rate, cpr=cpr, gap=round(gap, 1))
            if g:
                ga, gr, gc = stat(g)
                item['base'] = dict(id=sorted(g.ids)[0], name=name(g), how=how, act=round(ga), rate=gr, cpr=gc)
            bad.append((gap * a, item))
    bad = [x[1] for x in sorted(bad, key=lambda x: x[0])]
    rows.sort(key=lambda x: -x['per'])  # 每条带来的钱从高到低，一眼看出哪些方向 ROI 低
    peak = []
    for f in fams:
        if not f.first or f.first < D - one * 14:
            continue
        days = [d for d, v in f.c.items() if d <= D and v > 0]
        if not days:
            continue
        pk = max(days, key=lambda d: f.c[d])
        top = f.c[pk]
        last2 = (f.c[D] + f.c[D - one]) / 2
        if top >= 1000 and pk <= D - one * 2 and last2 >= ALIVE and f.c[D] < top * .7 and f.c[D - one] < top * .7:
            peak.append(dict(name=name(f), u=f.sub, part=part.get(f.sub), first=f.first.strftime('%m-%d'), pk=round(top), pkd=pk.strftime('%m-%d'), last2=round(last2), pct=round(last2 / top * 100)))
    peak.sort(key=lambda x: -x['pk'])
    return dict(rows=rows, bad=bad[:8], nbad=len(bad), peak=peak[:8], npeak=len(peak), nfresh=len(fresh), lo=lo.strftime('%m-%d'), hi=(D - one).strftime('%m-%d'))


def batches(fams, tot, D):
    """每个首花日这批素材：几条、几条跑起来、第二天每条花多少。条数和看板柱子下面的数一致（当天第一次花钱）。
    D 当天首花的还没有第二天，不算。"""
    one = dt.timedelta(days=1)
    norm = lambda f, d: f.c[d] * ONE_DAY / tot[d] if tot.get(d) else 0
    avg = day_avg(fams, tot)
    up = lambda f: is_up(f, avg, D)
    by = defaultdict(list)
    for f in fams:
        if f.spent and D - one * 15 <= f.batch < D:
            by[f.sub, f.batch].append(f)
    out = defaultdict(dict)
    for (u, b), fs in by.items():
        out[u][b.strftime('%m-%d')] = [len(fs), sum(1 for f in fs if up(f)), round(sum(f.c[b + one] for f in fs))]
    return out


def batch_items(fams, tot, D):
    """每批每条素材，给看板点开柱子用。批次和 batches 一样。items 按第二天花费从高到低：
    [素材ID, 素材名, 类型, 第一天, 第二天, 跑起来, 次留, 激活]，次留和激活看到 D-1（D 没回传完）。
    a0、r0 是这批首花当天的激活和次留，at、rt 是这批到 D-1 的合计。"""
    one = dt.timedelta(days=1)
    avg = day_avg(fams, tot)
    up = lambda f: is_up(f, avg, D)
    nm = lambda f: min((n for n in f.names if not n.startswith('推送视频_')), key=len, default=next(iter(f.names)))
    by = defaultdict(list)
    for f in fams:
        if f.spent and D - one * 15 <= f.batch < D:
            by[f.sub, f.batch].append(f)
    out = defaultdict(dict)
    for (u, b), fs in by.items():
        rows = []
        for f in sorted(fs, key=lambda f: -f.c[b + one]):
            a = sum(v for k, v in f.a.items() if k < D)
            r = sum(v for k, v in f.r.items() if k < D)
            rows.append([sorted(f.ids)[0], nm(f), f.kind, round(f.c[b]), round(f.c[b + one]), bool(up(f)), round(r / a * 100, 1) if a else None, round(a)])
        a0, r0 = sum(f.a[b] for f in fs), sum(f.r[b] for f in fs)
        at, rt = sum(v for f in fs for k, v in f.a.items() if k < D), sum(v for f in fs for k, v in f.r.items() if k < D)
        out[u][b.strftime('%m-%d')] = dict(c0=round(sum(f.c[b] for f in fs)), a0=round(a0), r0=round(r0), at=round(at), rt=round(rt), items=rows)
    return out


def tier_stats(fams, tot, D):
    """分档要看的数，窗口和页面「近 7 天」「次留」一样：消耗 D-6..D，次留到 D-1（D 没回传完）。"""
    one = dt.timedelta(days=1)
    norm = lambda f, d: f.c[d] * ONE_DAY / tot[d] if tot.get(d) else 0
    avg = day_avg(fams, tot)
    up = lambda f: is_up(f, avg, D)
    A0, R0 = Counter(), Counter()
    for f in fams:
        for x in f.a:
            A0[x] += f.a[x]
            R0[x] += f.r[x]
    t7 = sum(tot.get(D - one * k, 0) for k in range(7))
    def st(fs, days):
        lo = D - one * days
        c, a, r, b = 0, 0, 0, 0
        for f in fs:
            for x in set(f.c) | set(f.a):
                if lo <= x < D:
                    c += f.c[x]
                    a += f.a[x]
                    r += f.r[x]
                    if A0[x]:
                        b += f.a[x] * R0[x] / A0[x]
        return dict(a=round(a), rate=round(r / a * 100, 1) if a else None, cpr=round(c / r) if r else None, gap=round((r - b) / a * 100, 1) if a else None)
    def row(fs):
        ds = [sum(f.c[D - one * k] for f in fs) for k in range(7)]
        c7 = sum(ds)
        top = max((sum(f.c[D - one * k] for k in range(7)) for f in fs), default=0)
        lines = {f.first for f in fs if f.first and D - one * 6 <= f.first and up(f)}
        return dict(sh=round(c7 / t7 * 100, 1) if t7 else 0, d5=sum(1 for k, v in enumerate(ds) if tot.get(D - one * k) and v / tot[D - one * k] >= .03), top=round(top / c7 * 100) if c7 else 0, nb=len(lines), w7=st(fs, 6), w14=st(fs, 13))
    groups = defaultdict(list)
    for f in fams:
        if f.spent:
            groups[f.sub].append(f)
    out = {u: row(fs) for u, fs in groups.items()}
    every = [f for f in fams if f.spent]
    out['__gl'] = dict(w7=st(every, 6), w14=st(every, 13))
    keys = list(SUB_KEY.values())
    merged = [f for k in keys for f in groups.get(k, [])]
    if merged:
        out['PS03'] = row(merged)
    return out


RT_ALIAS = {'微信': 'PS03', '孩子': 'PS03'}  # 看板上 PS03 合成一行
RT_TAG = dict(new='新内容差', low='投放：低留存素材还在花', cheap='投放：放量买到便宜量', decay='老素材衰退',
              co='投放或流量：老素材同一天一起掉', ok='没有单一主因')
RT_NEXT = dict(new='看这批片子和上一批差在哪，先不加量。', low='这几条先关或限量。', cheap='查当天出价和账户，压便宜量。',
               decay='别再加钱，换开头或换底稿续上。', co='查当天账户和关停动作，先别改片子。', ok='看下面每条的数，先不动。')


def short_name(f):
    n = re.sub(r'^.*?today ko[cl]_', '', min(sorted(f.names), key=len))
    m = re.search(r'[A-Z]{1,3}\d{2}-[A-Za-z0-9]+-[A-Za-z]+', n)
    return m.group(0) if m else (n if len(n) <= 18 else n[:18] + '…')


def rt_diagnose(rows, of, D):
    """点开柱子的「这天留存为什么低」和按批次次留的趋势卡。全部按分日表算，账户层不在里面。
    比的都是相对当天大盘的差，这样 D-1 没回传完不影响。D 没回传，不算。
    方向：低于大盘 1 点以上，或比自己前 3 天（相对大盘）掉 3 点以上；激活不到 100 不算。贡献加起来等于总差。"""
    one = dt.timedelta(days=1)
    start = D - one * 14
    fam = {}
    daily = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0])))  # u -> 日 -> 素材 -> 消耗、激活、次留
    base = defaultdict(lambda: [0.0, 0.0])
    plat = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0])))
    for r in rows:
        if r['d'] < start - one * 10:
            continue
        f = of[r['id']]
        fam[id(f)] = f
        u = sub_of_row(r, f)
        u = RT_ALIAS.get(u, u)
        for k in (u, '__all'):
            x = daily[k][r['d']][id(f)]
            x[0] += r['c']
            x[1] += r['a']
            x[2] += r['r']
            y = plat[k][r['d']][r.get('p', '')]
            y[0] += r['a']
            y[1] += r['r']
        base[r['d']][0] += r['a']
        base[r['d']][1] += r['r']
    rate_of = lambda d: base[d][1] / base[d][0] * 100 if base[d][0] else 0
    pct_s = lambda v: ('+' if v >= 0 else '−') + f'{abs(v):.1f}'

    def prior(u, fid, d):
        """前 3 天：激活、次留、消耗、按这些激活加权的大盘次留、最高单日花费、有花费的天数。"""
        pa = pr = pc = pb = peak = nd = 0.0
        for i in range(1, 4):
            x = daily[u][d - one * i].get(fid)
            if x:
                pa, pr, pc = pa + x[1], pr + x[2], pc + x[0]
                pb += x[1] * rate_of(d - one * i)
                peak = max(peak, x[0])
                nd += 1 if x[0] > 0 else 0
        return pa, pr, pc, (pb / pa if pa else 0), peak, nd

    def cohort(u, d):
        """这天在跑的素材按首花日分：条数（当天花了钱或有激活）、首花第几天、同样这几条往前 10 天的激活和次留。"""
        ids = defaultdict(list)
        for fid, x in daily[u][d].items():
            if x[0] > 0 or x[1] > 0:
                ids[fam[fid].batch].append(fid)
        co = {}
        for b, fs in ids.items():
            pts = []
            for i in range(9, -1, -1):
                day = d - one * i
                a = sum(daily[u][day][fid][1] for fid in fs if fid in daily[u][day])
                r = sum(daily[u][day][fid][2] for fid in fs if fid in daily[u][day])
                pts.append(f'{round(a)},{round(r)}')
            co[b.strftime('%m-%d')] = dict(n=len(fs), age=(d - b).days, c=round(sum(daily[u][d][fid][0] for fid in fs)), p=';'.join(pts))
        return co

    def plat_line(u, d):
        ps = {k: v for k, v in plat[u][d].items() if k and v[0] >= 50}
        if len(ps) < 2:
            return ''
        (lk, lv), (hk, hv) = sorted(ps.items(), key=lambda kv: kv[1][1] / kv[1][0])[0], sorted(ps.items(), key=lambda kv: kv[1][1] / kv[1][0])[-1]
        if hv[1] / hv[0] - lv[1] / lv[0] < .05:
            return ''
        return f'{lk} {lv[1] / lv[0] * 100:.1f}%（{round(lv[0])} 激活），{hk} {hv[1] / hv[0] * 100:.1f}%。'

    def one_uc(u, d):
        ms = daily[u][d]
        A, R = sum(x[1] for x in ms.values()), sum(x[2] for x in ms.values())
        if A < 100:
            return None
        rate, bs = R / A * 100, rate_of(d)
        gap = rate - bs
        pa = pb = pr = 0.0
        for i in range(1, 4):
            for x in daily[u][d - one * i].values():
                pa, pr = pa + x[1], pr + x[2]
                pb += x[1] * rate_of(d - one * i)
        ex_p = (pr - pb) / pa if pa >= 100 else None
        below, worse = gap <= -1, ex_p is not None and gap - ex_p <= -3
        if not below and not worse:
            return None
        ref = bs if below else bs + ex_p
        total = rate - ref
        label = f'比大盘低 {abs(gap):.1f} 个点' if below else f'比自己前 3 天（相对大盘）掉 {abs(total):.1f} 个点'
        se = 196 * (rate / 100 * (1 - rate / 100) / A) ** .5
        if abs(total) < se:
            return dict(tag='差距在误差内', head=f'{label}，{round(A)} 激活的误差约 ±{se:.1f} 个点，不归因。', lines=[], next='')
        cats = defaultdict(list)
        for fid, x in ms.items():
            c, a, r = x
            if a <= 0:
                continue
            ct = a * (r / a * 100 - ref) / A
            f = fam[fid]
            age = (d - f.batch).days
            qa, qr, qc, qb, peak, nd = prior(u, fid, d)
            nx = daily[u][d + one].get(fid)
            info = dict(f=f, a=a, r=r, c=c, ct=ct, age=age, qa=qa, qc=qc, peak=peak, cn=nx[0] if nx else 0)
            ex_t = r / a * 100 - bs
            if a < 20:
                cats['misc'].append(info)
            elif age <= 3 or qa < 30:
                cats['new'].append(info)
            else:
                ex_q = qr / qa * 100 - qb
                info.update(ex_t=ex_t, ex_q=ex_q)
                err = 150 * (.16 / a + .16 / qa) ** .5
                daily_c = qc / max(nd, 1)
                if ex_q <= -2 and ex_t <= -2:
                    cats['low'].append(info)
                elif ex_t - ex_q <= -3 and ex_t - ex_q <= -err:
                    cheap = c >= 1.5 * daily_c and c / a <= .85 * (qc / qa)
                    cats['cheap' if cheap else 'decay'].append(info)
                else:
                    cats['ok'].append(info)
        hit = {k: sum(i['ct'] for i in v) for k, v in cats.items() if k != 'misc'}
        drag = sorted(((k, v) for k, v in hit.items() if v < 0), key=lambda kv: kv[1])
        tag = drag[0][0] if drag else 'ok'
        co = len(cats['decay']) + len(cats['cheap']) >= 3
        if co and hit.get('decay', 0) + hit.get('cheap', 0) <= (drag[0][1] if drag else 0) * .6:
            tag = 'co'
        tags = [tag]
        if tag != 'co' and len(drag) > 1 and drag[1][1] <= drag[0][1] * .5 and drag[1][0] != 'ok':
            tags.append(drag[1][0])
        lines = []
        cut = lambda i: f"，第二天已降到 ¥{round(i['cn']):,}" if i['cn'] <= .3 * i['c'] else ''
        def share(k):
            return sum(i['a'] for i in cats[k]) / A * 100
        for k in ('low', 'decay', 'cheap'):
            for i in sorted(cats[k], key=lambda i: i['ct'])[:2]:
                if i['ct'] > -.2:
                    continue
                nm = short_name(i['f'])
                if k == 'low':
                    lines.append(f"{nm} 前 3 天就低大盘 {abs(i['ex_q']):.1f} 个点，这天还花 ¥{round(i['c']):,}，占激活 {i['a'] / A * 100:.0f}%，贡献 {pct_s(i['ct'])} 点{cut(i)}。")
                else:
                    extra = f"，前面单日最高花到 ¥{round(i['peak']):,}" if i['peak'] >= 2 * i['c'] else ''
                    cheap_s = f"，激活成本 ¥{round(i['qc'] / i['qa'])} 到 ¥{round(i['c'] / i['a'])}" if k == 'cheap' else ''
                    lines.append(f"{nm} 相对大盘 {pct_s(i['ex_q'])} 到 {pct_s(i['ex_t'])}{extra}{cheap_s}，贡献 {pct_s(i['ct'])} 点{cut(i)}。")
        new_s = share('new')
        if cats['new']:
            na, nr = sum(i['a'] for i in cats['new']), sum(i['r'] for i in cats['new'])
            if hit.get('new', 0) < -.2:
                lines.append(f"首花 3 天内和没历史的 {len(cats['new'])} 条占激活 {new_s:.0f}%，次留 {nr / na * 100:.1f}%，贡献 {pct_s(hit['new'])} 点。")
        if new_s < 10 and tag != 'new':
            lines.append('不是新内容：这天几乎没有新素材的量。' if new_s < 1 else f'不是新内容：新素材只占激活 {new_s:.0f}%。')
        pl = plat_line(u, d)
        if pl:
            lines.append(pl)
        bq = [rate_of(d - one * i) for i in (1, 2, 3) if base[d - one * i][0]]
        if bq and bs - sum(bq) / len(bq) <= -2:
            lines.append(f'大盘这天也掉（前 3 天 {sum(bq) / len(bq):.1f}% 到 {bs:.1f}%），上面都是扣掉大盘后的差。')
        def next_step(ts):
            bad = [i for t in ('low', 'decay', 'cheap') if t in ts for i in cats[t] if i['ct'] <= -.2]
            if bad and all(i['cn'] <= .3 * i['c'] for i in bad) and all(t in ('low', 'decay', 'cheap') for t in ts):
                return '拖累的这几条第二天已经砍了，不用再动。'
            live = [t for t in ts if t not in ('low', 'decay', 'cheap') or any(i['ct'] <= -.2 and i['cn'] > .3 * i['c'] for i in cats[t])]
            return ''.join(RT_NEXT[t] for t in live or ts)
        return dict(tag=' + '.join(RT_TAG[t] for t in tags), head=f'{label}。', lines=lines[:4], next=next_step(tags))

    def one_all(d):
        ms = daily['__all'][d]
        A, R = sum(x[1] for x in ms.values()), sum(x[2] for x in ms.values())
        qa = qr = 0.0
        for i in range(1, 4):
            for x in daily['__all'][d - one * i].values():
                qa, qr = qa + x[1], qr + x[2]
        if A < 500 or qa < 500:
            return None
        rate, q = R / A * 100, qr / qa * 100
        if rate - q > -1.5:
            return None
        within = same = 0.0
        for fid, x in ms.items():
            pa, pr, _, _, _, _ = prior('__all', fid, d)
            if x[1] >= 20 and pa >= 30:
                within += x[1] * (x[2] / x[1] * 100 - pr / pa * 100) / A
                same += x[1]
        rest = rate - q - within
        dr = []
        for u in daily:
            if u == '__all' or d not in daily[u]:
                continue
            a, r = sum(x[1] for x in daily[u][d].values()), sum(x[2] for x in daily[u][d].values())
            if a >= 100:
                dr.append((a * (r / a * 100 - q) / A, u))
        dr.sort()
        lines = [f'同一批老素材自己掉贡献 {pct_s(within)} 点（占激活 {same / A * 100:.0f}%），新素材和结构贡献 {pct_s(rest)} 点。']
        if dr and dr[0][0] < 0:
            lines.append('拖得最多：' + '，'.join(f'{u} {pct_s(v)}' for v, u in dr[:3] if v < 0) + ' 点。')
        pl = plat_line('__all', d)
        if pl:
            lines.append(pl)
        main = within <= (rate - q) * .6
        return dict(tag='老素材一起掉，不是新内容' if main else '新素材和结构拖的', head=f'比前 3 天低 {q - rate:.1f} 个点（{q:.1f}% 到 {rate:.1f}%）。', lines=lines,
                    next='查当天投手动作和产品变更，不看单条片子。' if main else '看这天新上的和钱流向了哪些方向。')

    why, co = defaultdict(dict), defaultdict(dict)
    for u in list(daily):
        d = start
        while d <= D:
            if d in daily[u] and any(x[0] > 0 or x[1] > 0 for x in daily[u][d].values()):
                k = d.strftime('%m-%d')
                co[u][k] = cohort(u, d)
                w = None if d == D else one_all(d) if u == '__all' else one_uc(u, d)
                if w:
                    why[u][k] = w
            d += one
    days, d = [], start - one * 10
    while d <= D:
        days.append(d)
        d += one
    return dict(why=why, co=co, days=[x.strftime('%m-%d') for x in days], base=[[round(base[x][0]), round(base[x][1])] for x in days])


def history(rows, fams, D):
    """点 use case 名字看的历史素材（Reina 11/9）：表里所有花过钱的，按总消耗倒序。
    每条：[素材ID（按消耗排，最多 3 个，给链接找视频用）, 素材名, 类型, 首花, 总消耗, 激活, 次留, 消耗到前天, 近 7 天消耗, [第一天花钱离表首日几天, 逐日消耗, 逐日激活, 逐日次留]]。
    base 是全盘逐日 [激活, 次留]，从表首日到 D，画次留趋势的大盘线。
    次留和次留成本只算到 D-1（D 没回传完），所以另给一个「消耗到前天」算成本。"""
    one = dt.timedelta(days=1)
    idc, idn = Counter(), {}
    for r in rows:
        idc[r['id']] += r['c']
        if r['id'] not in idn or r['c'] > 0:
            idn[r['id']] = r['name']
    start = min(r['d'] for r in rows)
    out = defaultdict(list)
    for f in fams:
        if not f.spent:
            continue
        ids = sorted(f.ids, key=lambda i: -idc[i])
        a = sum(v for d, v in f.a.items() if d < D)
        r = sum(v for d, v in f.r.items() if d < D)
        cb = sum(v for d, v in f.c.items() if d < D)
        c7 = sum(f.c[D - one * k] for k in range(7))
        d0 = min(d for d, v in f.c.items() if v > 0)
        days = [d0 + one * k for k in range((D - d0).days + 1)]
        # 悬停小卡用的逐日序列：从第一天花钱到 D，消耗、激活、次留
        ser = [(d0 - start).days, [round(f.c[d]) for d in days], [round(f.a[d]) for d in days], [round(f.r[d]) for d in days]]
        out[f.uc].append([ids[:3], idn[ids[0]], f.kind, f.batch.isoformat(), round(sum(f.c.values())), round(a), round(r), round(cb), round(c7), ser])
    for v in out.values():
        v.sort(key=lambda x: -x[4])
    A, Rr = Counter(), Counter()
    for r in rows:
        A[r['d']] += r['a']
        Rr[r['d']] += r['r']
    base = [[round(A[start + one * k]), round(Rr[start + one * k])] for k in range((D - start).days + 1)]
    return dict(U=dict(out), base=base)


def make_roi(rows, fams, spend, D, T, of=None):
    tot = Counter()
    for r in rows:
        tot[r['d']] += r['c']
    lo, hi = D - dt.timedelta(days=7), D - dt.timedelta(days=2)
    W = [f for f in fams if f.first and max(lo, STABLE) <= f.first <= hi]
    n_lo, n_hi = D - dt.timedelta(days=14), D - dt.timedelta(days=1)
    new = [f for f in fams if f.spent and n_lo <= f.batch <= n_hi]
    Wy = [f for f in fams if f.first and max(lo, STABLE) <= f.first <= D - dt.timedelta(days=1)]  # 单条跑量比 W 多算前天首花的这批
    ys = [first_three_est(f, tot, D) for f in Wy]
    rate, cpr = retention(W, D - dt.timedelta(days=1))
    g = dict(y=round(sum(ys) / len(ys)) if ys else 0, hit=round(sum(1 for f in Wy if max(f.c.values()) >= HIT) / len(Wy) * 100, 1) if Wy else 0,
             rate=rate, cpr=cpr, nW=len(Wy), allN=len(new), t0=round((tot[D] + tot[D - dt.timedelta(days=1)]) / 2))
    g['yt'] = {t: dict(n=sum(1 for f in W if f.kind == t), y=round(sum(first_three(f, tot) for f in W if f.kind == t) / max(1, sum(1 for f in W if f.kind == t)))) for t in CURVE}
    groups = defaultdict(list)
    for f in fams:
        groups[f.sub].append(f)
    U = {}
    for u, fs in groups.items():
        batch_fs = [f for f in fs if f in W]
        y_fs = [f for f in fs if f in Wy]
        if not y_fs and not any(f.c[D] + f.c[D - dt.timedelta(days=1)] > 0 for f in fs):
            continue
        U[u] = roi_row(fs, batch_fs, tot, D, T, sum(1 for f in new if f.sub == u), len(new), spend['U'].get(u, [0])[0], spend['t7'], y_fs)
    out = dict(g=g, U=U, rev=recover(fams, tot, D), batch=batches(fams, tot, D), batch_items=batch_items(fams, tot, D), tier=tier_stats(fams, tot, D))
    out['rt'] = rt_diagnose(rows, of, D)
    out['hist'] = history(rows, fams, D)
    out['hist_from'] = min(r['d'] for r in rows).isoformat()
    keys = list(SUB_KEY.values())
    fs = [f for k in keys for f in groups.get(k, [])]
    batch_fs = [f for f in fs if f in W]
    y_fs = [f for f in fs if f in Wy]
    if y_fs:
        c7 = spend['merged']['PS03'][0] if 'merged' in spend else 0
        out['merged'] = {'PS03': roi_row(fs, batch_fs, tot, D, T, sum(1 for f in new if f.sub in keys), len(new), c7, spend['t7'], y_fs)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--today')
    ap.add_argument('--map')
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()
    D = dt.date.fromisoformat(a.date)
    T = dt.date.fromisoformat(a.today) if a.today else D + dt.timedelta(days=1)
    rows = load_rows(a.sheet)
    if not any(r['d'] == D for r in rows):
        print('NO_DATA')
        sys.exit(2)
    rows = [r for r in rows if r['d'] <= D]
    fams, of = families(rows, load_sub_map(a.map))
    if UNMARKED:
        print(f"WARNING PS03 有 {len(UNMARKED)} 条花过钱的素材映射没标子方向，先算接娃和班级群：" + '；'.join(sorted(next(iter(f.names)) for f in UNMARKED)[:5]))
    spend = make_spend(rows, fams, of, D)
    roi = make_roi(rows, fams, spend, D, T, of)
    spend['D'], spend['T_day'] = D.isoformat(), T.isoformat()
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(spend, open(os.path.join(a.out_dir, 'spend.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(roi, open(os.path.join(a.out_dir, 'roi.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps(dict(D=D.isoformat(), T=T.isoformat(), t7=spend['t7'], rate=spend['rate'], cpr=spend['cpr'], g=roi['g'], ucs=len(spend['U'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
