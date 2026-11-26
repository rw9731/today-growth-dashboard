"""将本周排期、产出底表与分日投放记录关联，按生产素材统计回收。"""

from collections import defaultdict
import json
from datetime import date, timedelta
import re

from output_build import KX, norm
import compute

ROW_IN_NAME = re.compile(r'(?<![A-Za-z0-9])([AB])(\d{2,3})[-_]0?\d(?!\d)')


def type_label(name, ids, facts, plan_t=''):
    """回收明细的类型列（Reina 11/23）：AI / 达人剪辑 / 达人原片 / 星广 / 星图 / 自建号。
    先按投放来源和素材 ID 认星广、星图、自建号，再看名字；认不出时用排期行的 AI / 二创。"""
    kinds = [compute.kind_of((facts.get(mid) or {}).get('src', ''), '', name, mid) for mid in ids]
    for k in kinds:
        for key in ('星图', '星广', '自建号'):
            if key in k:
                return key
    for k in kinds:
        if k.startswith('AI'):
            return 'AI'
        if k.startswith(('KOC', 'KOL')):
            return '达人原片' if k.endswith('原片') else '达人剪辑'
    if re.search(r'(?:^|[_-])AI(?:[_-]|素材|重拍)|AI素材|AI重拍|照真人', name):
        return 'AI'
    if re.search(r'(?i)koc|kol|达人|二创|真人', name):
        return '达人剪辑'
    return {'AI': 'AI', '二创': '达人剪辑'}.get(plan_t, '未标')


def xingtu_items(hist, week, end):
    """星图达人原生视频（Reina 11/23）：不在唯西排期行里，按 tools/xingtu.json 的素材 ID 从逐日历史里补进回收，
    首花在这一周的才算；类型写「星图达人原生」，ext=True 不计入「已放出 / 本周已排」。"""
    out = []
    H = (hist or {}).get('U', hist or {})
    for u, rows in H.items():
        for ids, name, *rest in rows:
            hit = [i for i in ids if i in compute.XT]
            first = rest[1] if len(rest) > 1 else ''
            if not hit or not first or not week <= first <= end:
                continue
            cost, act, ret, c1 = (rest[2:6] + [0, 0, 0, 0])[:4]
            out.append(dict(id=hit[0], ids=sorted(ids), ref='', u=u, name=name, ext=True,
                            typ='星图达人原生 · ' + compute.XT[hit[0]][0].replace('星图', ''),
                            due='', produced='', released=first, first=first,
                            cents=round(cost * 100), ret_cents=round(c1 * 100), act=act or 0, ret=ret or 0, up=None))
    return out



def cut_week(path, week, end):
    """原片精剪（Reina 11/23「放一起」）：两组「原片精剪排期」tab 的行，按交付日落在这一周的算进本周素材回收。
    notes/cut-items.json 由浏览器读两个 tab 写入（g、id、row、d 交付日、typ 达人原片/星广、uc、who 博主、n 条数、films 成片名）。"""
    try:
        src = json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        return [], {}
    rows = [r for r in src.get('rows', []) if week <= r.get('d', '') <= end and int(r.get('n') or 0) > 0]
    return rows, src.get('tabs', {})


def cut_entries(rows):
    return [dict(g=r['g'], uc=r['uc'], d=r['d'], t='精剪', n=int(r['n']), id=r['id'], ref=f"{r['g']}:{r['id']}:{r['uc']}",
                 src=f"{r['g']} 组原片精剪 {r['id']}：{r['typ']}·{r['who']}", sc='原片精剪：' + r['typ']) for r in rows]


def cut_items(rows, facts, T):
    """精剪成片按名字（去 .mp4、符号）关联投放素材 ID；按成片所在行算，不按名字里写的编号（B 组有几行名字抄错了编号）。"""
    if not facts:
        return []
    by_name = defaultdict(set)
    for mid, fact in facts.items():
        for name in fact['names']:
            by_name[norm(name)].add(mid)
    claims = defaultdict(list)
    for r in rows:
        for name in r.get('films', []):
            for mid in by_name.get(norm(name), ()):
                claims[mid].append((r['id'], name))
    linked = defaultdict(list)
    for mid, keys in claims.items():
        if len(set(keys)) == 1:
            linked[keys[0]].append(mid)
    by_id = {r['id']: r for r in rows}
    out = []
    for (rid, name), ids in linked.items():
        r = by_id[rid]
        ids = sorted(ids)
        records = [facts[mid] for mid in ids]
        verdicts = [f['up'] for f in records if f['up'] is not None]
        out.append(dict(
            id=ids[0], ids=ids, ref=f"{r['g']}:{rid}:{r['uc']}", u=r['uc'], name=re.sub(r'\.(mp4|mov)$', '', name), cut=True,
            typ='原片精剪 · ' + r['typ'], due=r['d'], produced='', released=min(f['released'] for f in records),
            first=min((f['first'] for f in records if f['first']), default=''),
            cents=sum(f['cents'] for f in records), ret_cents=sum(f['ret_cents'] for f in records),
            act=sum(f['act'] for f in records), ret=sum(f['ret'] for f in records), up=any(verdicts) if verdicts else None))
    return out


