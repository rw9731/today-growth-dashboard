"""前天上传的这批素材，第二天红了、绿了的，列出来去看内容。Reina 11/5 定：每天都要看具体内容，红的分析为什么没跑起来，绿的分析好在哪。

Usage:
  python3 tools/schedule_why.py --sheet <分日文件> --map <素材映射文件> --date D --out /tmp/sched/why

写 /tmp/sched/why/context.json：每个红、绿的方向（3 条以上）这批的素材、根素材之前上过多少条、这个方向最近跑起来的素材（用来比）；
写 /tmp/sched/why/todo.json 和 jl.js：其中还没有脚本的素材，按 RUN.md「读全片脚本」读，存进 scripts/。
读完写 notes/schedule-<T>.json（格式见 RUN.md），schedule_build.py 读它放进页面。
"""
import argparse, json, os, re, sys
import datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schedule_data as S  # noqa: E402
import scripts_lib  # noqa: E402
from jl_js import JS, PAGE  # noqa: E402

CAP = 20  # 一天最多读这么多条
HI, LO = .4, .15  # 和页面标色一样


def name(f):
    return min((n for n in f.names if not n.startswith('推送视频_')), key=len, default=next(iter(f.names)))


def root(f):
    """根素材：去掉扩量和二创后缀。同一条根素材改出来的算一家。"""
    n = name(f).replace('推送视频_', '')
    n = re.split(r'[_-]扩量', n)[0]
    return re.split(r'_二创', n)[0] if f.kind == '二创' else n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--map')
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    D = dt.date.fromisoformat(a.date)
    one = dt.timedelta(days=1)
    day = D - one
    rows = [r for r in S.load_rows(a.sheet) if r['d'] <= D]
    fams, _ = S.families(rows, S.load_sub_map(a.map))
    fams = [f for f in fams if f.first and f.spent]
    tot = defaultdict(float)
    for r in rows:
        tot[r['d']] += r['c']
    avg = S.day_avg(fams, tot)
    up = lambda f: S.is_up(f, avg, D)
    scr = scripts_lib.load()
    has = lambda f: any(i in scr for i in f.ids)
    roots = defaultdict(list)
    for f in fams:
        roots[root(f)].append(f)
    part = {v: k for k, v in S.SUB_KEY.items()}
    stat = lambda f: (lambda c, x, y: dict(cost=round(c), act=round(x), rate=round(y / x * 100, 1) if x else None, cpr=round(c / y) if y else None))(
        sum(v for k, v in f.c.items() if k < D), sum(v for k, v in f.a.items() if k < D), sum(v for k, v in f.r.items() if k < D))
    def brief(f):
        r = root(f)
        earlier = [g for g in roots[r] if g.batch < f.batch]
        return dict(id=sorted(f.ids)[0], name=name(f), kind=f.kind, up=up(f), c0=round(f.c[f.first]), c1=round(f.c[f.first + one]), expansion='扩量' in name(f), root=r,
                    root_before=len(earlier), root_before_cost=round(sum(sum(g.c.values()) for g in earlier)), stat=stat(f), script=has(f))
    by = defaultdict(list)
    for f in fams:
        if f.batch == day:
            by[f.sub].append(f)
    out, todo = [], []
    want = lambda f, why: todo.append((f, why)) if not has(f) else None
    for u, fs in by.items():
        n, k = len(fs), sum(1 for f in fs if up(f))
        if n < 3:
            continue
        color = 'green' if k / n >= HI else 'red' if k / n < LO else ''
        if not color:
            continue
        cost = sum(f.c[day + one] for f in fs)
        recent = sorted([f for f in fams if f.sub == u and D - one * 8 <= f.batch < day and up(f)], key=lambda f: -sum(f.c.values()))[:3]
        out.append(dict(u=u, part=part.get(u), color=color, n=n, k=k, per=round(cost / n), avg=round(avg.get(day + one, 0)), pieces=[brief(f) for f in sorted(fs, key=lambda f: -f.c[day + one])], recent=[brief(f) for f in recent]))
    # 先看第一档的红，再看第二档，探索排最后。条数有上限，要先保住放量方向
    plan = json.load(open(os.path.join(HERE, 'schedule_plan.json'), encoding='utf-8'))
    rank = {}
    for i, g in enumerate(plan['GROUPS']):
        for u in g[1]:
            rank[u] = i
    tier = lambda u: 0 if u in S.SUB_KEY.values() else rank.get(u, 2)
    out.sort(key=lambda x: (tier(x['u']), x['color'] != 'red', -x['n']))
    by_id = {sorted(f.ids)[0]: f for f in fams}
    for x in out:
        ordered = [by_id[p['id']] for p in x['pieces']]
        for f in (ordered[:2] + ordered[-1:] if x['color'] == 'red' else [f for f in ordered if up(f)][:3]):
            want(f, x['color'])
        for p in x['recent'][:2]:
            want(by_id[p['id']], '比较')
    os.makedirs(a.out, exist_ok=True)
    json.dump(dict(day=day.strftime('%m-%d'), avg=round(avg.get(day + one, 0)), rows=out), open(os.path.join(a.out, 'context.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    seen, need = set(), []
    for f, why in todo:
        if id(f) not in seen:
            seen.add(id(f))
            need.append(dict(id=sorted(f.ids)[0], name=name(f), why=why))
    need = need[:CAP]
    json.dump(need, open(os.path.join(a.out, 'todo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    hubs = json.load(open(os.path.join(HERE, 'jl_hubs.json')))
    start = (D - dt.timedelta(days=60)).isoformat()
    open(os.path.join(a.out, 'jl.js'), 'w').write(f'// 在这个页面跑（要已登录巨量）：{PAGE}\n' + JS % (json.dumps([x['id'] for x in need]), json.dumps(hubs), json.dumps(start)))
    print(json.dumps(dict(day=day.isoformat(), red=[x['u'] for x in out if x['color'] == 'red'], green=[x['u'] for x in out if x['color'] == 'green'], read=len(need)), ensure_ascii=False))


if __name__ == '__main__':
    main()
