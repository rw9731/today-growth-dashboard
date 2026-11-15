"""把 tools/plan_uc_read.js 读出的 6 个 tab（/tmp/h/plan_<tab>.json）合成 notes/plan_uc.json。
- 先按 notes/plan_fix.json 改掉排期表里填错、没跟着拆分改的 UC（Reina 11/15：以排期表为准）。
- 「原素材（照着改）」「视频/原素材名称」列里的是参照的原片，不是这一行出的片，不进 map（否则原片会被记成这一行的 UC）。
  需要 tools/plan_audit_read.js 的读数（/tmp/h/aud_<tab>.json）来认出原素材列的文字。
用法：python3 tools/plan_build.py [/tmp/h]
"""
import json, os, re, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from uc_resolve import norm_name
D = sys.argv[1] if len(sys.argv) > 1 else '/tmp/h'
TABS = ['kMJdAv', 'f18d7b', 'nPw5Dc', 'c665d9', 'EnYgPG', '3KtioB']
fix = json.load(open(os.path.join(ROOT, 'notes', 'plan_fix.json'), encoding='utf-8'))
m = defaultdict(set); src = defaultdict(list); fixed = 0; dropped = 0
for t in TABS:
    p = json.load(open(f'{D}/plan_{t}.json', encoding='utf-8'))
    orig = {}
    ap = f'{D}/aud_{t}.json'
    if os.path.exists(ap):
        a = json.load(open(ap, encoding='utf-8'))
        oc = [i for i, c in enumerate(a['cols']) if '原素材' in c[1] and '命名' not in c[1]]
        ok_ = [i for i, c in enumerate(a['cols']) if i not in oc]
        for r, uc, vals in a['rows']:
            orig[r] = (' '.join(vals[i] for i in oc), ' '.join(vals[i] for i in ok_ if '成片' in a['cols'][i][1] or '扩量素材名' in a['cols'][i][1] or '命名' in a['cols'][i][1]))
    for r, uc, names in p['rows']:
        f = fix.get(t, {}).get(str(r))
        if f and f[0] != uc:
            uc = f[0]; fixed += 1
        for n in names:
            if n.startswith('【') or re.search(r'命名后面|字幕|需修改|^\d+\.', n):
                continue
            o = orig.get(r)
            if o and n in o[0] and n not in o[1]:
                dropped += 1; continue
            k = norm_name(n)
            m[k].add(uc); src[k].append(f'{t}:{r}')
out = {'_note': '唯西排期表、成片表（A 组 kMJdAv f18d7b nPw5Dc，B 组 c665d9 EnYgPG 3KtioB）素材名 → UC，已按 notes/plan_fix.json 改过；tools/plan_build.py 生成', 'read': '2026-11-15',
       'map': {k: sorted(v) for k, v in m.items()}, 'src': {k: v for k, v in src.items()}}
json.dump(out, open(os.path.join(ROOT, 'notes', 'plan_uc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
multi = {k: sorted(v) for k, v in m.items() if len(v) > 1}
print(json.dumps({'names': len(m), 'fixed_rows': fixed, 'dropped_orig_names': dropped, 'multi': len(multi)}, ensure_ascii=False))
for k, v in list(multi.items())[:40]:
    print(v, src[k][:4], k[:90])
