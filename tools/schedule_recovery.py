"""将本周排期、产出底表与分日投放记录关联，按生产素材统计回收。"""

from collections import defaultdict
from datetime import timedelta
import re

from output_build import KX, norm


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
            id=ids[0], ids=ids, ref=ref, u=film['uc'], name=film['name'],
            due=due[ref], produced=film['d'], released=min(fact['released'] for fact in records), first=first,
            cents=sum(fact['cents'] for fact in records), ret_cents=sum(fact['ret_cents'] for fact in records),
            act=sum(fact['act'] for fact in records), ret=sum(fact['ret'] for fact in records),
            up=any(verdicts) if verdicts else None,
        ))
    data['items'].sort(key=lambda x: (-x['cents'], x['released'], x['id']))
    return data
