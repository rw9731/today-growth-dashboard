"""点亮路线图（Reina 11/17 定，会上说的「素材分类方向图，挨个点亮」）：
每个 use case × 素材类型测了多少、点没点亮、本周排了几条，写 roadmap/index.html。

用法：python3 tools/roadmap.py --sheet <投放数据_分日 A1:AB 的 get_values 文件> --uclib <✅ Use case 库 A1:H 的 get_values 文件>

口径：
- 测过 = 花过钱的素材（投放数据_分日 里有消耗）。
- 过冷启 = 上传当天 + 后 2 天花费 ≥ ¥400（日报 CS_COST）。只算上传日在数据开始之后、窗口已过完的素材。
- use case 首次点亮取累计消耗 ≥ ¥100,000 且周消耗占同期全盘 > 2% 的第一周。
  周一到周日为一周，尚未结束的周算到数据截止日。
- 其余 use case 状态：
  判弱 = 近 30 天 ≥ 10 条素材有消耗，且最佳单条累计消耗低于 ¥5,000。
  测试中 = 已投放、继续验证带量能力；没测 = 一条都没花过钱；
  储备 / 暂不做 = Use case 库状态是储备、而且没测过（暂不做的写在 NOT_NOW）。
- 格子（use case × 素材类型）：这一格里有一条素材累计花到 ¥5,000 = 点亮；花过钱的 ≥ 10 条、都没到 ¥5,000 = 偏弱；有花过钱的 = 测过；空 = 没测。
- 本周已排与排期看板共用 schedule_entries.py 的条目，按已点亮和探索汇总。
"""
import argparse
import datetime as dt
import html
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute  # noqa: E402
from schedule_entries import planned_entries

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS_COST = 400
MATERIAL_LIT = 5000
UC_LIT_COST = 100_000
UC_LIT_SHARE_PCT = 2
NOT_NOW = {'TR02': '订高铁票 11/2 定先不做'}
TYPES = ['AI 原片', 'AI 二剪和重拍', '达人原片', '达人二剪', '星广和自建号']


def type_of(kind):
    k = kind or ''
    if k.startswith('AI 短剧'):
        return 'AI 原片' if k.endswith('原片') else 'AI 二剪和重拍'
    if k.startswith('KOC') or k.startswith('KOL'):
        return '达人原片' if k.split(' · ')[1:2] == ['原片'] else '达人二剪'
    if any(s in k for s in ('星广', '星图', '自建号')):
        return '星广和自建号'
    return ''


