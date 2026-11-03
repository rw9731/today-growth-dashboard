"""Build one week's page from week.json and register it in weeks.json.

Usage (from the repo root):
  python3 tools/build_week.py week.json

Writes week/<Monday>/index.html (reads notes/week-<Monday>.json for the summary and to-dos),
updates weeks.json, and rewrites week/index.html when this is the newest week.
The page reuses the daily page's styles (the <style> block of tools/template.html).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LABELS = {'T1': '能放量、留存好', 'T2': '量中等、留存好', 'T3': '能放量、留存不达标', 'T0': '量小，先观察'}


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


def uc_names(x, names, key=''):
    """notes 正文里的 use case 编号换成名字，第一次看的人才看得懂。uc、tag、id 这几个字段留编号给页面查。"""
    if isinstance(x, dict):
        return {k: uc_names(v, names, k) for k, v in x.items()}
    if isinstance(x, list):
        return [uc_names(v, names) for v in x]
    if isinstance(x, str) and key not in ('uc', 'tag', 'id'):
        return re.sub(r' ?(?<![A-Za-z0-9_])[A-Z]{2}\d{2}(?![0-9A-Za-z]) ?', lambda m: names.get(m.group(0).strip(), m.group(0)), x)
    return x


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


def lint_notes(n):
    """Reina 定的写法，写错就不生成页面，免得发出去才发现。"""
    bad = []
    txt = json.dumps(n, ensure_ascii=False)
    if '不要再加' in txt:
        bad.append('不写「不要再加」，写「差」或「留存差」（公司战略可能还要继续试）')
    # 素材原名照写，其他地方不写这个词（Reina 11/3）
    clean = txt
    for name in ('爸妈按天气自己重排旅行行程', '计划替你重排', '计划变了就重排'):
        clean = clean.replace(name, '')
    if '重排' in clean:
        bad.append('不写「重排」，字幕原话要引用就放「」里并改写成别的说法核对；PS01 叫「早晚报和日程安排」')
    if '放量造成' in txt:
        bad.append('写「放量造成」要有同批素材加量才跌的证据，默认不写')
    for k in ('wk_market', 'wk_top', 'insight', 'rules'):
        for it in n.get(k) or []:
            if len(it.get('t', '')) < 8:
                bad.append(f'{k} 的小标题要是一句结论：{it.get("t")}')
    return bad


def main():
    res = json.load(open(sys.argv[1]))
    meta = res['meta'][0]
    notes_path = os.path.join(ROOT, 'notes', 'week-' + meta['week'] + '.json')
    names = {u['uc']: u['short'] for u in res.get('uc', [])}
    if os.path.exists(notes_path):
        bad = lint_notes(json.load(open(notes_path)))
        if bad:
            sys.exit('notes 不合格：\n' + '\n'.join(bad))
    res['notes'] = [uc_names(plain(json.load(open(notes_path))), names)] if os.path.exists(notes_path) else [{}]
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
