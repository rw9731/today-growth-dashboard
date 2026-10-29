"""List the expanded (扩量) materials worth explaining today, with video links.

Usage:
  python3 tools/kl_list.py /tmp/results.json --sheet <投放数据_分日 dump.json>

Prints JSON: one entry per source material (原素材) whose 扩量 versions spent at least
¥500 on D, top 4 by D spend, skipping sources already written in notes/<date>.json.
Each entry has the 扩量 versions (id, name, video, D spend, 次留率) and the source
versions (id, name, video). Videos come from tools/links.json (唯西日报 first, then 巨量).
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compute import load_rows, base_name, pick_video  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--sheet', required=True)
    a = ap.parse_args()
    res = json.load(open(a.results))
    meta = res['meta'][0]
    th = res['th'][0]
    links = json.load(open(os.path.join(HERE, 'links.json')))
    notes_path = os.path.join(os.path.dirname(HERE), 'notes', meta['date'] + '.json')
    done = json.load(open(notes_path)) if os.path.exists(notes_path) else {}
    names = {}
    for r in load_rows(a.sheet):
        names[r['id']] = r['name']
    fam = {}
    for k in res.get('kl', []):
        if k['cost27'] < th['min']:
            continue
        fam.setdefault(k['src_name'], []).append(k)
    out = []
    for src, ks in sorted(fam.items(), key=lambda kv: -sum(k['cost27'] for k in kv[1]))[:4]:
        if src in done:
            continue
        srcs = ks[0].get('src_ids') or [i for i, n in names.items() if base_name(n) == src]
        out.append({'src_name': src,
                    'kl': [{'id': k['id'], 'name': k['name'], 'video': pick_video(links.get(k['id'], {})),
                            'cost_D': round(k['cost27']), 'rate': k['rate'] and round(k['rate'], 3)} for k in sorted(ks, key=lambda k: -k['cost27'])],
                    'src': [{'id': i, 'name': names.get(i, ''), 'video': pick_video(links.get(i, {}))} for i in srcs]})
    print(json.dumps({'date': meta['date'], 'notes_file': os.path.relpath(notes_path, os.path.dirname(HERE)), 'families': out}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
