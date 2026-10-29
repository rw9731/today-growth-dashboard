"""List the 二剪 materials whose 改法 still has to be checked (subtitle comparison), with videos.

Usage:
  python3 tools/gaifa_list.py /tmp/results.json --sheet <投放数据_分日 dump.json>

A material is listed when its D spend is at least ¥500, it is a KOC/KOL 二剪 (二创 or 扩量 in
the name, or an AI 扩量), and tools/gaifa.json has no entry for it. Each entry carries the
material's video and its parent: for 扩量 the material it was cut from, for a first 二剪 the
达人原片 (only findable when that 原片 itself ran as an ad). Videos come from tools/links.json;
ids without one are in "need_video" (jl_js.py --sheet adds them to jl.js).
After comparing, write {id: {"gaifa": ..., "checked": date, "note": ...}} into tools/gaifa.json.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compute import load_rows, base_name, parent_of, pick_video, GAIFA  # noqa: E402

MIN = 500


def todo(res, sheet):
    rows = load_rows(sheet)
    names, spend, src = {}, {}, {}
    for r in rows:
        names[r['id']] = r['name'] or names.get(r['id'], '')
        spend[r['id']] = spend.get(r['id'], 0) + r['cost']
        src.setdefault(r['id'], (r.get('src') or '', r.get('track') or ''))
    by_base = {}
    for i, n in names.items():
        by_base.setdefault(base_name(n), []).append(i)
    D = res['meta'][0]['date']
    d_cost = {}
    for r in rows:
        if r['date'] == D:
            d_cost[r['id']] = d_cost.get(r['id'], 0) + r['cost']
    links = json.load(open(os.path.join(HERE, 'links.json')))
    out = []
    for i, c in sorted(d_cost.items(), key=lambda x: -x[1]):
        if c < MIN or i in GAIFA:
            continue
        n = names.get(i, '')
        s, track = src.get(i, ('', ''))
        ai = s == 'AIGC' or 'AI短剧' in track
        if ai and '扩量' not in n:
            continue
        if not ai and not ('二创' in n or '二创' in track or '扩量' in n):
            continue
        par = parent_of(n) if '扩量' in n else re.split(r'[_-]二创', base_name(n))[0]
        cand = [p for p in by_base.get(par, []) if p != i]
        pid = max(cand, key=lambda p: spend.get(p, 0)) if cand else ''
        out.append({'id': i, 'name': n, 'cost_D': round(c), 'video': pick_video(links.get(i, {})),
                    'parent_id': pid, 'parent_name': names.get(pid, par), 'parent_video': pick_video(links.get(pid, {})) if pid else ''})
    need = sorted({x['id'] for x in out if not x['video']} | {x['parent_id'] for x in out if x['parent_id'] and not x['parent_video']})
    return out, need


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--sheet', required=True)
    a = ap.parse_args()
    out, need = todo(json.load(open(a.results)), a.sheet)
    print(json.dumps({'todo': out, 'need_video': need}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
