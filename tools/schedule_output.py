"""本周实际产出：昨天和本周累计，按 AI、真人二创、星广、星图达人四类，对比本周预计。不改飞书。

用法：
  python3 tools/schedule_output.py --dir /tmp/sched/feishu --date T --out /tmp/sched/output.json

--dir 里是 tools/schedule_read.js 跑出来的结果，除了排期进度的 6 个 tab，还要 lheDJa（星广脚本审核表）、L1c0HC（付费达人执行表）。
T = 看板当天，D = T-1。本周 = D 所在的周一到周日。预计在 tools/schedule_plan.json 的 output_targets。

怎么算（Reina 11/5 要，按实际产出时间算，不按排期日期，也不按上线日期）：
- AI：A 组脚本及成片（完成时间）、B 组脚本&成片（完成时间，空着看文件名日期，再空看产出日期）、两组扩量表里类型是【AI】的（文件名日期）。
- 真人二创：A 组脚本及成片里剪真人原片的（命名含二创、KOC、KOL、原片）、B 组二剪表（文件名日期，再空看产出日期）、两组扩量表里其余的。
- 扩量表类型看「怎么改」里的【AI】【二创/重配】【AI 切片二剪】；没写类型的老行看文件名，含二创算真人二创，否则算 AI。
- 星广：星广脚本审核表，视频链接有内容，按成片完成时间，空着看文件名日期。
- 星图达人：付费达人执行表，按发布时间（和素材产出日报一样，按发布算），写图文的不算。
- 外部 agency 的 KOC/KOL 原片和自建号不在这四类里，不算。
"""
import argparse, datetime as dt, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TABS = {'kxA': 'kMJdAv', 'scA': 'f18d7b', 'kxB': '3KtioB', 'scB': 'c665d9', 'ecB': 'EnYgPG', 'xg': 'lheDJa', 'xt': 'L1c0HC'}
KINDS = [('ai', 'AI 素材'), ('ec', '真人二创'), ('xg', '星广'), ('xt', '星图达人')]
SRC = {'ai': ['A 组', 'B 组'], 'ec': ['A 组', 'B 组']}


def parse_day(s, T):
    """2026/11/04、26年11月4日、11月4号、11/4、11.4、1104 都认。没写年按离 T 最近的年份。"""
    s = str(s or '').strip()
    m = re.match(r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})', s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'(\d{2})年(\d{1,2})月(\d{1,2})', s)
    if m:
        return dt.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'(\d{1,2})[/月.](\d{1,2})', s) or re.fullmatch(r'(\d{2})(\d{2})', s)
    if not m:
        return None
    try:
        d = dt.date(T.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None
    if (d - T).days > 180:
        d = d.replace(year=T.year - 1)
    elif (T - d).days > 180:
        d = d.replace(year=T.year + 1)
    return d


def kx_kind(how, nec, n):
    m = re.search(r'【(AI|AI 切片二剪|二创[^】]*|重配[^】]*)】', how or '')
    if m:
        return ['ai' if m.group(1) == 'AI' else 'ec'] * n
    return ['ec'] * nec + ['ai'] * (n - nec)


def load(folder, tab):
    p = os.path.join(folder, tab + '.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    if isinstance(d, str):
        d = json.loads(d)
    return d.get('rows', [])


def compute(folder, T, targets):
    D = T - dt.timedelta(days=1)
    mon = D - dt.timedelta(days=D.weekday())
    raw = {k: load(folder, v) for k, v in TABS.items()}
    missing = [TABS[k] for k, v in raw.items() if v is None]
    cnt = {k: {} for k, _ in KINDS}   # kind -> {来源: {日期: 条数}}
    undated = []

    def add(kind, src, day, n=1):
        if day and mon <= day <= D:
            b = cnt[kind].setdefault(src, {})
            b[day] = b.get(day, 0) + n

    for x in raw['scA'] or []:
        day = parse_day(x.get('完成时间'), T)
        ec = int(x.get('ec', 0))
        add('ai', 'A 组', day, int(x.get('n', 1)) - ec)
        add('ec', 'A 组', day, ec)
    for key, src in (('kxA', 'A 组'), ('kxB', 'B 组')):
        row_day = None
        for x in raw[key] or []:
            row_day = parse_day(x.get('日期'), T) or row_day
            n = x.get('扩量素材名') or 0
            if not n:
                continue
            ds = x.get('ds') or [''] * n
            kinds = kx_kind(x.get('怎么改'), min(x.get('nec', n), n), n)
            for f, kind in zip(ds, kinds):
                day = parse_day(f, T)
                if not day:
                    day = row_day
                    undated.append(f"{src}扩量第 {x['r']} 行")
                add(kind, src, day)
    for x in raw['scB'] or []:
        if x.get('成片'):
            add('ai', 'B 组', parse_day(x.get('完成时间'), T) or parse_day(x.get('fd'), T) or parse_day(x.get('产出日期'), T))
    for x in raw['ecB'] or []:
        if x.get('二创成片'):
            add('ec', 'B 组', parse_day(x.get('fd'), T) or parse_day(x.get('产出日期'), T))
    for x in raw['xg'] or []:
        if x.get('视频链接'):
            add('xg', '', parse_day(x.get('成片完成时间'), T) or parse_day(x.get('fd'), T))
    for x in raw['xt'] or []:
        if '图文' not in str(x.get('合作形式', '')):
            add('xt', '', parse_day(x.get('发布时间'), T))

    days = (D - mon).days + 1
    rows = []
    for k, name in KINDS:
        srcs = cnt[k]
        total = sum(sum(v.values()) for v in srcs.values())
        rows.append(dict(k=k, name=name, y=sum(v.get(D, 0) for v in srcs.values()), n=total, t=targets.get(k, 0),
                         split=[[s, sum(srcs.get(s, {}).values())] for s in SRC.get(k, [])]))
    return dict(T=T.isoformat(), D=D.isoformat(), mon=mon.isoformat(), days=days, rows=rows, missing=missing, undated=sorted(set(undated)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    plan = json.load(open(os.path.join(HERE, 'schedule_plan.json'), encoding='utf-8'))
    out = compute(a.dir, T, plan.get('output_targets', {}))
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