def uc_can_light(cumulative_cents, week_cents, market_cents):
    """按金额的分比较，保留累计门槛的等号和周占比的严格大于。"""
    return cumulative_cents >= UC_LIT_COST * 100 and market_cents > 0 and week_cents * 100 > market_cents * UC_LIT_SHARE_PCT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--uclib', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'roadmap', 'index.html'))
    a = ap.parse_args()

    rows = compute.load_rows(a.sheet)
    real = [r for r in rows if r['cost'] > 0 or r['act'] > 0]
    D = max(r['date'] for r in real)
    Dd = dt.date.fromisoformat(D)
    first_day = min(r['date'] for r in real)
    d30 = (Dd - dt.timedelta(days=29)).isoformat()
    d7 = (Dd - dt.timedelta(days=6)).isoformat()

    lib = json.load(open(a.uclib))['values']
    hd = {h: i for i, h in enumerate(lib[0])}
    UC = {}
    for r in lib[1:]:
        g = lambda h: r[hd[h]] if hd.get(h) is not None and hd[h] < len(r) else ''
        u = g('UC_ID').strip()
        if not u or g('状态') not in ('在用', '储备'):
            continue
        UC[u] = {'l1': g('一级分类'), 'l2': g('二级分类'), 'name': g('Use case').split('：')[0], 'pri': g('优先级'), 'lib': g('状态')}

    # 每条素材
    M = {}
    for r in rows:
        if r['cost'] <= 0 and r['act'] <= 0 and r['ret'] <= 0:
            continue
        m = M.setdefault(r['id'], {'id': r['id'], 'name': r['name'], 'uc': r['uc'], 'cost': 0.0, 'c30': 0.0, 'days': defaultdict(float),
                                   'kind': compute.kind_of(r['src'], r['track'], r['name'], r['id'], kl=False), 'first': r['date']})
        m['cost'] += r['cost']
        m['days'][r['date']] += r['cost']
        if r['date'] >= d30:
            m['c30'] += r['cost']
        if r['name'] and not m['name']:
            m['name'] = r['name']
        if r['cost'] > 0 and r['date'] < m['first']:
            m['first'] = r['date']
    tot30 = sum(r['cost'] for r in rows if r['date'] >= d30)
    act30 = defaultdict(float)
    ret30 = defaultdict(float)
    for r in rows:
        if d30 <= r['date'] < D:
            act30[r['uc']] += r['act']
        if d30 < r['date'] <= D:
            ret30[r['uc']] += r['ret']

    for m in M.values():
        m['type'] = type_of(m['kind'])
        up = compute.up_day(m['id'])
        m['up'] = up
        w = [(dt.date.fromisoformat(up) + dt.timedelta(days=k)).isoformat() for k in range(3)] if up else []  # Reina 11/18：冷启窗口 3 天
        m['cs'] = None
        if up and up >= first_day and w[-1] <= D:
            m['cs'] = sum(m['days'].get(x, 0) for x in w) >= CS_COST

    # 本周排期
    plan = json.load(open(os.path.join(ROOT, 'tools', 'schedule_plan.json')))
    wk0 = plan.get('week')
    wk1 = (dt.date.fromisoformat(wk0) + dt.timedelta(days=6)).isoformat() if wk0 else None
    sched = defaultdict(lambda: defaultdict(int))
    sched_e = defaultdict(list)
    for e in planned_entries(plan, wk0) if wk0 else []:
        sched[e['uc']][e.get('t', '')] += int(e.get('n') or 0)
        sched_e[e['uc']].append(e)
    all_planned = planned_entries(plan)
    SCN = json.load(open(os.path.join(ROOT, 'tools', 'scenes.json')))
    SM = json.load(open(os.path.join(ROOT, 'notes', 'scene-map.json')))

    def sim(a, b):
        A = {a[i:i + 2] for i in range(len(a) - 1)}
        B = {b[i:i + 2] for i in range(len(b) - 1)}
        return len(A & B) / len(A) if A else 0

    def hits(u, sc_t):
        # 排期一行写的细分场景对到库里的场景编号；一行写几个场景（如首测一条一个）就都算上，条数平分
        scl = SCN.get(u, {}).get('scenes', [])
        h = [c['n'] for c in scl if sim(c['t'], sc_t) >= 0.6]
        if not h and scl:
            b = max(scl, key=lambda c: sim(sc_t, c['t'] + c.get('full', '')))
            if sim(sc_t, b['t'] + b.get('full', '')) >= 0.34:
                h = [b['n']]
        return h

    def split(n_, h):
        return {k: n_ // len(h) + (1 if i < n_ % len(h) else 0) for i, k in enumerate(h)}

    # 汇总到 use case
    by = defaultdict(list)
    for m in M.values():
        by[m['uc']].append(m)
    out = []
    for u, info in UC.items():
        ms = by.get(u, [])
        sp = [m for m in ms if m['cost'] > 0]
        n30 = [m for m in sp if m['c30'] > 0]
        c30 = sum(m['c30'] for m in ms)
        sh = c30 / tot30 if tot30 else 0
        best = max(sp, key=lambda m: m['cost'], default=None)
        if u in NOT_NOW and not sp:
            st = '暂不做'
        elif not sp:
            st = '储备' if info['lib'] == '储备' else '没测'
        elif len(n30) >= 10 and best['cost'] < MATERIAL_LIT:
            st = '判弱'
        else:
            st = '测试中'
        cells = {}
        for t in TYPES:
            cm = [m for m in sp if m['type'] == t]
            if not cm:
                cells[t] = None
                continue
            bm = max(cm, key=lambda m: m['cost'])
            cst = '点亮' if bm['cost'] >= MATERIAL_LIT else ('偏弱' if len(cm) >= 10 else '测过')
            cells[t] = {'n': len(cm), 'best': round(bm['cost']), 'best_name': bm['name'], 'st': cst}
        # 细分场景（Reina 11/17）：每个场景测了几条、最好一条、有没有点亮、这周排了几条
        scs = []
        sc_lib = SCN.get(u, {}).get('scenes', [])
        if sc_lib:
            tag = lambda m: SM.get(m['id']) if SM.get(m['id'], {}).get('uc') == u else None
            for sdef in sc_lib:
                sm_ = [m for m in sp if (tag(m) or {}).get('s') == sdef['n']]
                b_ = max(sm_, key=lambda m: m['cost'], default=None)
                cd_ = [m for m in sm_ if m['cs'] is not None]
                scs.append({'n': sdef['n'], 't': sdef['t'], 'g': sdef.get('g', ''), 'full': sdef.get('full', ''), 'cnt': len(sm_),
                            'cs_n': len(cd_), 'cs_pass': sum(1 for m in cd_ if m['cs']),
                            'best': round(b_['cost']) if b_ else 0, 'best_name': b_['name'] if b_ else '',
                            'c30': round(sum(m['c30'] for m in sm_)), 'first': min((m['first'] for m in sm_), default=''),
                            'last': max((m['first'] for m in sm_), default=''), 'sched': 0})
            for e in sched_e.get(u, []):
                h = hits(u, e.get('sc', ''))
                for k, v in (split(int(e.get('n') or 0), h) if h else {}).items():
                    scs[k - 1]['sched'] += v
            none_ = [m for m in sp if (tag(m) or {}).get('st') == 'none']
            unk_ = [m for m in sp if not (tag(m) or {}).get('s') and (tag(m) or {}).get('st') != 'none']
        else:
            none_, unk_ = [], []
        csd = [m for m in sp if m['cs'] is not None]
        new7 = [m for m in sp if m['first'] >= d7]
        a_, r_ = act30.get(u, 0), ret30.get(u, 0)
        sc = sched.get(u, {})
        out.append({'uc': u, 'name': info['name'], 'l1': info['l1'], 'pri': info['pri'], 'lib': info['lib'], 'st': st,
                    'n': len(sp), 'n30': len(n30), 'new7': len(new7), 'cs_n': len(csd), 'cs_pass': sum(1 for m in csd if m['cs']),
                    'best': round(best['cost']) if best else 0, 'best_name': best['name'] if best else '',
                    'cost': sum(m['cost'] for m in ms), 'c30': round(c30), 'share30': sh,
                    'ret': (r_ / a_) if a_ >= 100 else None, 'act30': round(a_),
                    'first': min((m['first'] for m in sp), default=''), 'last': max((m['first'] for m in sp), default=''),
                    'cells': cells, 'sched': sum(sc.values()), 'sched_t': dict(sc),
                    'note': NOT_NOW.get(u, ''), 'scs': scs, 'sc_none': len(none_), 'sc_unk': len(unk_)})

    # 时间线（Reina 11/17：要有 roadmap 的时间感）：按周看每个 use case 新测了几条、花了多少、哪周点亮、排了几条
    mon = lambda d: (dt.date.fromisoformat(d) - dt.timedelta(days=dt.date.fromisoformat(d).weekday())).isoformat()
    plan_weeks = {mon(e['d']) for e in all_planned}
    W0 = mon(first_day)
    W1 = max([mon(D)] + list(plan_weeks))
    weeks = []
    w = dt.date.fromisoformat(W0)
    while w.isoformat() <= W1:
        weeks.append(w.isoformat())
        w += dt.timedelta(days=7)
    wk_tot = defaultdict(float)
    for r in rows:
        wk_tot[mon(r['date'])] += r['cost']
    market_cents = {wk: round(cost * 100) for wk, cost in wk_tot.items()}
    # 每条素材累计花到 ¥5,000 的那天
    for m in M.values():
        acc, m['lit_day'] = 0.0, None
        for d_ in sorted(m['days']):
            acc += m['days'][d_]
            if acc >= MATERIAL_LIT:
                m['lit_day'] = d_
                break
    plan_wk = defaultdict(lambda: defaultdict(int))
    all_by_uc = defaultdict(list)
    for e in all_planned:
        plan_wk[e['uc']][mon(e['d'])] += int(e.get('n') or 0)
        all_by_uc[e['uc']].append(e)
    for x in out:
        case_materials = by.get(x['uc'], [])
        ms = [m for m in case_materials if m['cost'] > 0]
        tl = {}
        cumulative = 0
        x['lit_wk'] = ''
        for wk in weeks:
            new = sum(1 for m in ms if mon(m['first']) == wk)
            cost = sum(c for m in case_materials for d_, c in m['days'].items() if mon(d_) == wk)
            cents = round(cost * 100)
            cumulative += cents
            can_light = uc_can_light(cumulative, cents, market_cents.get(wk, 0))
            tl[wk] = {'new': new, 'cost': round(cost), 'share': cost / wk_tot[wk] if wk_tot.get(wk) else 0,
                      'plan': plan_wk[x['uc']].get(wk, 0), 'cumulative': cumulative / 100, 'can_light': can_light}
            if can_light and not x['lit_wk']:
                x['lit_wk'] = wk
        if x['lit_wk']:
            x['st'] = '已点亮'
        x['first_wk'] = mon(x['first']) if x['first'] else ''
        x['tl'] = tl
        # 细分场景按周（Reina 11/17：在路线图里点 use case 展开，下面同样按周分格）
        scl = SCN.get(x['uc'], {}).get('scenes', [])
        x['tl_sc'] = []
        if scl:
            tagd = lambda m: SM.get(m['id']) if SM.get(m['id'], {}).get('uc') == x['uc'] else None
            pw = defaultdict(lambda: defaultdict(int))
            for e in all_by_uc[x['uc']]:
                h = hits(x['uc'], e.get('sc', ''))
                for k, v in (split(int(e.get('n') or 0), h) if h else {0: int(e.get('n') or 0)}).items():
                    pw[k][mon(e['d'])] += v
            grp = [(c['n'], c['t'], c.get('g', ''), c.get('full', ''), [m for m in ms if (tagd(m) or {}).get('s') == c['n']]) for c in scl]
            other = [m for m in ms if not (tagd(m) or {}).get('s')]
            if other or any(pw[0].values()):
                grp.append((0, '没对上场景', '', '名字和字幕看不出场景、库里没有对应场景的素材，以及排期里对不上场景的行', other))
            for n_, t_, g_, f_, mm in grp:
                ltd = sorted(m['lit_day'] for m in mm if m['lit_day'])
                tls = {}
                for wk in weeks:
                    cost = sum(c for m in mm for d_, c in m['days'].items() if mon(d_) == wk)
                    tls[wk] = {'new': sum(1 for m in mm if mon(m['first']) == wk), 'cost': round(cost),
                               'share': cost / wk_tot[wk] if wk_tot.get(wk) else 0, 'plan': pw[n_].get(wk, 0)}
                fst = min((m['first'] for m in mm), default='')
                x['tl_sc'].append({'n': n_, 't': t_, 'g': g_, 'full': f_, 'cnt': len(mm), 'tl': tls,
                                   'cost': sum(m['cost'] for m in mm),
                                   'lit_day': ltd[0] if ltd else '', 'lit_wk': mon(ltd[0]) if ltd else '', 'first_wk': mon(fst) if fst else '',
                                   'lit_mat': next((m['name'] for m in mm if ltd and m['lit_day'] == ltd[0]), '')})
            x['tl_sc'].sort(key=lambda c: -c['cost'])
    prog = []
    for wk in weeks:
        if wk > mon(D):
            break
        prog.append({'wk': wk, 'lit': sum(1 for x in out if x['lit_wk'] and x['lit_wk'] <= wk), 'tested': sum(1 for x in out if x['first_wk'] and x['first_wk'] <= wk),
                     'new_lit': [x['uc'] + ' ' + x['name'] for x in out if x['lit_wk'] == wk], 'new_test': sum(1 for x in out if x['first_wk'] == wk)})
    TL = {'weeks': weeks, 'cur': mon(D), 'prog': prog}

    out.sort(key=lambda x: (-x['cost'], x['uc']))
    cnt = defaultdict(int)
    for x in out:
        cnt[x['st']] += 1
    # 本周排期按分档
    lighting = {'date': D, 'weeks': {x['uc']: x['lit_wk'] for x in out if x['lit_wk']},
                'cost': UC_LIT_COST, 'share_pct': UC_LIT_SHARE_PCT}
    tier_n = {'已点亮': 0, '探索': 0}
    for u, counts in sched.items():
        tier_n['已点亮' if u in lighting['weeks'] else '探索'] += sum(counts.values())
    weak_sched = [x for x in out if x['st'] == '判弱' and x['sched']]
    untested = [x for x in out if x['st'] == '没测']
    near = [x for x in out if x['st'] == '测试中' and 5 <= x['n30'] < 10]

    page = render(out, cnt, D, d30, first_day, wk0, wk1, tier_n, lighting, weak_sched, untested, near, TL)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w').write(page)
    print(json.dumps({'date': D, 'ucs': len(out), 'status': dict(cnt), 'week': wk0, 'sched_by_tier': dict(tier_n)}, ensure_ascii=False))


def fy(v):
    return '¥' + format(int(round(v)), ',')


def render(out, cnt, D, d30, first_day, wk0, wk1, tier_n, lighting, weak_sched, untested, near, TL):
    E = html.escape
    md = lambda s: (str(int(s[5:7])) + '/' + str(int(s[8:10]))) if s else '—'
    uc_rule = f'截至当周累计消耗达到 {fy(UC_LIT_COST)}，且当周消耗占同期全盘高于 {UC_LIT_SHARE_PCT}%'
    STC = {'已点亮': 'st-lit', '测试中': 'st-test', '判弱': 'st-weak', '没测': 'st-none', '储备': 'st-none', '暂不做': 'st-none'}
    CC = {'点亮': 'c-lit', '测过': 'c-test', '偏弱': 'c-weak'}
    def sc_cov(x):
        if not x['scs']:
            return ''
        t = sum(1 for c in x['scs'] if c['cnt'])
        l = sum(1 for c in x['scs'] if c['best'] >= MATERIAL_LIT)
        return f'<span class="scv">场景测过 {t}/{len(x["scs"])}' + (f'，点亮 {l}' if l else '') + '</span>'

    body = []
    for x in out:
        cells = ''
        for t in TYPES:
            c = x['cells'][t]
            if not c:
                cells += '<td class="cell c-none"></td>'
            else:
                tip = f"{t}：花过钱 {c['n']} 条，最好一条 {fy(c['best'])}（{c['best_name']}）"
                cells += f'<td class="cell {CC[c["st"]]}" title="{E(tip)}">{c["n"]}<span class="cb">{E(fy(c["best"]) if c["best"] >= 1000 else "")}</span></td>'
        cs = f"{x['cs_pass']}/{x['cs_n']}" if x['cs_n'] else '—'
        sch = (str(x['sched']) + ('<span class="sub">' + E('、'.join(f'{k} {v}' for k, v in x['sched_t'].items())) + '</span>' if x['sched_t'] else '')) if x['sched'] else ''
        ret = f"{x['ret']:.1%}" if x['ret'] is not None else '—'
        note = f'<span class="sub">{E(x["note"])}</span>' if x['note'] else ''
        best = f'{fy(x["best"])}<span class="sub" title="{E(x["best_name"])}">{E(x["best_name"][:28])}</span>' if x['best'] else '—'
        body.append(
            f'<tr data-uc="{E(x["uc"])}" data-uc-name="{E(x["name"])}"><td><span class="pill {STC[x["st"]]}">{x["st"]}</span></td>'
            f'<td class="uc"><b>{E(x["uc"])}</b> {E(x["name"])}<span class="sub">{E(x["l1"])}{" · " + E(x["pri"]) if x["pri"] else ""}{" · 库里是储备" if x["lib"] == "储备" else ""}</span>{note}</td>'
            f'{cells}'
            f'<td class="num">{x["n"] or ""}<span class="sub">{"近 7 天 +" + str(x["new7"]) if x["new7"] else ""}</span></td>'
            f'<td class="num">{cs}</td>'
            f'<td class="num">{best}</td>'
            f'<td class="num">{fy(x["c30"]) if x["c30"] else "—"}<span class="sub">{x["share30"]:.1%}</span></td>'
            f'<td class="num">{fy(x["cost"]) if x["cost"] else "—"}</td>'
            f'<td class="num">{ret}</td>'
            f'<td class="num">{md(x["first"])}<span class="sub">{"最近 " + md(x["last"]) if x["last"] else ""}</span></td>'
            f'<td class="num" data-plan-count>{sch}</td></tr>')
    # 路线图时间线
    wks, cur = TL['weeks'], TL['cur']
    nxt = (dt.date.fromisoformat(cur) + dt.timedelta(days=7)).isoformat()
    wlab = lambda w: ('本周 ' if w == cur else '下周 ' if w == nxt else '') + md(w) + ' 起'
    lv = lambda sh: 'l4' if sh >= 0.05 else 'l3' if sh >= 0.02 else 'l2' if sh >= 0.005 else 'l1'
    trs = []
    def tl_tds(o, label):
        tds = ''
        for w in wks:
            c = o['tl'][w]
            tip = f"{label} {wlab(w)}，新测 {c['new']} 条，花 {fy(c['cost'])}（占当周大盘 {c['share']:.2%}）"
            if 'cumulative' in c and w <= cur:
                tip += f"，截至该周累计 {fy(c['cumulative'])}"
            if c['plan']:
                tip += f"，排期 {c['plan']} 条"
            if w == o['lit_wk']:
                if o.get('lit_day'):
                    tip += f"，{md(o['lit_day'])} 点亮（{o['lit_mat']} 累计花到 {fy(MATERIAL_LIT)}）"
                else:
                    tip += '，首次同时达标'
            inner = ''
            if w == o['lit_wk']:
                inner += '<span class="star">★</span>'
            if c['new']:
                inner += f'<b>+{c["new"]}</b>'
            if w == o['first_wk']:
                inner += '<span class="tg">首测</span>'
            if c['plan']:
                inner += f'<span class="pl">排 {c["plan"]}</span>'
            if w > cur:
                cls = 'fut' + (' has' if c['plan'] else '')
            elif c['cost'] > 0 or c['new']:
                cls = lv(c['share'])
            else:
                cls = 'emp'
            if w == cur:
                cls += ' cur'
            tds += f'<td class="tc {cls}" data-week="{w}" title="{E(tip)}">{inner}</td>'
        return tds

    for x in out:
        tds = tl_tds(x, x['uc'])
        lit_txt = md(x['lit_wk']) + ' 起' if x['lit_wk'] else ''
        has = bool(x.get('tl_sc'))
        row_class = ' class="ucr"' if has else ''
        caret = '<i class="car">▸</i>' if has else ''
        trs.append(f'<tr{row_class} data-uc="{E(x["uc"])}"><td><span class="pill {STC[x["st"]]}">{x["st"]}</span></td>'
                   f'<td class="uc">{caret}<b>{E(x["uc"])}</b> {E(x["name"])}{sc_cov(x)}<span class="sub">{E(x["l1"])}</span></td>{tds}'
                   f'<td class="num">{fy(x["cost"]) if x["cost"] else "—"}</td><td class="num">{lit_txt}</td></tr>')
        g0 = None
        for c in x.get('tl_sc', []):
            st = '其他' if c['n'] == 0 else ('点亮' if c['lit_day'] else ('测过' if c['cnt'] else '没测'))
            cls = {'点亮': 'st-lit', '测过': 'st-test', '没测': 'st-none', '其他': 'st-none'}[st]
            gl = f'<span class="sg">{E(c["g"])}</span>' if c['g'] and c['g'] != g0 else ''
            g0 = c['g'] or g0
            num = f'<b>{c["n"]}</b> ' if c['n'] else ''
            trs.append(f'<tr class="scr" data-for="{E(x["uc"])}" data-scene="{c["n"]}" hidden><td><span class="pill sm {cls}">{st}</span></td>'
                       f'<td class="uc sc">{gl}{num}<span data-scene-label title="{E(c["full"])}">{E(c["t"])}</span><span class="sub">{"花过钱 " + str(c["cnt"]) + " 条" if c["cnt"] else ""}</span></td>'
                       f'{tl_tds(c, x["uc"] + " " + (str(c["n"]) + " " if c["n"] else "") + c["t"])}'
                       f'<td class="num">{fy(c["cost"])}</td><td class="num">{md(c["lit_day"]) if c["lit_day"] else ""}</td></tr>')
    th_w = ''.join(f'<th class="tc{" cur" if w == cur else ""}" data-week="{w}">{E(wlab(w))}</th>' for w in wks)
    prog = TL['prog']
    n_all = len(out)
    nP = len(prog)
    VW, L, R, T, B = 1200, 46, 12, 26, 52
    PH = 230
    slot = (VW - L - R) / max(nP, 1)
    bw = min(64, slot * 0.46)
    ymax = max(n_all, 1)
    ys = ymax * 1.12
    yy = lambda v: T + PH - v / ys * PH
    sv = [f'<svg class="pgsvg" viewBox="0 0 {VW} {T + PH + B}" role="img" aria-label="每周累计点亮和测过的 use case 数">']
    for g in range(0, ymax + 1, 10):
        sv.append(f'<line class="gl" x1="{L}" x2="{VW - R}" y1="{yy(g):.1f}" y2="{yy(g):.1f}"/><text class="ax" x="{L - 8}" y="{yy(g) + 4:.1f}" text-anchor="end">{g}</text>')
    sv.append(f'<line class="tot" x1="{L}" x2="{VW - R}" y1="{yy(n_all):.1f}" y2="{yy(n_all):.1f}"/><text class="ax" x="{VW - R}" y="{yy(n_all) - 6:.1f}" text-anchor="end">库里一共 {n_all} 个 use case</text>')
    for i, p in enumerate(prog):
        cx = L + slot * (i + 0.5)
        x0 = cx - bw / 2
        lit, tst = p['lit'], p['tested']
        sv.append(f'<rect class="bt" x="{x0:.1f}" y="{yy(tst):.1f}" width="{bw:.1f}" height="{yy(0) - yy(tst):.1f}" rx="3"/>')
        if lit:
            sv.append(f'<rect class="bl" x="{x0:.1f}" y="{yy(lit):.1f}" width="{bw:.1f}" height="{yy(0) - yy(lit):.1f}"/>')
            if yy(0) - yy(lit) >= 18:
                sv.append(f'<text class="vl" x="{cx:.1f}" y="{yy(lit) + 15:.1f}" text-anchor="middle">{lit}</text>')
        sv.append(f'<text class="vt" x="{cx:.1f}" y="{yy(tst) - 6:.1f}" text-anchor="middle">{tst}</text>')
        we = (dt.date.fromisoformat(p['wk']) + dt.timedelta(days=6)).isoformat()
        lab = md(p['wk']) + '–' + md(we)
        cc = ' cur' if p['wk'] == cur else ''
        sv.append(f'<text class="xl{cc}" x="{cx:.1f}" y="{T + PH + 20}" text-anchor="middle">{"本周 " if p["wk"] == cur else ""}{lab}</text>')
        sv.append(f'<text class="xs" x="{cx:.1f}" y="{T + PH + 38}" text-anchor="middle">新点亮 {len(p["new_lit"])}　新测 {p["new_test"]}</text>')
    sv.append('</svg>')
    cols = ''.join(
        f'<div class="pc{" cur" if p["wk"] == cur else ""}"><b>这周新点亮</b>'
        + (''.join(f'<span>{E(n)}</span>' for n in p['new_lit']) or '<span class="mu">没有新点亮</span>') + '</div>' for p in prog)
    pg = ''.join(sv) + f'<div class="pcols" style="grid-template-columns: repeat({nP}, 1fr); margin-left: {L / VW * 100:.2f}%; margin-right: {R / VW * 100:.2f}%">{cols}</div>'
    latest_qualified = sum(x['tl'][cur]['can_light'] for x in out)
    latest_new = len(prog[-1]['new_lit'])
    tl_html = f'''
  <section class="card" id="roadmap">
    <h2>路线图：每周测了什么、哪周点亮</h2>
    <h3>点亮进度（累计 use case 数）</h3>
    <div class="lgd"><span><i style="background:#2f8f5b"></i>到这周为止已点亮（柱内数字）</span><span><i style="background:#cfe5d7"></i>测过、还没点亮（柱顶数字是测过的总数）</span><span>横轴是周（周一到周日），「新测」是这周第一次花钱的 use case 数</span></div>
    <div class="prog">{pg}</div>
    <p class="note">首次同时达到两项条件的周记为点亮周。{md(cur)}–{md(D)} 有 {latest_qualified} 个 use case 同时达标，其中 {latest_new} 个首次点亮。</p>
    <h3>每个 use case 每周</h3>
    <div class="lgd"><span><i style="background:#2f8f5b"></i>当周花费占大盘 ≥ 5%</span><span><i style="background:#6fb38c"></i>2–5%</span><span><i style="background:#b9dcc6"></i>0.5–2%</span><span><i style="background:#e6f1ea"></i>有花费，不到 0.5%</span><span>★ 这周点亮</span><span>+N 这周新测（第一次花钱）的条数</span><span>「排 N」排期看板这周排的条数，虚线框是还没到的周</span></div>
    <p class="note"><b>点一行 use case 展开它的细分场景</b>（Use case 库里的场景），每个场景一行、同样按周分格：哪周新测了几条、花了多少、哪周点亮、排了几条。<button type="button" class="tgl" id="scall">全部展开</button></p>
    <div class="rmwrap"><table class="rm tl">
      <thead><tr><th>状态</th><th>use case</th>{th_w}<th class="num">累计消耗</th><th class="num">首次点亮</th></tr></thead>
      <tbody>{''.join(trs)}</tbody>
    </table></div>
    <p class="note">Use case 和展开后的细分场景都按累计消耗从高到低排列，消耗统计覆盖 {md(first_day)}–{md(D)}。排期从 11/3 那周开始有记录。</p>
  </section>'''

    tsum = sum(tier_n.values())
    tier_line = '、'.join(f'{E(g)} {n} 条（{n / tsum:.0%}）' for g, n in tier_n.items()) if tsum else '这周还没有排期'
    lighting_json = json.dumps(lighting, ensure_ascii=False).replace('</', '<\\/')
    lst = lambda v: '、'.join(f'{E(x["uc"])} {E(x["name"])}' for x in v) or '无'
    src = open(os.path.join(ROOT, 'topic', '2026-11-17-coldstart-threshold', 'index.html')).read()
    STYLE = src[src.find('<style>'):src.find('</head>')]
    EXTRA = '''<style>
  .wk .rm { border-collapse: collapse; width: 100%; font-size: var(--cds-font-size-caption); }
  .wk .rm th, .wk .rm td { padding: 6px 8px; border-bottom: 1px solid var(--color-border-line); vertical-align: top; text-align: left; }
  .wk .rmwrap { overflow: visible; }
  .wk .rm thead th { position: sticky; top: 0; background: var(--color-panel); z-index: 3; font-weight: 600; white-space: nowrap; box-shadow: 0 1px 0 var(--color-border-line); }
  .wk .tl td:nth-child(1), .wk .tl th:nth-child(1) { position: sticky; left: 0; background: var(--color-panel); z-index: 2; width: 4.6rem; min-width: 4.6rem; }
  .wk .tl td:nth-child(2), .wk .tl th:nth-child(2) { position: sticky; left: 4.6rem; background: var(--color-panel); z-index: 2; box-shadow: 1px 0 0 var(--color-border-line); }
  .wk .tl thead th:nth-child(1), .wk .tl thead th:nth-child(2) { z-index: 4; }
  .wk .rm td.num, .wk .rm th.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .wk .rm .sub { display: block; color: var(--color-fg-muted); font-size: 11px; font-weight: 400; max-width: 16rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wk .rm td.num .sub { margin-left: auto; }
  .wk .rm td.uc { min-width: 12rem; }
  .wk .rm tr.grp td { background: var(--color-bg); font-weight: 600; font-size: var(--cds-font-size-caption); }
  .wk .rm td.cell { text-align: center; min-width: 4.2rem; font-weight: 600; font-variant-numeric: tabular-nums; border-left: 2px solid var(--color-bg, #fff); }
  .wk .rm td.cell .cb { display: block; font-size: 10px; font-weight: 400; opacity: .8; }
  .wk .c-lit { background: #2f8f5b; color: #fff; }
  .wk .c-test { background: #dcebe1; color: #1f5f3c; }
  .wk .c-weak { background: #f3d9d4; color: #9a3324; }
  .wk .c-none { background: transparent; }
  .wk .pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .wk .st-lit { background: #2f8f5b; color: #fff; }
  .wk .st-test { background: #dcebe1; color: #1f5f3c; }
  .wk .st-weak { background: #f3d9d4; color: #9a3324; }
  .wk .st-none { background: #ece9e1; color: #6b665c; }
  .wk .kp { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: var(--cds-gap-sm) 0; }
  .wk .kp span { font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
  .wk .kp b { display: block; font-size: 22px; color: var(--color-fg); font-variant-numeric: tabular-nums; }
  .wk .lgd { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); margin: var(--cds-gap-sm) 0; }
  .wk .lgd i { display: inline-block; width: 14px; height: 12px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  .wk .tl td.tc, .wk .tl th.tc { text-align: center; min-width: 4.4rem; padding: 4px 3px; border-left: 2px solid var(--color-bg, #fff); white-space: nowrap; }
  .wk .tl th.tc { font-size: 11px; }
  .wk .tl td.tc b { font-size: 12px; }
  .wk .tl td.tc .star { color: #c98a00; font-size: 14px; margin-right: 2px; }
  .wk .tl td.tc .tg { display: block; font-size: 10px; opacity: .75; }
  .wk .tl td.tc .pl { display: block; font-size: 10px; opacity: .85; }
  .wk .tl .l4 { background: #2f8f5b; color: #fff; } .wk .tl .l3 { background: #6fb38c; color: #fff; }
  .wk .tl .l2 { background: #b9dcc6; color: #1f5f3c; } .wk .tl .l1 { background: #e6f1ea; color: #1f5f3c; }
  .wk .tl .emp { background: transparent; }
  .wk .tl .fut { background: transparent; color: var(--color-fg-muted); }
  .wk .tl .fut.has { outline: 1.5px dashed #6fb38c; outline-offset: -4px; color: #1f5f3c; }
  .wk .tl th.cur, .wk .tl td.cur { box-shadow: inset 0 0 0 2px #c98a00; }
  .wk .tl thead th.cur { box-shadow: inset 0 0 0 2px #c98a00, 0 1px 0 var(--color-border-line); }
  .wk .prog { margin: 6px 0 4px; }
  .wk .pgsvg { display: block; width: 100%; height: auto; }
  .wk .pgsvg .gl { stroke: var(--color-border-line); stroke-width: 1; }
  .wk .pgsvg .tot { stroke: var(--color-fg-muted); stroke-dasharray: 4 4; stroke-width: 1; }
  .wk .pgsvg .ax { fill: var(--color-fg-muted); font-size: 12px; }
  .wk .pgsvg .bt { fill: #cfe5d7; } .wk .pgsvg .bl { fill: #2f8f5b; }
  .wk .pgsvg .vl { fill: #fff; font-size: 13px; font-weight: 700; }
  .wk .pgsvg .vt { fill: var(--color-fg); font-size: 13px; font-weight: 600; }
  .wk .pgsvg .xl { fill: var(--color-fg); font-size: 13px; font-weight: 600; }
  .wk .pgsvg .xl.cur { fill: #b07800; }
  .wk .pgsvg .xs { fill: var(--color-fg-muted); font-size: 11.5px; }
  .wk .pcols { display: grid; gap: 6px; font-size: 11.5px; line-height: 1.5; }
  .wk .pc { display: flex; flex-direction: column; border-top: 2px solid #2f8f5b; padding-top: 4px; min-width: 0; }
  .wk .pc.cur { border-top-color: #c98a00; }
  .wk .pc b { font-size: 11px; color: var(--color-fg-muted); font-weight: 600; }
  .wk .pc span { color: var(--color-fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wk .pc .mu { color: var(--color-fg-muted); }
  .wk tr.ucr { cursor: pointer; }
  .wk tr.ucr:hover td { background: color-mix(in srgb, var(--color-fg) 4%, transparent); }
  .wk tr.ucr:hover td.cell { background: revert-layer; }
  .wk .car { display: inline-block; width: 1em; font-style: normal; color: var(--color-fg-muted); transition: transform .15s; }
  .wk tr.ucr.open .car { transform: rotate(90deg); }
  .wk .scv { display: block; font-size: 11px; color: #2f8f5b; font-weight: 600; }
  .wk .tl tr.scr td { padding-top: 3px; padding-bottom: 3px; }
  .wk .tl tr.scr td:nth-child(1), .wk .tl tr.scr td:nth-child(2) { background: var(--color-bg); }
  .wk .tl tr.scr td.uc { padding-left: 1.6rem; font-size: 12px; font-weight: 400; }
  .wk .tl tr.scr td.tc { font-size: 11px; }
  .wk .tl tr.ucr.open td { border-bottom-color: transparent; }
  .wk .pill.sm { font-size: 10px; padding: 0 6px; }
  .wk .sg { display: block; font-size: 10.5px; color: var(--color-fg-muted); margin-top: 2px; }
  .wk .tgl { margin-left: 8px; font: inherit; font-size: 12px; padding: 2px 10px; border: 1px solid var(--color-border-line); border-radius: 12px; background: var(--color-panel); color: var(--color-fg); cursor: pointer; }
  .wk .def { margin: var(--cds-gap-sm) 0 0; padding: 10px 14px; background: color-mix(in srgb, #2f8f5b 10%, var(--color-panel)); color: var(--color-fg); border-left: 3px solid #2f8f5b; border-radius: 4px; font-size: var(--cds-font-size-caption); line-height: 1.7; }
</style>'''
    th_types = ''.join(f'<th class="num" style="text-align:center">{E(t)}</th>' for t in TYPES)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>点亮路线图 · 投放素材</title>
{STYLE}
{EXTRA}
</head>
<body>
<div class="wrap">
<div class="topic-top">
  <nav class="lx-nav" aria-label="日报、周报、排期和专题">
    <div class="lx-navrow"><span class="lx-nav-label">日报</span><span class="lx-chips"><a class="lx-chip" href="../">最新日报</a></span></div>
    <div class="lx-navrow"><span class="lx-nav-label">周报</span><span class="lx-chips"><a class="lx-chip" href="../week/">最新周报</a></span></div>
    <div class="lx-navrow"><span class="lx-nav-label">排期</span><span class="lx-chips"><a class="lx-chip" href="../schedule/">素材排期</a><a class="lx-chip" href="../output/">素材产出</a><a class="lx-chip" aria-current="page" href="./">点亮路线图</a></span></div>
    <div class="lx-navrow"><span class="lx-nav-label">专题</span><span class="lx-chips"><a class="lx-chip" href="../topic/">专题分析</a></span></div>
  </nav>
</div>
<div class="wk">
  <header>
    <h1>点亮路线图：每个 use case 什么时候测、什么时候点亮、接下来排了什么</h1>
    <p class="sub">数据 {md(first_day)}–{md(D)}（投放数据_分日，两端合计），一行一个 use case（Use case 库里在用和储备的）。</p>
    <p class="def"><b>Use case 点亮</b>需要{uc_rule}。累计从 {md(first_day)} 起算，首次同时达标的周标 ★。每周从周一算到周日，尚未结束的周统计到数据截止日。</p>
  </header>

  <section class="card sum" id="summary">
    <h2>总览</h2>
    <div class="kp">
      <span><b>{cnt.get('已点亮', 0)}</b>已点亮</span><span><b>{cnt.get('测试中', 0)}</b>测试中</span><span><b>{cnt.get('判弱', 0)}</b>判弱</span>
      <span><b>{cnt.get('没测', 0)}</b>没测</span><span><b>{cnt.get('储备', 0) + cnt.get('暂不做', 0)}</b>储备 / 暂不做</span>
    </div>
    <ul>
      <li id="week-plan-summary"><b>本周已排 {tsum} 条（{md(wk0)}–{md(wk1)}）</b>，<span>{tier_line}</span>。</li>
      <li><b>判弱但这周还在排的：</b><span id="week-plan-weak">{lst(weak_sched)}</span>。这些方向近 30 天至少有 10 条素材产生消耗，单条最高累计消耗低于 {fy(MATERIAL_LIT)}。</li>
      <li><b>测试中、近 30 天有 5–9 条素材产生消耗的：</b>{lst(near)}。</li>
      <li><b>库里在用、还没测过的：</b>{lst(untested)}。新方向的候选。</li>
    </ul>
    <p class="note" data-plan-status hidden>暂时读不到最新排期，显示上次发布的数量。</p>
  </section>

{tl_html}

  <section class="card" id="map">
    <h2>use case × 素材类型</h2>
    <div class="lgd"><span><i style="background:#2f8f5b"></i>素材类型格点亮需要一条素材累计花到 {fy(MATERIAL_LIT)}</span><span><i style="background:#dcebe1"></i>测过，还没点亮</span><span><i style="background:#f3d9d4"></i>偏弱：花过钱的 ≥ 10 条、都没到 {fy(MATERIAL_LIT)}</span><span><i style="background:#ece9e1"></i>空白：这类没测过</span></div>
    <p class="note">格子里大字是花过钱的素材条数，小字是最好一条的累计花费（¥1,000 以上才写），鼠标放上去看素材名。过冷启 = 上传当天 + 后 2 天花到 ¥400，分母是上传日在 {md(first_day)} 以后、窗口已过完的素材。次留率是近 30 天的，激活不到 100 不写。累计消耗覆盖 {md(first_day)}–{md(D)}。本周已排与素材排期看板同口径，剔除建议拿掉和顺延的条目，小字是 AI / 二创各几条。</p>
    <div class="rmwrap"><table class="rm">
      <thead><tr><th>状态</th><th>use case</th>{th_types}<th class="num">花过钱的素材</th><th class="num">过冷启</th><th class="num">最好一条</th><th class="num">近 30 天消耗</th><th class="num">累计消耗</th><th class="num">次留率</th><th class="num">第一次测</th><th class="num">本周已排</th></tr></thead>
      <tbody>{''.join(body)}</tbody>
    </table></div>
  </section>

  <section class="card" id="rule">
    <h2>口径</h2>
    <ul class="take">
      <li>Use case 的点亮周取第一次满足「{uc_rule}」的周。分母是同期两端合计的全盘消耗。</li>
      <li>已产生消耗且待点亮的方向继续测试。判弱的条件是近 30 天至少有 10 条素材产生消耗，且最佳单条累计消耗低于 {fy(MATERIAL_LIT)}。</li>
      <li>素材类型：AI 原片；AI 二剪和重拍（AI 短剧的只剪辑、换开头、全片重配、AI 重拍）；达人原片（KOC、KOL 原片）；达人二剪（KOC、KOL 的二剪、只剪辑、换开头、全片重配）；星广和自建号（唯西星广、知定堂星广、星图、唯西自建号）。客供和还没对上 use case 的素材不进格子。</li>
      <li>use case 归属和日报一致（UC_ID 列，待对应的按 tools/uc_resolve.py 补）。</li>
      <li>细分场景的归属来自 notes/scene-map.json，日报每天给新素材打标。场景里有一条素材累计花到 {fy(MATERIAL_LIT)} 即点亮。「排 N」按排期里写的细分场景和库里的场景文字匹配，一行写了几个场景就平分条数。未匹配到场景的素材和排期计入「没对上场景」。</li>
    </ul>
  </section>
</div>
</div>
<script>
(function(){{
  function tog(tr, open){{
    var u = tr.getAttribute('data-uc'), rs = document.querySelectorAll('tr.scr[data-for="' + u + '"]');
    if(!rs.length) return;
    if(open === undefined) open = rs[0].hidden;
    rs.forEach(function(r){{ r.hidden = !open; }}); tr.classList.toggle('open', open);
  }}
  document.querySelectorAll('tr.ucr').forEach(function(tr){{ tr.addEventListener('click', function(){{ tog(tr); }}); }});
  var b = document.getElementById('scall'), all = false;
  if(b) b.addEventListener('click', function(){{ all = !all; document.querySelectorAll('tr.ucr').forEach(function(tr){{ tog(tr, all); }}); b.textContent = all ? '全部收起' : '全部展开'; }});
}})();
</script>
<script id="roadmap-lighting" type="application/json">{lighting_json}</script>
<script type="module" src="../tools/roadmap_plan_live.js?v=3"></script>
</body>
</html>
'''


if __name__ == '__main__':
    main()
