"""从 Use case 库同步细分场景到 tools/scenes.json（Reina 11/9：日报第五节按细分场景看测试覆盖）。

用法：python3 tools/scene_sync.py <'✅ Use case 库'!A1:K200 的 get_values 结果文件>
只取状态「在用」、有 UC_ID 的行；「可包装的场景」里以「数字. 」开头的每一行算一个细分场景，前面不带数字的行是分组名（兴趣、工作、省钱……），「平替角度」那行不算。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    x = json.load(open(sys.argv[1]))
    rows = x['values']
    H = [h.strip() for h in rows[0]]
    c = {k: H.index(k) for k in ('一级分类', 'Use case', 'UC_ID', '状态', '可包装的场景')}
    out = {}
    for r in rows[1:]:
        r = r + [''] * (len(H) - len(r))
        if r[c['状态']].strip() != '在用' or not r[c['UC_ID']].strip():
            continue
        sc, grp = [], ''
        for ln in r[c['可包装的场景']].split('\n'):
            ln = ln.strip()
            m = re.match(r'^(\d+)\.\s*(.+)$', ln)
            if m:
                t = m.group(2)
                sc.append({'n': int(m.group(1)), 't': re.split(r'[：:]', t, maxsplit=1)[0], 'g': grp, 'full': t})
            elif ln and not ln.startswith('平替角度'):
                grp = ln
        out[r[c['UC_ID']].strip()] = {'l1': r[c['一级分类']], 'name': r[c['Use case']].split('：')[0][:20], 'scenes': sc}
    old = json.load(open(os.path.join(HERE, 'scenes.json'))) if os.path.exists(os.path.join(HERE, 'scenes.json')) else {}
    json.dump(out, open(os.path.join(HERE, 'scenes.json'), 'w'), ensure_ascii=False, indent=1)
    ch = [u for u in out if [s['t'] for s in out[u]['scenes']] != [s['t'] for s in old.get(u, {}).get('scenes', [])]]
    print(json.dumps({'uc': len(out), 'scenes': sum(len(v['scenes']) for v in out.values()), 'changed': ch}, ensure_ascii=False))


if __name__ == '__main__':
    main()
