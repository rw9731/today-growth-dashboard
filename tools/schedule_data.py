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
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ONE_DAY = 150000      # 每条产出按全盘一天 ¥15 万折算
HIT = 2000            # 放量：单日 ≥ ¥2,000
ALIVE = 100           # 最近 2 天还在花：日均 ≥ ¥100
RAMP = 200            # 起量日：第一次单日 ≥ ¥200
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
                         a=num(r[col['激活']]), r=num(r[col['次留']]), uc=uc, fuzzy=fuzzy))
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
        f.from_fuzzy = f.from_fuzzy or r['fuzzy']
    for f in fams.values():
        f.batch = min(upload_day(i) for i in f.ids)
        spent = sorted(d for d, v in f.c.items() if v > 0)
        f.first = spent[0] if spent else None
        f.spent = bool(spent)
        f.uc = f.key_uc()
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
    seven = Counter()
    win = defaultdict(lambda: [0.0, 0.0, 0.0])  # 消耗、激活、次留
    d6, d1 = D - dt.timedelta(days=6), D - dt.timedelta(days=1)
    for r in rows:
        f = of[r['id']]
        u = sub_of_row(r, f)
        if r['d'] in idx:
            seg[u][idx[r['d']]][bucket((r['d'] - f.batch).days)] += r['c']
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
    return seg, seven, win, cnt


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
    seg, seven, win, cnt = spend_uc(rows, fams, of, days, D)
    n = len(days)
    t = [[sum(seg[u][i][j] for u in seg) for j in range(4)] for i in range(n)]
    tw = [sum(win[u][k] for u in win) for k in range(3)]
    tn = [sum(cnt[u][i] for u in cnt) for i in range(n)]
    us = sorted(set(seg) | set(seven) | set(win) | set(cnt), key=lambda u: -seven[u])
    out = dict(days=[d.strftime('%m-%d') for d in days], t7=round(sum(seven.values())), rate=pct(tw[2], tw[1]), cpr=cost_per(tw[0], tw[2]),
               T=dict(s=';'.join(enc_day(x) for x in t), n=','.join(str(x) for x in tn)),
               U={u: spend_row(u, seg, seven, win, cnt, n) for u in us})
    keys = list(SUB_KEY.values())
    if any(k in out['U'] for k in keys):
        w = [sum(win[k][i] for k in keys) for i in range(3)]
        c = [sum(cnt[k][i] for k in keys) for i in range(n)]
        s = merge_seg(seg, keys, n)
        out['merged'] = {'PS03': [round(sum(seven[k] for k in keys)), pct(w[2], w[1]), cost_per(w[0], w[2]), int(w[1]),
                                  ','.join(str(x) for x in c), ';'.join(enc_day(x) for x in s)]}
    return out


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


def roi_row(fs, batch_fs, tot, D, T, new14, total_new, c7, c7_total):
    ys = sorted(first_three(f, tot) for f in batch_fs)
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
    n01 = sum(1 for f in fs if f.first and f.first >= D - dt.timedelta(days=1) and f.c[D] + f.c[d1] > 0)  # 第 0–1 天已上线、还在起量
    win = lambda a, b: sum(f.c[D - dt.timedelta(days=k)] for f in fs for k in range(a, b + 1))
    tw = lambda a, b: sum(tot.get(D - dt.timedelta(days=k), 0) for k in range(a, b + 1))
    mom = (win(0, 2) / tw(0, 2) - win(3, 5) / tw(3, 5)) * 100 if tw(0, 2) and tw(3, 5) else 0  # 最近 3 天占比减前 3 天占比
    return dict(n14=new14, n=n, y=round(s / n), yx=round((s - ys[-1]) / (n - 1)) if n > 1 else 0, top=round(ys[-1] / s, 2) if s else 0,
                hit=sum(1 for f in batch_fs if max(f.c.values()) >= HIT), rate=rate, cpr=cpr,
                sh=round(c7 / c7_total * 100, 1) if c7_total else 0, np=round(new14 / total_new * 100, 1) if total_new else 0,
                mom=round(mom, 1), lvl=round(lvl), R=round(R), Dn=round(lvl) - round(R), n01=n01, chips={k: round(v) for k, v in sorted(chips.items())})


def make_roi(rows, fams, spend, D, T):
    tot = Counter()
    for r in rows:
        tot[r['d']] += r['c']
    lo, hi = D - dt.timedelta(days=7), D - dt.timedelta(days=2)
    W = [f for f in fams if f.first and lo <= f.first <= hi]
    n_lo, n_hi = D - dt.timedelta(days=14), D - dt.timedelta(days=1)
    new = [f for f in fams if f.spent and n_lo <= f.batch <= n_hi]
    ys = [first_three(f, tot) for f in W]
    rate, cpr = retention(W, D - dt.timedelta(days=1))
    g = dict(y=round(sum(ys) / len(ys)) if ys else 0, hit=round(sum(1 for f in W if max(f.c.values()) >= HIT) / len(W) * 100, 1) if W else 0,
             rate=rate, cpr=cpr, nW=len(W), allN=len(new))
    groups = defaultdict(list)
    for f in fams:
        groups[f.sub].append(f)
    U = {}
    for u, fs in groups.items():
        batch_fs = [f for f in fs if f in W]
        if not batch_fs:
            continue
        U[u] = roi_row(fs, batch_fs, tot, D, T, sum(1 for f in new if f.sub == u), len(new), spend['U'].get(u, [0])[0], spend['t7'])
    out = dict(g=g, U=U)
    keys = list(SUB_KEY.values())
    fs = [f for k in keys for f in groups.get(k, [])]
    batch_fs = [f for f in fs if f in W]
    if batch_fs:
        c7 = spend['merged']['PS03'][0] if 'merged' in spend else 0
        out['merged'] = {'PS03': roi_row(fs, batch_fs, tot, D, T, sum(1 for f in new if f.sub in keys), len(new), c7, spend['t7'])}
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
    roi = make_roi(rows, fams, spend, D, T)
    spend['D'], spend['T_day'] = D.isoformat(), T.isoformat()
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(spend, open(os.path.join(a.out_dir, 'spend.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(roi, open(os.path.join(a.out_dir, 'roi.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps(dict(D=D.isoformat(), T=T.isoformat(), t7=spend['t7'], rate=spend['rate'], cpr=spend['cpr'], g=roi['g'], ucs=len(spend['U'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
