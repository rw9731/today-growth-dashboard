"""出当天的排期看板，更新 schedules.json。

用法（在仓库根目录）：
  python3 tools/schedule_data.py --sheet <分日文件> --date D --out-dir /tmp/sched
  python3 tools/schedule_build.py --data-dir /tmp/sched --date T [--progress /tmp/sched/progress.json]

写 schedule/T/index.html、schedules.json；T 是最新一天时同时写 schedule/index.html。
排期内容只从 tools/schedule_plan.json 读，use case 名字从 tools/ucs.json 读，页面骨架是 tools/schedule_template.html。
标了 schedule-source=manual 的页面（11/4 那版）不覆盖，要覆盖加 --force。
"""
import argparse, datetime as dt, html, json, os, re, sys
from collections import defaultdict

from schedule_data import STABLE, flow, total_warn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK = '一二三四五六日'
SUB_KEYS = [('接娃和班级群', 'PS03'), ('消息排清单', '微信'), ('孩子的具体问题', '孩子')]

NAV_CSS = """html,body{margin:0}
[hidden]{display:none!important}
.sx-nav{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:8px 12px;margin-bottom:12px;border:1px solid var(--grid);border-radius:12px;background:var(--panel);font-size:13px;min-width:0}
.sx-nav [hidden]{display:none}
.sx-back{color:var(--ink);text-decoration:none;font-weight:600;white-space:nowrap;padding-right:8px;margin-right:2px;border-right:1px solid var(--grid)}
.sx-back:hover{color:var(--link)}
.sx-lab{font-weight:600;min-width:34px}
.sx-chips{display:flex;flex-wrap:wrap;gap:6px;min-width:0}
.sx-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;border:1px solid var(--grid);color:var(--ink);text-decoration:none;font-variant-numeric:tabular-nums;white-space:nowrap}
.sx-chip:hover{border-color:var(--mute)}
.sx-chip[aria-current="page"]{background:var(--ink);border-color:var(--ink);color:var(--bg);font-weight:600}
.sx-chip .new{font-size:11px;font-weight:600;color:var(--good)}
.sx-chip[aria-current="page"] .new{color:inherit;opacity:.7}
.sx-nav select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--grid);border-radius:999px;padding:5px 10px;max-width:100%}
.prog{color:var(--sub);font-size:12px;margin:4px 0 0;max-width:112ch}
.prog summary{cursor:pointer}"""

NAV_HTML = """<nav class="sx-nav" aria-label="素材看板和往期排期">
<a class="sx-back" href="{rel}">← 素材看板</a>
<span class="sx-lab">排期</span>
<span class="sx-chips" id="sx-chips"><a class="sx-chip" aria-current="page" href="{rel}schedule/{date}/">{label}</a></span>
<select id="sx-more" aria-label="更早的排期" hidden></select>
</nav>"""

NAV_JS = """<script>
(async()=>{{
  const REL='{rel}',CUR='{date}';
  let list=[];
  try{{list=await(await fetch(REL+'schedules.json',{{cache:'no-store'}})).json()}}catch(e){{return}}
  if(!Array.isArray(list)||!list.length)return;
  list.sort((a,b)=>a.date<b.date?1:-1);
  const hrefOf=r=>REL+'schedule/'+r.date+'/';
  const shown=list.slice(0,7);
  if(!shown.some(r=>r.date===CUR)){{const c=list.find(r=>r.date===CUR);if(c)shown.push(c)}}
  document.getElementById('sx-chips').replaceChildren(...shown.map(r=>{{
    const a=document.createElement('a');a.className='sx-chip';a.href=hrefOf(r);a.textContent=r.label;
    if(r.date===CUR)a.setAttribute('aria-current','page');
    if(r===list[0]){{const s=document.createElement('span');s.className='new';s.textContent='最新';a.appendChild(s)}}
    return a;
  }}));
  const rest=list.filter(r=>!shown.includes(r));
  if(rest.length){{
    const sel=document.getElementById('sx-more');
    const head=document.createElement('option');head.value='';head.textContent='更早 '+rest.length+' 天';
    sel.replaceChildren(head,...rest.map(r=>{{const o=document.createElement('option');o.value=hrefOf(r);o.textContent=r.label;return o}}));
    sel.hidden=false;
    sel.addEventListener('change',()=>{{if(sel.value)location.href=sel.value}});
  }}
}})();
</script>"""


