"""Add 「五、昨天上新的素材（按上传日期）」 and the left TOC to an already published daily page (Reina 11/9).

Usage:
  python3 tools/backfill_newd.py <date> <compute 输出的 results.json>

Takes the results embedded in <date>/index.html and only replaces newd / newd_meta with the ones from the given
results.json (compute.py --date <date>, which reads notes/uploads-<date>.json). Every other number on the page stays as
it was published. Old wording 「上线」 in the opening summary is changed to 「首次消耗」 so the two dates read clearly.
Then re-renders the page with the current template through build.py.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    day, src = sys.argv[1], sys.argv[2]
    html = open(os.path.join(ROOT, day, 'index.html')).read()
    blob = re.search(r'<script type="application/json" id="results">(.*?)</script>', html, re.S).group(1)
    res = json.loads(blob.replace('<\\/', '</'))
    new = json.load(open(src))
    assert new['meta'][0]['date'] == day, 'results.json is for another day'
    res['newd'] = new['newd']
    res['newd_meta'] = new.get('newd_meta') or [{}]
    meta = res['meta'][0]
    t = meta.get('take', '')
    t = t.replace('上线的新素材昨天占消耗的', '首次消耗的素材昨天占消耗的').replace(' 上线那批次留率', ' 首次消耗那批次留率')
    t = re.sub(r'，主要是 (\d+/\d+) 刚上的', r'，主要是 \1 首次消耗的', t)
    meta['take'] = t
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(res, f, ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build.py'), f.name], check=True)
    nolink = sum(1 for m in res['newd'] if not m.get('video') and not m.get('link'))
    print(json.dumps({'date': day, 'newd': len(res['newd']), 'spent': sum(1 for m in res['newd'] if m.get('first')), 'no_link': nolink}))


if __name__ == '__main__':
    main()