def plan_ref(entry):
    match = re.search(r'([AB])\s*组(?:扩量)?第\s*(\d+)\s*行', entry.get('src', ''))
    if match and match[1] == entry.get('g'):
        return f'{match[1]}:{int(match[2])}:{entry["uc"]}'
    return ''


def weekly_recovery(entries, production, facts, T, D):
    monday = T - timedelta(days=T.weekday())
    week = monday.isoformat()
    data = dict(week=week, end=(monday + timedelta(days=6)).isoformat(),
                through=D.isoformat(), available=production is not None and facts is not None, items=[])
    if not data['available']:
        return data

    due = {plan_ref(e): e['d'] for e in entries if int(e.get('n') or 0) > 0}
    plan_t = {plan_ref(e): e.get('t', '') for e in entries if int(e.get('n') or 0) > 0}
    row_ref = {r.rsplit(':', 1)[0]: r for r in due if r}
    by_name = defaultdict(set)
    for mid, fact in facts.items():
        for name in fact['names']:
            by_name[norm(name)].add(mid)

    # 同一条成片可以在多个账户、平台或素材 ID 下投放。一个 ID 只归到唯一能核实的成片。
    assets = {}
    claims = defaultdict(list)
    for key, film in production.items():
        group = film.get('g')
        uc = film.get('uc')
        ref = f'{group}:{film.get("row")}:{uc}'
        if film.get('tab') != KX.get(group):
            # 脚本表、二剪表交的成片按名字里写的排期行号（B145-01）归到排期行（Reina 11/26：美好生活放出数对不上）
            m = ROW_IN_NAME.search(film.get('name', ''))
            ref = row_ref.get(f'{m[1]}:{int(m[2])}') if m and m[1] == group else None
            if ref and uc and not ref.endswith(':' + uc) and ref.rsplit(':', 1)[1] not in film.get('name', ''):
                ref = None  # 名字里的行号对上了，use case 对不上的不算（B145-01 雪莉Shirley 是 WK01，不是 B 组第 145 行的美好生活）
        if (not ref or ref not in due or film.get('k') == 'X'
                or not week <= film.get('d', '') <= T.isoformat()):
            continue
        candidates = by_name[norm(film['name'])] | {film.get('mid')}
        for mid in candidates:
            fact = facts.get(mid)
            if fact and fact['released'] >= (date.fromisoformat(film['d']) - timedelta(days=3)).isoformat():  # 上传可能比表里登记的完成日早一两天
                claims[mid].append(key)
                assets[key] = (film, ref)

    linked = defaultdict(list)
    for mid, keys in claims.items():
        if len(keys) == 1:
            linked[keys[0]].append(mid)
    for key, ids in linked.items():
        film, ref = assets[key]
        ids = sorted(ids)
        records = [facts[mid] for mid in ids]
        first = min((fact['first'] for fact in records if fact['first']), default='')
        verdicts = [fact['up'] for fact in records if fact['up'] is not None]
        data['items'].append(dict(
            id=ids[0], ids=ids, ref=ref, u=ref.rsplit(':', 1)[1] or film['uc'], name=film['name'], typ=type_label(film['name'], ids, facts, plan_t.get(ref, '')),
            due=due[ref], produced=film['d'], released=min(fact['released'] for fact in records), first=first,
            cents=sum(fact['cents'] for fact in records), ret_cents=sum(fact['ret_cents'] for fact in records),
            act=sum(fact['act'] for fact in records), ret=sum(fact['ret'] for fact in records),
            up=any(verdicts) if verdicts else None,
        ))
    data['items'].sort(key=lambda x: (-x['cents'], x['released'], x['id']))
    return data



def made_counts(entries, production, cut_rows, week, T):
    """每个排期行实际交了几条、审核通过几条（Reina 11/26：回收表要能看到实际完成进度）。
    扩量表的成片按所在行号对；脚本表、二剪表的成片按名字里写的排期行号（B238-02、A353-01）对；
    精剪按两组精剪 tab 的成片格数，精剪不用等审，交了就算通过。只换前贴的不算。返回 {ref: [交了, 通过]}。"""
    refs = {}
    for e in entries:
        if int(e.get('n') or 0) > 0:
            r = plan_ref(e)
            if r:
                g, row, _ = r.split(':', 2)
                refs.setdefault(f'{g}:{row}', r)
    made = defaultdict(lambda: [0, 0])
    for film in (production or {}).values():
        if film.get('k') == 'X' or not week <= film.get('d', '') <= T:
            continue
        g = film.get('g')
        ref = None
        if film.get('tab') == KX.get(g):
            ref = refs.get(f'{g}:{film.get("row")}')
        else:
            m = ROW_IN_NAME.search(film.get('name', ''))
            if m and m[1] == g:
                ref = refs.get(f'{g}:{int(m[2])}')
                if ref and film.get('uc') and not ref.endswith(':' + film['uc']) and ref.rsplit(':', 1)[1] not in film.get('name', ''):  # 脚本表 UC 标错时以名字里的 UC 为准
                    ref = None
        if not ref:
            continue
        made[ref][0] += 1
        if film.get('ok'):
            made[ref][1] += 1
    for r in cut_rows or []:
        n = len(r.get('films') or [])
        if n:
            made[f"{r['g']}:{r['id']}:{r['uc']}"] = [n, n]
    return dict(made)