def date(s):
    return dt.date.fromisoformat(s)


def md(d):
    return f'{d.month}/{d.day}'


def full_range(a, b):
    return f'{md(a)}–{md(b)}'


def short_range(a, b):
    return f'{md(a)}–{b.day}' if a.month == b.month else full_range(a, b)


def label(d):
    return f'{md(d)} 周{WEEK[d.weekday()]}'


def dec(s):
    """spend.json 的桶：¥10 为单位；无逗号 = 只有第一桶，值后面补一个 0。"""
    out = []
    for x in s.split(';'):
        if x == '':
            out.append([0, 0, 0, 0])
        elif ',' not in x:
            out.append([int(x + '0') * 10, 0, 0, 0])
        else:
            out.append([int(v) * 10 for v in x.split(',')])
    return out


def spend_row(R):
    return dict(c7=R[0], rate=R[1], cpr=R[2], a=R[3], n=[int(x) for x in R[4].split(',')], s=dec(R[5]))


def load_spend(S):
    """表里 PS03 一行放合计，三部分只写进执行细节。"""
    dec_run = lambda t: [[int(v) for v in day.split(',')] for day in t.split(';')]
    dec_ret = lambda t: [[int(v) for v in day.split(',')] if day else [0] * 8 for day in t.split(';')]
    U = {u: spend_row(R) for u, R in S['U'].items()}
    for u, x in U.items():
        if u in S.get('run', {}):
            x['k'] = dec_run(S['run'][u])
        if u in S.get('ret', {}):
            x['rt'] = dec_ret(S['ret'][u])
    parts = {k: U.pop(k, None) for _, k in SUB_KEYS}
    if S.get('merged', {}).get('PS03'):
        U['PS03'] = spend_row(S['merged']['PS03'])
        if S.get('run_merged', {}).get('PS03'):
            U['PS03']['k'] = dec_run(S['run_merged']['PS03'])
        if S.get('ret_merged', {}).get('PS03'):
            U['PS03']['rt'] = dec_ret(S['ret_merged']['PS03'])
    total = dict(c7=S['t7'], rate=S['rate'], cpr=S['cpr'], n=[int(x) for x in S['T']['n'].split(',')], s=dec(S['T']['s']))
    if S['T'].get('k'):
        total['k'] = dec_run(S['T']['k'])
    if S['T'].get('ret'):
        total['rt'] = dec_ret(S['T']['ret'])
    return U, total, parts


def ps03_note(parts, suffix):
    bits = [f"{n} ¥{parts[k]['c7'] / 10000:.1f}万、{parts[k]['rate']}%、¥{parts[k]['cpr']}" for n, k in SUB_KEYS if parts.get(k)]
    if not bits:
        return {}
    return {'PS03': '；'.join(bits) + (('。' + suffix) if suffix else '')}


def view_entries(plan, U, days, D, T):
    """这一天页面上的排期条目。
    已上线的从数据算（当周、当天第一次花钱）；已交没花钱的挪到今天，排期写定之后上线的条数扣掉；
    过了日子还没交的不再算进后面的供给，看进度那一行。"""
    mon = T - dt.timedelta(days=T.weekday())
    sun = mon + dt.timedelta(days=6)
    asof = date(plan['asof'])
    out, pending = [], defaultdict(list)
    for u, x in U.items():
        for d, n in zip(days, x['n']):
            if n and mon <= d <= D:
                out.append(dict(uc=u, d=md(d), g='', t='', n=n, s='live', src='', link='', to='', w=1))
    for e in plan['E']:
        d = date(e['d'])
        if d < T:
            if e['s'] == 'done' and d >= mon:
                pending[e['uc']].append(e)
            continue
        if d <= T + dt.timedelta(days=4):
            out.append({**e, 'd': md(d), 'w': int(d <= sun)})
    for u, es in pending.items():
        went_live = sum(n for d, n in zip(days, U[u]['n']) if asof <= d <= D) if u in U else 0
        for e in sorted(es, key=lambda x: x['d']):
            k = min(e['n'], went_live)
            went_live -= k
            if e['n'] > k:
                out.append({**e, 'n': e['n'] - k, 'd': md(T), 'w': 1})
    return out


