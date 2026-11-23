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
             tpl=f"{x['uc']} {tpl[:30]}" if tpl and k == '变式' else '', how=how[:80],
             tier=x.get('tier') or '', bt=x.get('bt') or '')  # 档位、排期类型：排期表 11/20 起有这两列，看板优先用
    if old:  # 留着原来手写的说明，只改对不上的字段
        for f in ('to',):
            if old.get(f) and not e[f]:
                e[f] = old[f]
    return e


def roll_week(P, T):
    """周一换新一周（Reina 11/23：周一就要能看到新一周的排期分布，不等手动换周）。
    T 所在那周的周一晚于 plan 的 week 时：上周产出目标写进 targets_by_week，week 换成这周一，
    产能取 capacity_by_week[这周一]（Reina 给的周产量），没有就沿用上周；MOVES、MT、cap_extra 清空。
    每天怎么分只按周总量推（周六日每组 AI、二创各 10，其余平摊到周一到周五），只管周总量。"""
    mon = T - dt.timedelta(days=T.weekday())
    old = dt.date.fromisoformat(P['week'])
    if mon <= old:
        return ''
    m = P.get('meters') or []
    if len(m) == 4:
        P.setdefault('targets_by_week', {})[old.isoformat()] = {
            'ai': m[0][2] + m[2][2], 'ec': m[1][2] + m[3][2],
            'xg': P.get('output_targets', {}).get('xg', 0), 'kol': P.get('output_targets', {}).get('kol', 0)}
    cap = (P.get('capacity_by_week') or {}).get(mon.isoformat()) or {}
    ga, gb = cap.get('唯西A组信息流') or {}, cap.get('唯西B组') or {}
    note = ''
    if ga.get('AI') and gb.get('AI'):
        c = {'A': (ga['AI'], ga['二创']), 'B': (gb['AI'], gb['二创'])}
        P['week_total'] = {'A': ga['AI'] + ga['二创'], 'B': gb['AI'] + gb['二创']}
        P['cap_day'] = {g: {'wd': {'AI': round((ai - 20) / 5), '二创': round((ec - 20) / 5)}, 'we': {'AI': 10, '二创': 10}}
                        for g, (ai, ec) in c.items()}
        P['cap_note'] = (f"{mon.month}/{mon.day} 这周产能取 capacity_by_week：A 组信息流 {P['week_total']['A']}（AI {c['A'][0]}、二创 {c['A'][1]}），"
                         f"B 组 {P['week_total']['B']}（AI {c['B'][0]}、二创 {c['B'][1]}）。每天怎么分按周六日各 10、其余平摊推的，只管周总量。")
    else:
        c = {'A': (m[0][2], m[1][2]), 'B': (m[2][2], m[3][2])} if len(m) == 4 else {'A': (0, 0), 'B': (0, 0)}
        note = '（这周的产能还没写进 capacity_by_week，沿用上周）'
    P['meters'] = [['A 组 AI', 0, c['A'][0]], ['A 组二创', 0, c['A'][1]], ['B 组 AI', 0, c['B'][0]], ['B 组二创', 0, c['B'][1]]]
    P['week'] = mon.isoformat()
    P['MOVES'], P['MT'], P['cap_extra'] = [], {}, {}
    return f'换周：plan 的 week {old} → {mon}{note}'


def week_meters(P, E, mon):
    """meters 的已排条数和 sub 按 E 里这周的扩量行重算。"""
    d0, d1 = mon.isoformat(), (mon + dt.timedelta(days=6)).isoformat()
    s = {}
    days = set()
    for e in E:
        if SRC.match(e.get('src', '')) and d0 <= e['d'] <= d1 and e['d'] >= d0:
            s[(e['g'], e['t'])] = s.get((e['g'], e['t']), 0) + e['n']
            days.add(e['d'])
    m = P.get('meters') or []
    if len(m) == 4:
        for row, key in zip(m, [('A', 'AI'), ('A', '二创'), ('B', 'AI'), ('B', '二创')]):
            row[1] = s.get(key, 0)
    last = max(days) if days else ''
    P['sub'] = (f"这周（{mon.month}/{mon.day}–{(mon + dt.timedelta(days=6)).month}/{(mon + dt.timedelta(days=6)).day}）的排期按飞书 A 组、B 组扩量排期同步"
                + (f"，飞书现在排到 {int(last[5:7])}/{int(last[8:])}" if last else '') +
                f"：A 组 AI {s.get(('A', 'AI'), 0)}、二创 {s.get(('A', '二创'), 0)}，B 组 AI {s.get(('B', 'AI'), 0)}、二创 {s.get(('B', '二创'), 0)}。"
                + (P.get('cap_note') or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    path = os.path.join(ROOT, 'tools', 'schedule_plan.json')
    P = json.load(open(path, encoding='utf-8'))
    rolled = roll_week(P, T)
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
                    # 表里写「下周」的老顺延行（11/23：A 组第 210–216 行是 11/10 顺延的），换周后不再往后推
                    stale_next = (x.get('day') or '').startswith('下周') and old['d'] < nxt.isoformat()
                    if not stale_next and x['r'] >= start and d and in_scope(d) and len(olds) == 1 and old['d'] != d.isoformat():
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
    if rolled:
        print(rolled)
    if a.apply and (changes or rolled):
        P['E'] = out
        week_meters(P, out, mon)
        P['asof'] = T.isoformat()
        json.dump(P, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('已写回 tools/schedule_plan.json')


if __name__ == '__main__':
    main()
