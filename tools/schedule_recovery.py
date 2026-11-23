"""将本周排期、产出底表与分日投放记录关联，按生产素材统计回收。"""

from collections import defaultdict
from datetime import timedelta
import re

from output_build import KX, norm
import compute


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
        if (film.get('tab') != KX.get(group) or ref not in due or film.get('k') == 'X'
                or not week <= film.get('d', '') <= T.isoformat()):
            continue
        candidates = by_name[norm(film['name'])] | {film.get('mid')}
        for mid in candidates:
            fact = facts.get(mid)
            if fact and fact['released'] >= film['d']:
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
            id=ids[0], ids=ids, ref=ref, u=film['uc'], name=film['name'], typ=type_label(film['name'], ids, facts, plan_t.get(ref, '')),
            due=due[ref], produced=film['d'], released=min(fact['released'] for fact in records), first=first,
            cents=sum(fact['cents'] for fact in records), ret_cents=sum(fact['ret_cents'] for fact in records),
            act=sum(fact['act'] for fact in records), ret=sum(fact['ret'] for fact in records),
            up=any(verdicts) if verdicts else None,
        ))
    data['items'].sort(key=lambda x: (-x['cents'], x['released'], x['id']))
    return data