def batch_view(R, groups):
    """看板用的批次数：PS03 合成一行，再加全盘。[条数, 跑起来, 第二天合计消耗]"""
    raw = R.get('batch', {})
    keys = [k for _, k in SUB_KEYS]
    def add(into, src):
        for d, v in src.items():
            x = into.setdefault(d, [0, 0, 0])
            for i in range(3):
                x[i] += v[i]
    B = {u: dict(v) for u, v in raw.items() if u not in keys}
    B['PS03'] = {}
    B['__all'] = {}
    for k in keys:
        add(B['PS03'], raw.get(k, {}))
    for v in raw.values():
        add(B['__all'], v)
    return B


def batch_detail(R):
    """点开柱子看的每批素材：PS03 合成一行，配上片子链接。"""
    raw = R.get('batch_items', {})
    keys = [k for _, k in SUB_KEYS]
    links = json.load(open(os.path.join(ROOT, 'tools', 'links.json'), encoding='utf-8'))
    url = lambda i: (lambda x: x.get('link') or x.get('video') or x.get('jl') or '')(links.get(i, {}))
    out = {u: dict(v) for u, v in raw.items() if u not in keys}
    out['PS03'] = {}
    for k in keys:
        for d, v in raw.get(k, {}).items():
            x = out['PS03'].setdefault(d, dict(c0=0, a0=0, r0=0, at=0, rt=0, items=[]))
            for f in ('c0', 'a0', 'r0', 'at', 'rt'):
                x[f] += v.get(f, 0)
            x['items'] += v['items']
    for u in out:
        for v in out[u].values():
            v['items'] = [it[1:] + [url(it[0])] for it in sorted(v['items'], key=lambda it: -it[4])]
    return out


def why_rows(why, notes, B, names, total, days):
    """回收那一节的表：前天首花这批，每批一行，从 notes/batches.json 取。"""
    if not why:
        return why
    day = why['day']
    i = len(days) - 1
    run = sum(total['k'][i]) if total.get('k') else 0
    avg = sum(total['s'][i]) / run if run else 0
    rows = []
    for k, e in notes.items():
        u, d = k.split('|')
        v = B.get(u, {}).get(d)
        if d != day or not v or v[0] < 3:
            continue
        per = v[2] / v[0]
        rows.append(dict(label=f"{names.get(u, '')} {u}".strip(), color='green' if per >= avg else 'red', n=v[0], k=v[1], per=round(per), why='\n'.join(x for x in (e.get('good'), e.get('bad')) if x), next=e.get('next', '')))
    if rows:
        rows.sort(key=lambda r: (r['color'] != 'red', -r['n']))
        why = {**why, 'rows': rows}
    why.setdefault('rows', [])
    return why


