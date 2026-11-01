"""Build one week's page from week.json and register it in weeks.json.

Usage (from the repo root):
  python3 tools/build_week.py week.json

Writes week/<Monday>/index.html (reads notes/week-<Monday>.json for the summary and to-dos),
updates weeks.json, and rewrites week/index.html when this is the newest week.
The page reuses the daily page's styles (the <style> block of tools/template.html).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(tpl, style, res, meta, rel):
    blob = json.dumps(res, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    rep = {'{{STYLE}}': style, '{{LABEL}}': meta['label'], '{{PLABEL}}': meta['p_label'], '{{WEEK}}': meta['week'],
           '{{WRET}}': meta['w_ret'], '{{WRET3}}': meta['w_ret3'], '{{BUILT}}': meta['built'], '{{REL}}': rel,
           '{{RESULTS}}': blob}
    out = tpl
    for k, v in rep.items():
        out = out.replace(k, v)
    assert '{{' not in out.replace(blob, ''), 'unfilled placeholder'
    return out


def main():
    res = json.load(open(sys.argv[1]))
    meta = res['meta'][0]
    notes_path = os.path.join(ROOT, 'notes', 'week-' + meta['week'] + '.json')
    res['notes'] = [json.load(open(notes_path))] if os.path.exists(notes_path) else [{}]
    daily = open(os.path.join(ROOT, 'tools', 'template.html')).read()
    style = re.search(r'<style>\n(.*?)</style>', daily, re.S).group(1)
    tpl = open(os.path.join(ROOT, 'tools', 'week_template.html')).read()
    d = os.path.join(ROOT, 'week', meta['week'])
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'index.html'), 'w').write(render(tpl, style, res, meta, '../../'))

    path = os.path.join(ROOT, 'weeks.json')
    weeks = json.load(open(path)) if os.path.exists(path) else []
    weeks = [w for w in weeks if w['week'] != meta['week']] + [{'week': meta['week'], 'label': meta['label']}]
    weeks.sort(key=lambda w: w['week'], reverse=True)
    json.dump(weeks, open(path, 'w'), ensure_ascii=False, indent=1)
    latest = weeks[0]['week'] == meta['week']
    if latest:
        open(os.path.join(ROOT, 'week', 'index.html'), 'w').write(render(tpl, style, res, meta, '../'))
    print(json.dumps({'week': meta['week'], 'latest': latest, 'weeks': [w['week'] for w in weeks]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
