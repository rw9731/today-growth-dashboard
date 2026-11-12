"""排期看板「外部 agency」进度：悦普抖音星图达人、知定堂星广（Reina 11/12）。

  python3 tools/agency_progress.py --dir /tmp/sched/agency --date T --out /tmp/sched/agency.json

--dir 里是 tools/agency_read.js 跑出来的 5cypAT.json（悦普执行表）、et1SeP.json（知定堂排期和审核），缺哪个就不出哪家。
周是 T 所在的周一到周日；目标在 tools/agency_targets.json（键是周一），这周没写就沿用最近一周的，并标出来。
- 悦普：只算抖音、合作形式是星图的行。按「发布档期」归到这周；发了 = 稿件进度写已发布或发布链接有值。
  到昨天该发 = 档期在周一到 T-1 的；晚了 = 其中还没发的。
- 知定堂：按「交付日期」归到这周；成片通过 = 成片审核情况写「通过」，条数按「视频链接」那格里的视频数（一行常有真人版、AI 版两条）。
  到昨天该交 = 交付日期在周一到 T-1 的行，按条数算；晚了 = 其中还没通过的行。
"""
import argparse, datetime as dt, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_day(s, T):
    """11月12日、11.13、11/12、11/12/2026、2026/11/12 都认，年份缺了按 T 补（跨年按离 T 近的算）。"""
    s = (s or '').strip()
    m = re.match(r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})', s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r'(\d{1,2})[/.月](\d{1,2})(?:[/.](\d{4}))?', s)
        if not m:
            return None
        mo, d = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else T.year
        if not m.group(3) and abs(mo - T.month) > 6:
            y += 1 if mo < T.month else -1
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def target(targets, key, mon):
    """这周的目标；没写就沿用最近一周的，带 stale 标记。"""
    weeks = sorted((k for k in targets if re.match(r'\d{4}-\d{2}-\d{2}$', k) and key in targets[k]), reverse=True)
    if mon.isoformat() in weeks:
        x = targets[mon.isoformat()][key]
        return x['t'], x.get('note', ''), False
    past = [w for w in weeks if w < mon.isoformat()]
    if past:
        x = targets[past[0]][key]
        return x['t'], x.get('note', ''), True
    return None, '', True


def yuepu(rows, T, mon, sun, targets):
    wk = []
    for x in rows:
        d = parse_day(x.get('d'), T)
        if not d or not (mon <= d <= sun):
            continue
        done = bool(x.get('pub')) or '已发布' in (x.get('st') or '')
        wk.append(dict(r=x['r'], name=x['name'], uc=x.get('uc', ''), st=x.get('st', ''), d=d.isoformat(), done=done))
    wk.sort(key=lambda x: (x['d'], x['r']))
    t, note, stale = target(targets, 'yp', mon)
    due = [x for x in wk if x['d'] < T.isoformat()]
    got = sum(x['done'] for x in wk)
    late = [x for x in due if not x['done']]
    todo = [x for x in wk if not x['done'] and x['d'] >= T.isoformat()]
    return dict(name='悦普', what='抖音星图达人', unit='个', verb='发布', t=t or len(wk), t_note=note, t_stale=stale, sched=len(wk),
                got=got, due=len(due), due_got=sum(x['done'] for x in due), late=late, todo=todo, rows=wk)


def zhidingtang(rows, T, mon, sun, targets):
    wk = []
    for x in rows:
        d = parse_day(x.get('d'), T)
        if not d or not (mon <= d <= sun):
            continue
        ok = '通过' in (x.get('vst') or '')
        n = max(1, int(x.get('vid') or 0)) if ok else int(x.get('vid') or 0)
        wk.append(dict(r=x['r'], name=x.get('acct') or '', uc=x.get('uc', ''), st=x.get('vst') or x.get('sst') or '', d=d.isoformat(), done=ok, n=n, vid=int(x.get('vid') or 0), pub=bool(x.get('pub'))))
    wk.sort(key=lambda x: (x['d'], x['r']))
    t, note, stale = target(targets, 'zdt', mon)
    due = [x for x in wk if x['d'] < T.isoformat()]
    got = sum(x['n'] for x in wk if x['done'])
    late = [x for x in due if not x['done']]
    todo = [x for x in wk if not x['done'] and x['d'] >= T.isoformat()]
    return dict(name='知定堂', what='星广成片', unit='条', verb='成片通过', t=t or len(wk), t_note=note, t_stale=stale, sched=len(wk),
                got=got, due=len(due), due_got=sum(1 for x in due if x['done']), late=late, todo=todo,
                vid=sum(x['vid'] for x in wk), pub=sum(x['pub'] for x in wk), rows=wk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True, help='看板当天 T')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    mon = T - dt.timedelta(days=T.weekday())
    sun = mon + dt.timedelta(days=6)
    targets = json.load(open(os.path.join(ROOT, 'tools', 'agency_targets.json'), encoding='utf-8'))
    out = dict(T=T.isoformat(), mon=mon.isoformat(), sun=sun.isoformat(), list=[], missing=[])
    for fn, f in (('5cypAT', yuepu), ('et1SeP', zhidingtang)):
        p = os.path.join(a.dir, fn + '.json')
        if not os.path.exists(p):
            out['missing'].append(fn)
            continue
        out['list'].append(f(json.load(open(p, encoding='utf-8'))['rows'], T, mon, sun, targets))
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for g in out['list']:
        print(f"{g['name']} {g['what']}：本周{g['verb']} {g['got']}/{g['t']}{'（目标沿用上周）' if g['t_stale'] else ''}，到昨天该{g['verb'][:2]} {g['due']}，晚了 {len(g['late'])}，后面还有 {len(g['todo'])}")
    if out['missing']:
        print('WARNING 没读到：' + '、'.join(out['missing']))


if __name__ == '__main__':
    main()