def load_batch_notes():
    """每批的内容和操作分析。notes/batches.json，键是「UC|MM-DD」，全盘当天的操作写在「__day|MM-DD」。"""
    p = os.path.join(ROOT, 'notes', 'batches.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def batch_line(B, groups, D, total, days):
    """页面顶部一句：前天首花的这批，第二天（昨天）每条花了多少，和当天大盘平均每条比。"""
    day = (D - dt.timedelta(days=1)).strftime('%m-%d')
    i = len(days) - 1
    run = sum(total['k'][i]) if total.get('k') else 0
    avg = sum(total['s'][i]) / run if run else 0
    listed = {u for g in groups for u in g[1]}
    rows = []
    for gi, g in enumerate(groups):
        us = list(g[1]) + ([u for u in B if u not in listed and not u.startswith('__')] if gi == len(groups) - 1 else [])
        pick = lambda j: sum(B.get(u, {}).get(day, [0, 0, 0])[j] for u in us)
        n = pick(0)
        if not n:
            continue
        rows.append(dict(g=g[0], n=n, k=pick(1), per=round(pick(2) / n), x=round(pick(2) / n / avg, 1) if avg else None))
    return dict(day=day, avg=round(avg), rows=rows) if rows else None


# 分档的线（Reina 11/5 问，见 claude/usecase-tiers-1104.md）
UP_SH, UP_D5, UP_TOP, UP_NB, UP_GAP = 5, 5, 33, 2, 1.5
COST_OK = 3  # 成本差 ¥3 以内算和全盘差不多，和页面标色一致。第一档占全盘一半以上，卡死 ≤全盘就是 ¥1 定档
IN_ACT, IN_GAP = 100, 3


def tier_view(R, groups, total, plan, T):
    """每个 use case 悬停时显示的分档信息：现在哪一档，到下一档还差什么。"""
    raw = R.get('tier', {})
    gl = raw.get('__gl', {})
    moved = plan.get('MOVED', {})
    out = {}
    for gi, g in enumerate(groups):
        for u in g[1]:
            t = raw.get(u)
            if not t:
                continue
            x = dict(g=gi, sh=t['sh'], d5=t['d5'], top=t['top'], nb=t['nb'])
            w7, w14 = t['w7'], t['w14']
            if gi < 2:
                x.update(rate=w7['rate'], cpr=w7['cpr'])
                x['can'] = gi == 1 and t['sh'] >= UP_SH and t['d5'] >= UP_D5 and t['top'] <= UP_TOP and t['nb'] >= UP_NB and w7['rate'] is not None and w7['rate'] >= total['rate'] - UP_GAP and (w7['cpr'] or 999) <= total['cpr'] + COST_OK
            else:
                ok = lambda w, k: w['a'] >= IN_ACT and w['gap'] is not None and w['gap'] >= IN_GAP and (w['cpr'] or 999) <= gl.get(k, {}).get('cpr', 0) + COST_OK
                k = 'w14' if ok(w14, 'w14') and not ok(w7, 'w7') else 'w7'
                w = t[k]
                x.update(win=7 if k == 'w7' else 14, a=w['a'], rate=w['rate'], cpr=w['cpr'], gap=w['gap'], gc=gl.get(k, {}).get('cpr', 0) + COST_OK, can=ok(w, k))
            if u in moved:
                d = date(moved[u]['d'])
                x['from'] = moved[u]['from']
                x['md'] = md(d)
                x['fresh'] = (T - d).days <= 7
            out[u] = x
    return dict(U=out, up=dict(sh=UP_SH, d5=UP_D5, top=UP_TOP, nb=UP_NB, gap=UP_GAP), inn=dict(act=IN_ACT, gap=IN_GAP))


def rule_rows(RU, U, E, GL, W, T):
    """每个 use case 的交界点和条数建议。条数建议的阈值是初值，Reina 11/4 定先跑 1–2 周。
    """
    days = [T + dt.timedelta(days=i) for i in range(len(W))]
    X = {}
    for u, x in RU.items():
        if u not in U:
            continue
        launches = {'AI': defaultdict(int), '二创': defaultdict(int)}
        for e in E:
            if e['uc'] == u and e['d'] in W and e['s'] in ('done', 'todo', 'add'):
                m, d = e['d'].split('/')
                when = dt.date(T.year, int(m), int(d))
                # 已交的今天算首花，待交的交付第二天算首花：产出到首花 48% 当天、32% 隔天（首花 10/28 起）
                launches['AI' if e['t'] == 'AI' else '二创'][T if e['s'] == 'done' else max(T, when + dt.timedelta(days=1))] += e['n']
        f = flow(x, GL['yt'], GL['t0'], launches, days)
        mult = x['y'] / GL['y'] if GL['y'] else 0
        mx = x['yx'] / GL['y'] if GL['y'] else 0
        dens = x['np'] / x['sh'] if x['sh'] else 0
        if x['n'] < 5:
            tag = '不判'
        elif mult >= 1.3 and mx >= .8:
            tag = '加'
        elif mult >= .8 and (mx < .6 or x['top'] >= .6):
            tag = '靠一条'
        elif mult < .6 and dens >= 1:
            tag = '减'
        else:
            tag = '持平'
        X[u] = dict(mult=round(mult, 1), mx=round(mx, 1), n=x['n'], hit=x['hit'], tag=tag, R=x['R'], top=x['top'], dens=round(dens, 1), nr=x['rate'], nc=x['cpr'], **f)
    return X


def load_why(T):
    """前天首花这批红、绿的内容分析（tools/schedule_why.py 列清单，看完片写 notes/schedule-T.json），没有就不显示。"""
    p = os.path.join(ROOT, 'notes', f'schedule-{T.isoformat()}.json')
    if not os.path.exists(p):
        return None
    why = json.load(open(p, encoding='utf-8'))
    return why


def with_links(rev):
    """回收表的素材配上能打开的片子链接。"""
    links = json.load(open(os.path.join(ROOT, 'tools', 'links.json'), encoding='utf-8'))
    url = lambda i: (lambda x: x.get('link') or x.get('video') or x.get('jl') or '')(links.get(i, {}))
    for x in rev.get('bad', []):
        x['url'] = url(x['id'])
        if x.get('base'):
            x['base']['url'] = url(x['base']['id'])
    return rev


def uc_names(plan):
    ucs = json.load(open(os.path.join(ROOT, 'tools', 'ucs.json'), encoding='utf-8'))
    names = {u: v['short'] for u, v in ucs.items() if isinstance(v, dict) and v.get('short')}
    names.update(plan.get('UC_extra', {}))
    return names


def progress_html(prog, T):
    """页面顶部那一行小字。落下的行多时收起来，不把主表挤下去。"""
    if not prog or not prog.get('line'):
        return ''
    if prog.get('lag_n', 0) <= 6:
        return '<p class="prog">' + html.escape(prog['line']) + '</p>'
    return ('<details class="prog"><summary>' + html.escape(prog['head']) + f"落下 {prog['lag_n']} 行：</summary>" + html.escape('；'.join(prog['lags'])) + '。</details>')


def render(tpl, P, fields, rel, T):
    blob = json.dumps(P, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    rep = dict(fields)
    rep.update(REL=rel, DATE=T.isoformat(), LABEL=label(T), NAV_CSS=NAV_CSS, NAV=NAV_HTML.format(rel=rel, date=T.isoformat(), label=label(T)),
               NAV_JS=NAV_JS.format(rel=rel, date=T.isoformat()))
    out = tpl
    for k, v in rep.items():
        out = out.replace('{{' + k + '}}', str(v))
    out = out.replace('__P__', blob)
    left = re.findall(r'\{\{[A-Z0-9_]+\}\}', out.replace(blob, ''))
    assert not left, f'没填的占位符 {left}'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--date', required=True, help='看板当天 T')
    ap.add_argument('--progress')
    ap.add_argument('--root', default=ROOT, help='输出目录，测试时用')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    T = date(a.date)
    plan = json.load(open(os.path.join(ROOT, 'tools', 'schedule_plan.json'), encoding='utf-8'))
    S = json.load(open(os.path.join(a.data_dir, 'spend.json'), encoding='utf-8'))
    R = json.load(open(os.path.join(a.data_dir, 'roi.json'), encoding='utf-8'))
    D = date(S['D'])
    if T <= D:
        sys.exit(f'T {T} 要晚于数据日 {D}')
    if T != D + dt.timedelta(days=1):
        print(f'WARNING 数据日 {D} 不是 T 的前一天')
    day_dir = os.path.join(a.root, 'schedule', T.isoformat())
    page = os.path.join(day_dir, 'index.html')
    if os.path.exists(page) and 'name="schedule-source" content="manual"' in open(page, encoding='utf-8').read() and not a.force:
        sys.exit(f'{page} 是手工定稿的版本，不覆盖；确实要覆盖加 --force')

    U, total, parts = load_spend(S)
    RU = dict(R['U'])
    if R.get('merged', {}).get('PS03'):
        for _, k in SUB_KEYS:
            RU.pop(k, None)
        RU['PS03'] = R['merged']['PS03']
    GL = R['g']
    days = [D - dt.timedelta(days=13 - i) for i in range(14)]
    fut = [T + dt.timedelta(days=i) for i in range(5)]
    W = [md(d) for d in fut]
    E = view_entries(plan, U, days, D, T)
    B = batch_view(R, plan['GROUPS'])
    X = rule_rows(RU, U, E, GL, W, T)
    WT = total_warn(X, GL['t0'])
    in_week = plan.get('week') == (T - dt.timedelta(days=T.weekday())).isoformat()
    if not in_week:
        print(f"WARNING schedule_plan.json 的 week 是 {plan.get('week')}，这周的排期还没写进去：页面不显示产能条和结论，排期列是空的")
    listed = {u for g in plan['GROUPS'] for u in g[1]} | set(plan.get('FOLD', []))
    unlisted = sorted(u for u, x in U.items() if u not in listed and x['c7'] > 0)
    if unlisted:
        print('WARNING 有消耗但不在 GROUPS 里：' + '、'.join(unlisted))
    names = uc_names(plan)
    bars = plan.get('bars', 14)
    P = dict(E=E, U=U, T=total, UC=names, GROUPS=plan['GROUPS'], FOLD=plan.get('FOLD', []), MT=plan['MT'], MOVES=plan['MOVES'] if in_week else [],
             days=S['days'], X=X, GL=GL, NOTE=ps03_note(parts, plan.get('ps03_note', '')), START=14 - bars, futDays=W,
             futKey={md(d): d.strftime('%m-%d') for d in fut}, today=md(T), year=T.year, WE=[md(d) for d in days + fut if d.weekday() >= 5],
             DIR=plan.get('DIR', []), WT=WT, B=B, BT=batch_line(B, plan['GROUPS'], D, total, days), TIER=tier_view(R, plan['GROUPS'], total, plan, T), WHY=why_rows(load_why(T), load_batch_notes(), B, names, total, days), BD=batch_detail(R), BN=load_batch_notes(), REV=with_links(R.get('rev', dict(rows=[], bad=[], nbad=0, peak=[], npeak=0))), meters=plan.get('meters', []) if in_week else [])
    asof = date(plan['asof'])
    prog = json.load(open(a.progress, encoding='utf-8')) if a.progress else None
    if a.progress is None:
        print('WARNING 没给 --progress：页面顶部没有进度那一行')
    fields = dict(
        SUB=plan.get('sub', '') if in_week else '',
        PROG=progress_html(prog, T),
        D=md(D), RET=short_range(D - dt.timedelta(days=6), D - dt.timedelta(days=1)), T4=md(fut[-1]), TW=full_range(fut[0], fut[-1]),
        PREV=short_range(D - dt.timedelta(days=6), D - dt.timedelta(days=3)), LAST2=short_range(D - dt.timedelta(days=1), D),
        FIRST=short_range(max(D - dt.timedelta(days=7), STABLE), D - dt.timedelta(days=1)), GY=f"{GL['y']:,}",
        FOOT=plan.get('foot_note', ''), BACKTEST=plan.get('backtest', ''),
        MOVES_HEAD=plan.get('moves_head', '要改什么') if T == asof else f"{md(asof)} 提的改动，{plan.get('moves_head', '要改什么')}",
        MOVES_HIDE='' if P['MOVES'] else ' hidden')
    tpl = open(os.path.join(ROOT, 'tools', 'schedule_template.html'), encoding='utf-8').read()
    os.makedirs(day_dir, exist_ok=True)
    open(page, 'w', encoding='utf-8').write(render(tpl, P, fields, '../../', T))

    path = os.path.join(a.root, 'schedules.json')
    lst = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else []
    lst = [r for r in lst if r['date'] != T.isoformat()]
    lst.append(dict(date=T.isoformat(), label=label(T)))
    lst.sort(key=lambda r: r['date'], reverse=True)
    json.dump(lst, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    latest = lst[0]['date'] == T.isoformat()
    if latest:
        open(os.path.join(a.root, 'schedule', 'index.html'), 'w', encoding='utf-8').write(render(tpl, P, fields, '../', T))
    red = [u for u, x in X.items() if x['warn'] and any(u in g[1] for g in plan['GROUPS'][:2])]
    print(json.dumps(dict(date=T.isoformat(), D=D.isoformat(), latest=latest, in_week=in_week, all=WT, red={u: X[u]['warn'] for u in red},
                          schedules=[r['date'] for r in lst][:5]), ensure_ascii=False))


if __name__ == '__main__':
    main()
