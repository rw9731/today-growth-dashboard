"""排期进度：截至昨天每组该交多少、实交多少、落下哪几行。不改飞书。

用法：
  python3 tools/schedule_progress.py --dir /tmp/sched/feishu --date T --out /tmp/sched/progress.json [--since YYYY-MM-DD]

--dir 里是 tools/schedule_read.js 在 6 个飞书 tab 跑出来的结果，文件名 <tab id>.json。
--since 默认是 T-1 所在那周的周一，只核对这之后到期的行。T = 看板当天，核对到 T-1。

怎么算：
- 扩量素材迭代排期（A 组 kMJdAv、B 组 3KtioB）：日期按合并单元格往下带，「怎么改」里写了「还要做，M/D 交」的按这个日期算。
  该交 = 条数，实交 = 扩量素材名按换行拆的条数。类型看「怎么改」里的【AI】或【二创/重配】。B 组这个 tab 是空的也能跑。
- 新素材每周排期（A 组 nPw5Dc）：该交 = 注意事项里「拍 N 条」。实交 = 脚本及成片（f18d7b）里同 use case、成片不空、完成时间在这周到 T-1 的条数，按日期从早到晚分给各行。
- 脚本&成片（B 组 c665d9）、真人素材和ai切片二剪（B 组 EnYgPG）：每行一条，产出日期到期算该交，成片或二创成片不空算实交。
- tools/schedule_plan.json 里已经建议拿掉（s = cut）的行不算该交，算在 skipped。
输出 line（页面那一行）、draft（给唯西的提醒草稿，只推给 Reina，不自己发群）。
"""
import argparse, datetime as dt, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TABS = {'A': {'kx': 'kMJdAv', 'sc': 'f18d7b', 'new': 'nPw5Dc'}, 'B': {'sc': 'c665d9', 'ec': 'EnYgPG', 'kx': '3KtioB'}}
NAMES = {('A', 'kx'): '扩量', ('B', 'kx'): '扩量', ('A', 'new'): '新素材排期', ('B', 'sc'): '脚本', ('B', 'ec'): '二创'}


def parse_day(s, T):
    """11/3 周二（…）、2026/11/04、2026/11/3、2026-11-04 都认。没写年按离 T 最近的年份。"""
    s = (s or '').strip()
    m = re.match(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'(\d{1,2})/(\d{1,2})', s)
    if m:
        d = dt.date(T.year, int(m.group(1)), int(m.group(2)))
        if (d - T).days > 180:
            d = d.replace(year=T.year - 1)
        elif (T - d).days > 180:
            d = d.replace(year=T.year + 1)
        return d
    return None


def clean_uc(s):
    return (s or '').strip().split('\n')[0].strip()


def is_uc(s):
    return bool(re.fullmatch(r'[A-Z]{1,2}\d{2}', s))


def kind_of(how):
    m = re.search(r'【(AI|二创[^】]*|重配[^】]*)】', how or '')
    if not m:
        return ''
    return 'AI' if m.group(1) == 'AI' else '二创'


