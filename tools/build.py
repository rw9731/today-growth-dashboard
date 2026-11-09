"""Build one day's page from results.json and register it in reports.json.

Usage (from the repo root):
  python3 tools/build.py results.json

Writes <date>/index.html, updates reports.json, and rewrites index.html when this
date is the newest report (index.html always shows the latest day).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LABELS = {'T1': '能放量、留存好', 'T2': '量中等、留存好', 'T3': '能放量、留存不达标', 'T0': '量小或没达标，先观察'}


def c3(s):
    """notes 里写的「3 留」统一显示成「连续 3 留」：巨量回传的是 D1、D2、D3 每天都打开，不是第 3 天当天回来。"""
    out, i = [], 0
    for m in re.finditer(r'( ?)3 ?留', s):
        st, sp = m.start(), m.group(1)
        if s[:st].endswith('连续') or (st > 0 and s[st - 1].isdigit() and not sp):
            continue
        prev = s[st - 1] if st > 0 else ''
        out += [s[i:st], ('' if ('\u4e00' <= prev <= '\u9fff' or not sp) else sp) + '连续 3 留']
        i = m.end()
    out.append(s[i:])
    return ''.join(out)


def plain(x):
    """页面上不显示 T1、T2、T3 这些代号，notes 里写了也换成大白话。"""
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [plain(v) for v in x]
    if isinstance(x, str):
        return c3(re.sub(r'(?<![A-Za-z0-9])T[0-3](?![0-9A-Za-z])', lambda m: '「' + LABELS[m.group(0)] + '」', x))
    return x


def render(tpl, res, meta, rel):
    blob = json.dumps(res, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    rep = {'{{D}}': meta['D'], '{{D1}}': meta['D1'], '{{D2}}': meta['D2'], '{{D3}}': meta['D3'], '{{W}}': meta['W'], '{{W3}}': meta.get('W3', '—'),
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
    res['notes'] = [plain(json.load(open(notes_path)))] if os.path.exists(notes_path) else [{}]
    plan_path = os.path.join(ROOT, 'notes', meta['date'] + '-plan.json')
    res['plan'] = [plain(json.load(open(plan_path)))] if os.path.exists(plan_path) else [{}]
    txt = json.dumps([res['notes'], res['plan']], ensure_ascii=False)
    for name in ('爸妈按天气自己重排旅行行程', '计划替你重排', '计划变了就重排'):
        txt = txt.replace(name, '')
    if '重排' in txt:
        print('WARNING notes 里有「重排」：除素材原名和字幕原话外不要写这个词（Reina 11/3）')
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
