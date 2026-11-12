"""排期数据对表：把 schedule_plan.json 里这周的排期条目（E）和飞书扩量排期表对齐（Reina 11/12：飞书排期改了，关联的数据要一起改）。

  python3 tools/plan_sync.py --dir /tmp/sync --date T [--apply]

--dir 里是 tools/plan_rows_read.js 在 A 组 kMJdAv、B 组 3KtioB 跑出来的 kMJdAv.json、3KtioB.json。
不加 --apply 只打印差异；加了才写回 tools/schedule_plan.json（asof 改成 T）。

范围：plan 的 week 那周（周一到周日）和「下周」（记成下周一）。表里每一行有 UC_ID 和条数的算一条：
- E 里已有这一行（src 写「X 组扩量第 N 行」）：UC、条数、AI/二创有一项不同就按表重写这一条；都一样只同步日期（本周开头那块之前的老行不动日期，它们在 E 里常写成提前或顺延后的日子）。
- E 里没有这一行、日期在这周或下周：按表新加。
- E 里有、表里这一行已经没有 UC 或条数：删掉。
不碰 E 里不是扩量排期行的条目（比如「脚本及成片」那种），不碰别的周。
"""
import argparse, datetime as dt, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABS = {'A': 'kMJdAv', 'B': '3KtioB'}
LINK = {'A': 'https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc?sheet=kMJdAv',
        'B': 'https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb?sheet=3KtioB'}
SRC = re.compile(r'^([AB]) 组扩量第 (\d+) 行')


def parse_day(s, year, nxt):
    s = (s or '').strip()
    if s.startswith('下周'):
        return nxt
    m = re.match(r'(\d{1,2})\s*[/月.]\s*(\d{1,2})', s)
    if not m:
        return None
    try:
        return dt.date(year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def kind(x):
    t = x.get('t') or ''
    if '二创' in t or 'KOC' in t or 'KOL' in t:
        return '二创'
    if 'AI' in t:
        return 'AI'
    return '二创' if re.search(r'【二创|重配】|二剪', x.get('how') or '') else 'AI'


def entry(g, x, d, old=None):
    how = re.sub(r'^(【[^】]*】\s*)+', '', x.get('how') or '').strip()
    k = '自己发挥' if x['uc'] == '自选' else ('变式' if '头部模板' in (x.get('basis', '') + x.get('how', '')) else '')
    tpl = x.get('tm') or ''
    e = dict(uc=x['uc'], d=d.isoformat(), g=g, t=kind(x), n=int(x['n']), s='todo',
             src=f"{g} 组扩量第 {x['r']} 行：{x.get('sc') or x['uc']}", link=LINK[g],
             to='顺延到下周' if (x.get('day') or '').startswith('下周') else '', sc=x.get('sc') or '', k=k,
             tpl=f"{x['uc']} {tpl[:30]}" if tpl and k == '变式' else '', how=how[:80])
    if old:  # 留着原来手写的说明，只改对不上的字段
        for f in ('to',):
            if old.get(f) and not e[f]:
                e[f] = old[f]
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    path = os.path.join(ROOT, 'tools', 'schedule_plan.json')
    P = json.load(open(path, encoding='utf-8'))
    mon = dt.date.fromisoformat(P['week'])
    nxt = mon + dt.timedelta(days=7)
    in_scope = lambda d: d and mon <= d <= nxt
    E = P['E']
    by_row = {}
    for i, e in enumerate(E):
        m = SRC.match(e.get('src', ''))
        if m and in_scope(dt.date.fromisoformat(e['d'])):
            by_row.setdefault((m.group(1), int(m.group(2))), []).append(i)
    keep, add, changes = {}, [], []
    seen = set()
    for g, tab in TABS.items():
        rows = json.load(open(os.path.join(a.dir, tab + '.json'), encoding='utf-8'))['rows']
        # 本周开头那块：第一行日期在这周的行号
        starts = [x['r'] for x in rows if (d := parse_day(x.get('d0'), mon.year, nxt)) and mon <= d < nxt]
        start = min(starts) if starts else 10 ** 9
        for x in rows:
            key = (g, x['r'])
            d = parse_day(x.get('day'), mon.year, nxt)
            has = bool(x.get('uc')) and str(x.get('n') or '').strip().isdigit()
            olds = by_row.get(key, [])
            if not has:
                continue
            if olds:
                seen.add(key)
                old = E[olds[0]]
                tot = sum(E[i]['n'] for i in olds)
                same = all(E[i]['uc'] == x['uc'] for i in olds) and tot == int(x['n']) and E[olds[0]]['t'] == kind(x)
                if same:
                    if x['r'] >= start and d and in_scope(d) and len(olds) == 1 and old['d'] != d.isoformat():
                        changes.append(f"{g} 第 {x['r']} 行 日期 {old['d']} → {d}")
                        keep[olds[0]] = dict(old, d=d.isoformat(), to=old.get('to') or ('顺延到下周' if d == nxt else ''))
                    continue
                dd = d if (x['r'] >= start and d and in_scope(d)) else dt.date.fromisoformat(old['d'])
                ne = entry(g, x, dd, old)
                changes.append(f"{g} 第 {x['r']} 行 {'+'.join(E[i]['uc'] for i in olds)} {tot} 条 {old['t']} → {x['uc']} {x['n']} 条 {ne['t']}（{dd}）")
                keep[olds[0]] = ne
                for i in olds[1:]:
                    keep[i] = None
            elif x['r'] >= start and d and in_scope(d):
                ne = entry(g, x, d)
                changes.append(f"{g} 第 {x['r']} 行 新加 {x['uc']} {x['n']} 条 {ne['t']}（{d}）")
                add.append(ne)
    for key, idx in by_row.items():
        if key not in seen:
            for i in idx:
                changes.append(f"{key[0]} 第 {key[1]} 行 表里已经没有了，删掉 E 里的 {E[i]['uc']} {E[i]['n']} 条（{E[i]['d']}）")
                keep[i] = None
    out = []
    for i, e in enumerate(E):
        if i in keep:
            if keep[i] is not None:
                out.append(keep[i])
        else:
            out.append(e)
    out += add
    for c in changes:
        print(c)
    tot = lambda L, g, d0, d1: sum(e['n'] for e in L if e['g'] == g and d0 <= e['d'] <= d1 and SRC.match(e.get('src', '')))
    for g in 'AB':
        print(f"{g} 组本周（{mon}–{mon + dt.timedelta(days=6)}）E 里扩量行合计：{tot(E, g, str(mon), str(mon + dt.timedelta(days=6)))} → {tot(out, g, str(mon), str(mon + dt.timedelta(days=6)))}；下周 {tot(E, g, str(nxt), str(nxt))} → {tot(out, g, str(nxt), str(nxt))}")
    print(f'共 {len(changes)} 处')
    if a.apply and changes:
        P['E'] = out
        P['asof'] = T.isoformat()
        json.dump(P, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('已写回 tools/schedule_plan.json')


if __name__ == '__main__':
    main()
