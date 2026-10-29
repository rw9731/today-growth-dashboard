"""Build one day's page from results.json and register it in reports.json.

Usage (from the repo root):
  python3 tools/build.py results.json

Writes <date>/index.html, updates reports.json, and rewrites index.html when this
date is the newest report (index.html always shows the latest day).
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(tpl, res, meta, rel):
    blob = json.dumps(res, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    rep = {'{{D}}': meta['D'], '{{D1}}': meta['D1'], '{{D2}}': meta['D2'], '{{D3}}': meta['D3'], '{{W}}': meta['W'],
           '{{T}}': meta['T'], '{{WEEK}}': meta['week'], '{{WEEKDAY}}': meta['weekday'], '{{BUILT}}': meta['built'],
           '{{REL}}': rel, '{{DATE}}': meta['date'], '{{DCN}}': f"{int(meta['date'][5:7])}月{int(meta['date'][8:10])}日",
           '{{RESULTS}}': blob}
    out = tpl
    for k, v in rep.items():
        out = out.replace(k, v)
    assert '{{' not in out.replace(blob, ''), 'unfilled placeholder'
    return out


def main():
    res = json.load(open(sys.argv[1]))
    meta = res['meta'][0]
    notes_path = os.path.join(ROOT, 'notes', meta['date'] + '.json')
    res['notes'] = [json.load(open(notes_path))] if os.path.exists(notes_path) else [{}]
    tpl = open(os.path.join(ROOT, 'tools', 'template.html')).read()
    day_dir = os.path.join(ROOT, meta['date'])
    os.makedirs(day_dir, exist_ok=True)
    open(os.path.join(day_dir, 'index.html'), 'w').write(render(tpl, res, meta, '../'))

    path = os.path.join(ROOT, 'reports.json')
    reports = json.load(open(path)) if os.path.exists(path) else []
    reports = [r for r in reports if r['date'] != meta['date']]
    reports.append({'date': meta['date'], 'label': f"{meta['D']} {meta['weekday']}"})
    reports.sort(key=lambda r: r['date'], reverse=True)
    json.dump(reports, open(path, 'w'), ensure_ascii=False, indent=1)

    latest = reports[0]['date'] == meta['date']
    if latest:
        open(os.path.join(ROOT, 'index.html'), 'w').write(render(tpl, res, meta, './'))
    print(json.dumps({'date': meta['date'], 'latest': latest, 'reports': [r['date'] for r in reports]}))


if __name__ == '__main__':
    main()