def load_tab(folder, tab):
    p = os.path.join(folder, tab + '.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    if isinstance(d, str):  # javascript_tool 的返回值原样存的
        d = json.loads(d)
    return d.get('rows', [])


def load_cut(plan):
    """plan 里建议拿掉的行：{(组, 表, 行号): uc}，新素材排期没有行号，按 (A, new, 日期, uc)。"""
    out = {}
    pat = {'扩量': 'kx', '脚本': 'sc', '二创': 'ec'}
    for e in plan.get('E', []):
        if e.get('s') != 'cut':
            continue
        src = e.get('src', '').split('：')[-1]
        m = re.match(r'([AB]) 组(扩量|脚本|二创)第 (\d+) 行', src)
        if m:
            out[(m.group(1), pat[m.group(2)], int(m.group(3)))] = e.get('uc')
        elif '新素材排期' in src:
            out[('A', 'new', e['d'], e.get('uc'))] = e.get('n')
    return out


def kx_rows(rows, group, T, since, upto, cut):
    due, skipped = [], 0
    day = None
    for x in rows:
        d = parse_day(x.get('日期'), T)
        if d:
            day = d
        uc = clean_uc(x.get('UC_ID'))
        n_txt = str(x.get('条数', '')).strip()
        if not is_uc(uc) or not re.fullmatch(r'\d+', n_txt):
            continue
        how = x.get('怎么改', '')
        over = re.search(r'还要做，(\d{1,2}/\d{1,2}) ?交', how)
        when = parse_day(over.group(1), T) if over else day
        if not when or when < since or when > upto:
            continue
        n = int(n_txt)
        got = len(x.get('扩量素材名') or [])
        if cut.get((group, 'kx', x['r'])) == uc and got == 0:
            skipped += n
            continue
        due.append(dict(tab='kx', r=x['r'], uc=uc, n=n, got=min(got, n), extra=max(0, got - n), due=when.isoformat(), kind=kind_of(how)))
    return due, skipped


def new_rows(rows, sc, T, since, upto, cut):
    """A 组新素材：排期按 use case 和日期，交付在脚本及成片里按 use case 找。"""
    done = {}
    review = 0
    for x in sc or []:
        uc = clean_uc(x.get('UC_ID'))
        when = parse_day(x.get('完成时间'), T)
        if is_uc(uc) and x.get('成片') and when:
            done.setdefault(uc, []).append(when)
            if '通过' not in (x.get('成片状态') or '') and when <= upto:
                review += 1
    for v in done.values():
        v.sort()
    due, skipped = [], 0
    day = None
    for x in rows:
        d = parse_day(x.get('日期'), T)
        if d:
            day = d
        uc = clean_uc(x.get('UC_ID'))
        m = re.search(r'拍 ?(\d+) ?条', x.get('注意事项', ''))
        if not is_uc(uc) or not m or not day or day < since or day > upto:
            continue
        n = int(m.group(1))
        if cut.get(('A', 'new', day.isoformat(), uc)):
            skipped += n
            continue
        mon = day - dt.timedelta(days=day.weekday())
        pool = [w for w in done.get(uc, []) if mon <= w <= upto]
        got = min(n, len(pool))
        for w in pool[:got]:
            done[uc].remove(w)
        due.append(dict(tab='new', r=x['r'], uc=uc, n=n, got=got, extra=0, due=day.isoformat(), kind='AI'))
    return due, skipped, review


def one_per_row(rows, group, tab, field, T, since, upto, cut):
    due, skipped = [], 0
    day = None
    for x in rows:
        d = parse_day(x.get('产出日期'), T)
        if d:
            day = d
        uc = clean_uc(x.get('UC_ID'))
        if not is_uc(uc) or not day or day < since or day > upto:
            continue
        got = 1 if x.get(field) else 0
        if cut.get((group, tab, x['r'])) == uc and not got:
            skipped += 1
            continue
        due.append(dict(tab=tab, r=x['r'], uc=uc, n=1, got=got, extra=0, due=day.isoformat(), kind='AI' if tab == 'sc' else '二创'))
    return due, skipped


def md(s):
    d = dt.date.fromisoformat(s)
    return f'{d.month}/{d.day}'


def uc_label(uc, names):
    return f"{uc} {names[uc]}" if uc in names else uc


def lag_text(x, group, names):
    kind = (' ' + x['kind']) if x.get('kind') else ''
    return f"{group} 组{NAMES[(group, x['tab'])]}第 {x['r']} 行 {uc_label(x['uc'], names)} 差 {x['n'] - x['got']} 条{kind}（{md(x['due'])} 该交）"


def make_draft(group, lags, names, upto):
    if not lags:
        return ''
    lines = [f"{group} 组这边，排期表截至 {md(upto.isoformat())} 还有这几行没交齐："]
    for x in lags:
        lines.append(f"- {NAMES[(group, x['tab'])]}第 {x['r']} 行，{uc_label(x['uc'], names)}，{md(x['due'])} 该交 {x['n']} 条，交了 {x['got']} 条，还差 {x['n'] - x['got']} 条")
    lines.append('麻烦看下今天能不能补上。补不上的回一句哪天能交，我们好提前调后面的安排。')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--since')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    upto = T - dt.timedelta(days=1)
    since = dt.date.fromisoformat(a.since) if a.since else upto - dt.timedelta(days=upto.weekday())
    plan = json.load(open(os.path.join(HERE, 'schedule_plan.json'), encoding='utf-8'))
    ucs = json.load(open(os.path.join(HERE, 'ucs.json'), encoding='utf-8'))
    names = {u: v['short'] for u, v in ucs.items() if isinstance(v, dict) and v.get('short')}
    cut = load_cut(plan)
    tabs = {g: {k: load_tab(a.dir, t) for k, t in v.items()} for g, v in TABS.items()}
    missing = [f'{g} 组 {t}' for g, v in TABS.items() for k, t in v.items() if tabs[g][k] is None]
    out = dict(T=T.isoformat(), since=since.isoformat(), upto=upto.isoformat(), groups={}, missing=missing, draft={})

    def summarize(group, due, skipped, review=0):
        lags = sorted([x for x in due if x['got'] < x['n']], key=lambda x: (x['due'], x['r']))
        kinds = {k: dict(due=sum(x['n'] for x in due if x['kind'] == k), got=sum(x['got'] for x in due if x['kind'] == k)) for k in sorted({x['kind'] for x in due})}
        out['groups'][group] = dict(due=sum(x['n'] for x in due), got=sum(x['got'] for x in due), skipped=skipped, review=review,
                                    extra=sum(x['extra'] for x in due), rows=len(due), by_kind=kinds, lag=[{**x, 'name': names.get(x['uc'], '')} for x in lags])
        out['draft'][group] = make_draft(group, lags, names, upto)

    A, B = tabs['A'], tabs['B']
    if all(A[k] is not None for k in ('kx', 'sc', 'new')):
        d1, s1 = kx_rows(A['kx'], 'A', T, since, upto, cut)
        d2, s2, rv = new_rows(A['new'], A['sc'], T, since, upto, cut)
        summarize('A', d1 + d2, s1 + s2, rv)
    if all(B[k] is not None for k in ('sc', 'ec', 'kx')):
        d1, s1 = kx_rows(B['kx'], 'B', T, since, upto, cut)
        d2, s2 = one_per_row(B['sc'], 'B', 'sc', '成片', T, since, upto, cut)
        d3, s3 = one_per_row(B['ec'], 'B', 'ec', '二创成片', T, since, upto, cut)
        summarize('B', d1 + d2 + d3, s1 + s2 + s3)

    head = []
    for g in ('A', 'B'):
        x = out['groups'].get(g)
        if x:
            head.append(f"{g} 组截至昨天该交 {x['due']} 实交 {x['got']}")
    lags = [lag_text(x, g, names) for g in ('A', 'B') for x in out['groups'].get(g, {}).get('lag', [])]
    out['lags'], out['lag_n'] = lags, len(lags)
    if not head:
        out['head'] = out['line'] = ''
    else:
        out['head'] = f"进度（{md(since.isoformat())} 到 {md(upto.isoformat())}）：" + '，'.join(head) + '。'
        out['line'] = out['head'] + (('落下：' + '；'.join(lags) + '。') if lags else '没有落下的。')
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(line=out['line'], missing=missing, lag_rows=len(lags), draft=out['draft']), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
