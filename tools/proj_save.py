"""新素材建进了多少项目、项目里是怎么分钱的（Reina 11/11，回答「每天新素材建了多少计划、给了多少测试预算」）。

数据：巨量广告智擎版 std/projects/list（D-9 到 D 有记录的项目，创建时间、预算、出价）+ std/promotion/materials/list（每个项目里每条素材这段时间的消耗）。
在投放管理页用 javascript_tool 跑查询（只调查询接口，不点按钮），结果整理成 JSON 列表 [{adv, pid, ct, name, budget, bid, dbid, st, cost, mats: [[素材ID, 消耗], ...]}] 后：
python3 tools/proj_save.py --date D 项目文件.json → notes/proj-D.json，compute.py 读它写进冷启结论。
普通户（非智擎）没有算进来。
"""
import argparse, collections, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--date', required=True)
ap.add_argument('src')
a = ap.parse_args()
P = json.load(open(a.src))
inp = collections.defaultdict(list)
for p in P:
    for m, c in p['mats']:
        inp[m].append(c)
per_day = {}
for m, cs in inp.items():
    u = compute.up_day(m)
    if u:
        per_day.setdefault(u, []).append(len(cs))
nm = [len(p['mats']) for p in P if p['mats']]
top = [max(c for _, c in p['mats']) / sum(c for _, c in p['mats']) for p in P if p['mats'] and sum(c for _, c in p['mats']) > 0]
pairs = sum(len(p['mats']) for p in P)
zero = sum(1 for p in P for _, c in p['mats'] if c <= 0)
bud = collections.Counter((p['budget'], p['bid']) for p in P).most_common(3)
out = {'date': a.date, 'source': '巨量广告智擎版 std/projects/list + std/promotion/materials/list，普通户不在内',
       'n_proj': len(P), 'mats_per_proj_med': st.median(nm) if nm else None, 'top1_share_med': round(st.median(top), 2) if top else None,
       'zero_pair_share': round(zero / pairs, 3) if pairs else None,
       'proj_per_mat': {u: [st.median(v), len(v)] for u, v in sorted(per_day.items())},
       'budget_bid': [[b, bid, n] for (b, bid), n in bud]}
# 明细：给 compute.py 按上传日拆「没拿到量的素材为什么没拿到」用。projects = [项目ID, 素材数, [[有消耗的素材ID, 消耗], ...]]；
# mat_proj = 最近 14 天上传的素材 → 它在哪些项目里（projects 的下标）
d0 = (compute.dt.date.fromisoformat(a.date) - compute.dt.timedelta(days=14)).isoformat()
out['projects'] = [[p['pid'], len(p['mats']), [[m, round(c, 2)] for m, c in p['mats'] if c > 0]] for p in P]
mp = collections.defaultdict(list)
for k, p in enumerate(P):
    for m, _ in p['mats']:
        if compute.up_day(m) >= d0:
            mp[m].append(k)
out['mat_proj'] = mp
p_ = os.path.join(os.path.dirname(HERE), 'notes', f'proj-{a.date}.json')
json.dump(out, open(p_, 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps({k: v for k, v in out.items() if k not in ('proj_per_mat', 'projects', 'mat_proj')}, ensure_ascii=False))
