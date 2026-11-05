"""分日表审核核对（Reina 11/5）：投放分日表里新花钱的扩量、二剪，是不是都审过。只读，不发消息，不改飞书。

用法：
  python3 tools/review_cover.py --sheet <分日文件> --date D --dir /tmp/sched/feishu --out /tmp/sched/review_cover.json [--since 2026-11-05]

--dir 是 tools/schedule_read.js 跑出来的 <tab id>.json，用里面的 cov：kMJdAv、f18d7b、c665d9、EnYgPG、3KtioB。
范围：首花在 since 之后、名字带 扩量、二创、二剪、重配 这类字的素材。文件名日期早于 since 的不算（规则：只审 11/5 起交的），带「改动」「合规修改」的是后来改的，算。
分四类：
- no_table：表里找不到，没传到审核表就投了
- not_reviewed：表里有，成片状态是空的、待审核、修改后待审核，或者标了通过但没有审核备注（他们自己标的）
- need_fix：状态是需修改，备注不是小改，还在花钱
- ok：通过，或者小改（小改完直接传，不用再看）
"""
import argparse, datetime as dt, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schedule_data as S

TABS = ['kMJdAv', 'f18d7b', 'c665d9', 'EnYgPG', '3KtioB']
EC = re.compile(r'扩量|二创|二剪|重配|新剪|照真人|精剪|精简|混剪')
LATER = re.compile(r'[_-](改动|合规修改|修改\d*)$')


def norm(x):
    x = re.sub(r'\.(mp4|mov|m4v)$', '', (x or '').strip(), flags=re.I)
    x = re.sub(r'^推送视频[_-]?', '', x)
    x = LATER.sub('', x)
    return re.sub(r'[^一-龥a-zA-Z0-9]', '', x).lower()


def fnv(s):
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xffffffff
    return h


def b36(n):
    d = '0123456789abcdefghijklmnopqrstuvwxyz'
    out = ''
    while True:
        n, r = divmod(n, 36)
        out = d[r] + out
        if not n:
            return out


def key(name):
    return b36(fnv(norm(name)))


def name_day(name):
    """文件名里最后一个日期，20261103、-261103 都认。没有返回 None。"""
    L = re.findall(r'(?<![0-9a-zA-Z])(?:20)?26(\d{2})(\d{2})(?!\d)', name or '')
    L = [x for x in L if 1 <= int(x[0]) <= 12 and 1 <= int(x[1]) <= 31]
    return dt.date(2026, int(L[-1][0]), int(L[-1][1])) if L else None


def load_cov(folder):
    idx, seen, missing = {}, [], []
    for tab in TABS:
        p = os.path.join(folder, tab + '.json')
        if not os.path.exists(p):
            missing.append(tab)
            continue
        d = json.load(open(p, encoding='utf-8'))
        if isinstance(d, str):
            d = json.loads(d)
        cov = d.get('cov')
        if cov is None:
            missing.append(tab)
            continue
        seen.append(tab)
        for r, st, note, hs in cov:
            for h in hs.split():
                idx.setdefault(h, []).append(dict(tab=tab, name=d.get('tab', ''), r=r, st=st, note=note))
    return idx, seen, missing


def classify(hits):
    """一条素材可能在排期表和交审 tab 都有：有状态的那行算数。备注 note：0 没写、1 写了、2 写了小改。
    通过但没有备注的，是他们自己标的（11/5 B 组第 9 行就是这样），算没审。"""
    if not hits:
        return 'no_table', None
    ok = [h for h in hits if ('通过' in h['st'] and '未通过' not in h['st'] and h['note']) or h['note'] == 2]
    if ok:
        return 'ok', ok[0]
    fix = [h for h in hits if '需修改' in h['st'] or '未通过' in h['st']]
    if fix:
        return 'need_fix', fix[0]
    self_ok = [h for h in hits if '通过' in h['st']]
    if self_ok:
        return 'not_reviewed', {**self_ok[0], 'st': '标了通过，没有审核备注'}
    return 'not_reviewed', ([h for h in hits if h['st']] or hits)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--since', default='2026-11-05')
    a = ap.parse_args()
    D, since = dt.date.fromisoformat(a.date), dt.date.fromisoformat(a.since)
    first, name, cost = {}, {}, {}
    for r in S.load_rows(a.sheet):
        if r['d'] > D or r['c'] <= 0:
            continue
        first[r['id']] = min(first.get(r['id'], r['d']), r['d'])
        name[r['id']] = r['name']
        cost.setdefault(r['id'], {})[r['d']] = r['c']
    idx, seen, missing = load_cov(a.dir)
    out = dict(D=a.date, since=a.since, seen=seen, missing=missing, no_table=[], not_reviewed=[], need_fix=[], ok=0, new=0)
    for i, d in first.items():
        n = name[i]
        if d < since or not EC.search(n):
            continue
        nd = name_day(n)
        if nd and nd < since and not LATER.search(n.strip()):
            continue  # 11/5 之前交的，不补审
        cat, hit = classify(idx.get(key(n), []))
        if d == D:
            out['new'] += 1
        if cat == 'ok':
            out['ok'] += 1
            continue
        out[cat].append(dict(id=i, name=n, first=str(d), spend=round(sum(cost[i].values())), last=round(cost[i].get(D, 0)), tab=hit and hit['name'], r=hit and hit['r'], st=hit and hit['st']))
    for k in ('no_table', 'not_reviewed', 'need_fix'):
        out[k].sort(key=lambda x: -x['spend'])
    bad = len(out['no_table']) + len(out['not_reviewed']) + len(out['need_fix'])
    md = f'{D.month}/{D.day}'
    if missing:
        out['line'] = f'{md} 审核核对没做全：{"、".join(missing)} 没读到'
    elif bad:
        out['line'] = f'{md} 扩量和二剪：{len(out["no_table"])} 条没传表就投了，{len(out["not_reviewed"])} 条传了没审就投了，{len(out["need_fix"])} 条要改还在投'
    elif out['ok']:
        out['line'] = f'{md} 扩量和二剪都审过了（{out["ok"]} 条）'
    else:
        out['line'] = f'{md} 没有要核对的扩量和二剪（{a.since} 起交的还没花钱）'
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(out['line'])


if __name__ == '__main__':
    main()
