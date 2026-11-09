"""列出日报第五节里还没打细分场景的素材（Reina 11/9）。

用法：python3 tools/scene_todo.py /tmp/results.json --out /tmp/scene_todo.json
范围：results 里 newd 和 ramp_mats 的素材，notes/scene-map.json 里没有的，以及标了「待看片」、现在 scripts/ 里有了字幕的。
输出按 UC 分组：{UC: {"scenes": [{"n", "t"}], "mats": [{"id", "name", "hook", "lines", "demo", "sibling_scripts"}]}}，
sibling_scripts 是同一条原片其他版本的字幕（二创、扩量通常只换开头）。打完标用 scene_merge.py 合并。
"""
import argparse, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def theme(n):
    n = re.sub(r'^推送视频_', '', n.strip())
    n = re.sub(r'\s*\(\d+\)$', '', n)
    n = re.split(r'[_-](二创|扩量|精剪|精简|混剪|合规修改)', n)[0]
    n = re.sub(r'[_-]20\d{6}$', '', n)
    return re.sub(r'(\s改|_\d+)$', '', n)


def brief(s):
    ln = s.get('lines') or []
    if isinstance(ln, list):
        ln = ' / '.join(x if isinstance(x, str) else (x.get('t') or x.get('text') or '') for x in ln)
    return {'hook': s.get('hook', ''), 'demo': str(s.get('demo', ''))[:200], 'lines': str(ln)[:400]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    R = json.load(open(a.results))
    SC = json.load(open(os.path.join(HERE, 'scenes.json')))
    p = os.path.join(ROOT, 'notes', 'scene-map.json')
    SM = json.load(open(p)) if os.path.exists(p) else {}
    lib = {}
    for f in glob.glob(os.path.join(ROOT, 'scripts', '*.json')):
        try:
            s = json.load(open(f))
        except Exception:
            continue
        lib.setdefault(theme(s.get('name', '')), []).append(s)
    ms = {}
    for k in ('newd', 'ramp_mats'):
        for m in R.get(k) or []:
            ms.setdefault(m['id'], m)
    out, n = {}, 0
    for i, m in ms.items():
        t = SM.get(i)
        own = os.path.exists(os.path.join(ROOT, 'scripts', i + '.json'))
        if t and not (t.get('st') == 'tbd' and own and t.get('by') != 'script'):
            continue
        uc = m.get('uc') or '待对应'
        e = {'id': i, 'name': m['name']}
        if own:
            e.update(brief(json.load(open(os.path.join(ROOT, 'scripts', i + '.json')))))
        else:
            sib = [s for s in lib.get(theme(m['name']), []) if s.get('id') != i][:2]
            if sib:
                e['sibling_scripts'] = [dict(name=s.get('name'), **brief(s)) for s in sib]
        g = out.setdefault(uc, {'scenes': [{'n': s['n'], 't': s['full']} for s in SC.get(uc, {}).get('scenes', [])], 'mats': []})
        g['mats'].append(e)
        n += 1
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=0)
    print(json.dumps({'todo': n, 'uc': len(out), 'mapped': len(SM)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
