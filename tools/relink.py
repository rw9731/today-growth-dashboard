"""Refresh the links on an already published day without recomputing the numbers.

Usage:
  python3 tools/relink.py 2026-10-28

Reads the results embedded in <date>/index.html, fills each material's link from
tools/links.json, and rebuilds the page with tools/build.py (index.html too when it is
the newest day).
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    day = sys.argv[1]
    html = open(os.path.join(ROOT, day, 'index.html')).read()
    blob = re.search(r'<script type="application/json" id="results">(.*?)</script>', html, re.S).group(1)
    res = json.loads(blob.replace('<\\/', '</'))
    links = json.load(open(os.path.join(ROOT, 'tools', 'links.json')))
    n = 0
    for m in res['mat']:
        lk = links.get(m['id'])
        if lk and (lk['link'], lk['type']) != (m.get('link'), m.get('link_type')):
            m['link'], m['link_type'] = lk['link'], lk['type']
            n += 1
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(res, f, ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build.py'), f.name], check=True)
    missing = sum(1 for m in res['mat'] if not m.get('link'))
    print(json.dumps({'date': day, 'updated': n, 'still_missing': missing}))


if __name__ == '__main__':
    main()
