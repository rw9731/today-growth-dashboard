"""Refresh the links on an already published day without recomputing the numbers.

Usage:
  python3 tools/relink.py 2026-10-28 [--sheet <投放数据_分日 dump.json>]

With --sheet, also fills the 素材类型 of materials that don't have one yet.

Reads the results embedded in <date>/index.html, fills each material's link from
tools/links.json, and rebuilds the page with tools/build.py (index.html too when it is
the newest day).
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    day = sys.argv[1]
    sheet = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else None
    html = open(os.path.join(ROOT, day, 'index.html')).read()
    blob = re.search(r'<script type="application/json" id="results">(.*?)</script>', html, re.S).group(1)
    res = json.loads(blob.replace('<\\/', '</'))
    links = json.load(open(os.path.join(ROOT, 'tools', 'links.json')))
    n = 0
    if sheet:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        from compute import load_rows, kind_of
        info = {r['id']: r for r in load_rows(sheet)}
        for m in res['mat']:
            if not m.get('kind') and m['id'] in info:
                r = info[m['id']]
                m['kind'] = kind_of(r['src'], r['track'], m['name'])
    for m in res['mat']:
        lk = links.get(m['id'], {})
        ltype = lk.get('type', '')
        video = lk.get('video') or (lk.get('link', '') if ltype == '预览' else '')
        link = '' if ltype == '预览' else lk.get('link', '')
        new = (link, ltype if link else '', video)
        if new != (m.get('link', ''), m.get('link_type', ''), m.get('video', '')):
            m['link'], m['link_type'], m['video'] = new
            n += 1
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(res, f, ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build.py'), f.name], check=True)
    missing = sum(1 for m in res['mat'] if not m.get('video'))
    print(json.dumps({'date': day, 'updated': n, 'still_missing': missing}))


if __name__ == '__main__':
    main()
