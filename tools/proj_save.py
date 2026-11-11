"""冷启的项目数据存成 notes/proj-D.json（Reina 11/11，回答「新素材建了多少计划、新建项目有没有起量」）。

用法：python3 tools/proj_save.py --date D /tmp/linkjs/proj_*.json
输入是 tools/proj_js.py 生成的 proj.js 的 __pjGet(k) 返回值（{date, k, d}，d 是一行一个项目，\\t 分隔，见 proj_js.py 文件头）。
也接受 11/11 手工拉的旧格式：一个 JSON 列表 [{adv, pid, ct, name, budget, bid, dbid, st, cost, mats: [[素材ID, 消耗], ...]}]。
compute.py 读 notes/proj-D.json，在冷启共性问题和每天面板里写「新建项目有多少没起量、项目里塞了多少素材」。普通户不在内。
"""
import argparse, collections, datetime as dt, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute  # noqa: E402


def load(p):
    x = json.loads(open(p).read().strip())
    return json.loads(x) if isinstance(x, str) else x


def read(paths, date):
    """统一成 [{pid, ct, budget, bid, n, spent: [[m, c]], recent: [m]}]。"""
    P = []
    d14 = (dt.date.fromisoformat(date) - dt.timedelta(days=14)).isoformat()
    for p in paths:
        x = load(p)
        if isinstance(x, list):  # 旧格式
            for q in x:
                P.append({'pid': q['pid'], 'ct': q['ct'], 'budget': q['budget'], 'bid': q['bid'], 'n': len(q['mats']),
                          'spent': [[m, c] for m, c in q['mats'] if c > 0], 'recent': [m for m, _ in q['mats'] if compute.up_day(m) >= d14]})
            continue
        if x.get('date') != date:
            raise SystemExit(f"日期对不上：{p} 是 {x.get('date')}，参数是 {date}")
        for line in (x.get('d') or '').split('\n'):
            f = line.split('\t')
            if len(f) < 12:
                continue
            sp = [[m, float(c)] for m, c in (s.rsplit(':', 1) for s in f[10].split('|') if s)]
            P.append({'pid': f[1], 'ct': f[2], 'budget': f[4], 'bid': f[5], 'n': int(f[9] or 0), 'spent': sp, 'recent': [m for m in f[11].split('|') if m]})
    seen, out = set(), []
    for q in P:  # 同一项目分段时可能重复
        if q['pid'] not in seen:
            seen.add(q['pid'])
            out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('src', nargs='+')
    a = ap.parse_args()
    P = read(a.src, a.date)
    if not P:
        raise SystemExit('没有读到项目')
    per_day = collections.defaultdict(list)
    cnt = collections.Counter()
    for p in P:
        for m in p['recent']:
            cnt[m] += 1
    for m, n in cnt.items():
        per_day[compute.up_day(m)].append(n)
    nm = [p['n'] for p in P if p['n']]
    top = [max(c for _, c in p['spent']) / sum(c for _, c in p['spent']) for p in P if p['spent']]
    pairs = sum(p['n'] for p in P)
    spent_pairs = sum(len(p['spent']) for p in P)
    bud = collections.Counter((p['budget'], p['bid']) for p in P).most_common(3)
    out = {'date': a.date, 'source': '巨量广告智擎版 std/projects/list + std/promotion/materials/list，普通户不在内',
           'n_proj': len(P), 'mats_per_proj_med': st.median(nm) if nm else None, 'top1_share_med': round(st.median(top), 2) if top else None,
           'zero_pair_share': round(1 - spent_pairs / pairs, 3) if pairs else None,
           'proj_per_mat': {u: [st.median(v), len(v)] for u, v in sorted(per_day.items())},
           'budget_bid': [[b, bid, n] for (b, bid), n in bud]}
    # 新建项目有没有起量（Reina 11/11，回应 Xuhan：新素材一般推到没有高热素材的项目里）。
    # 干净项目 = 项目里没有一条比项目创建日更早上传的素材在这段时间花到 ¥1,000；只看 D-8 到 D-1 建的项目。
    d = dt.date.fromisoformat(a.date)
    c0, c1 = (d - dt.timedelta(days=8)).isoformat(), (d - dt.timedelta(days=1)).isoformat()
    cl, ht = [], []
    for p in P:
        ct = (p.get('ct') or '')[:10]
        if not (c0 <= ct <= c1):
            continue
        tot = sum(c for _, c in p['spent'])
        hot = any(c >= 1000 and compute.up_day(m) < ct for m, c in p['spent'])
        (ht if hot else cl).append((tot, p['n'], sum(1 for m in p['recent'] if compute.up_day(m) >= ct)))
    k80 = []
    for p in P:
        cs = sorted((c for _, c in p['spent']), reverse=True)
        t = sum(cs)
        if t >= 500:
            acc = 0
            for j, c in enumerate(cs):
                acc += c
                if acc >= 0.8 * t:
                    k80.append(j + 1)
                    break
    out['new_proj'] = {'from': c0, 'to': c1, 'clean_n': len(cl), 'clean_lt100': sum(1 for x in cl if x[0] < 100),
                       'clean_med': round(st.median([x[0] for x in cl])) if cl else None, 'clean_tot': round(sum(x[0] for x in cl)),
                       'clean_mats_med': st.median([x[1] for x in cl]) if cl else None, 'clean_new_med': st.median([x[2] for x in cl]) if cl else None,
                       'hot_n': len(ht), 'hot_tot': round(sum(x[0] for x in ht)), 'k80_n': len(k80), 'k80_med': st.median(k80) if k80 else None}
    # 明细：给 compute.py 按上传日拆「没拿到量的素材为什么没拿到」用。projects = [项目ID, 素材数, [[有消耗的素材ID, 消耗], ...]]；
    # mat_proj = 最近 14 天上传的素材 → 它在哪些项目里（projects 的下标）
    out['projects'] = [[p['pid'], p['n'], [[m, round(c, 2)] for m, c in p['spent']]] for p in P]
    mp = collections.defaultdict(list)
    for k, p in enumerate(P):
        for m in p['recent']:
            mp[m].append(k)
    out['mat_proj'] = mp
    pth = os.path.join(os.path.dirname(HERE), 'notes', f'proj-{a.date}.json')
    json.dump(out, open(pth, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({k: v for k, v in out.items() if k not in ('proj_per_mat', 'projects', 'mat_proj')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
