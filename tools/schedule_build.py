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
    return dict(c7=R[0], rate=R[1], cpr=R[2], n=[int(x) for x in R[4].split(',')], s=dec(R[5]))


def load_spend(S):
    """表里 PS03 一行放合计，三部分只写进执行细节。"""
    U = {u: spend_row(R) for u, R in S['U'].items()}
    parts = {k: U.pop(k, None) for _, k in SUB_KEYS}
    if S.get('merged', {}).get('PS03'):
        U['PS03'] = spend_row(S['merged']['PS03'])
    total = dict(c7=S['t7'], rate=S['rate'], cpr=S['cpr'], n=[int(x) for x in S['T']['n'].split(',')], s=dec(S['T']['s']))
    return U, total, parts


def ps03_note(parts, suffix):
    bits = [f"{n} ¥{parts[k]['c7'] / 10000:.1f}万、{parts[k]['rate']}%、¥{parts[k]['cpr']}" for n, k in SUB_KEYS if parts.get(k)]
    if not bits:
        return {}
    return {'PS03': '；'.join(bits) + (('。' + suffix) if suffix else '')}


def view_entries(plan, U, days, D, T):
    """这一天页面上的排期条目。
    已上线的从数据算（当周、当天上传且花过钱）；已交没花钱的挪到今天，排期写定之后上线的条数扣掉；
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


def rule_rows(RU, U, E, GL, W):
    """每个 use case 的预警和条数建议。阈值是初值，Reina 11/4 定先跑 1–2 周。"""
    X = {}
    for u, x in RU.items():
        if u not in U:
            continue
        d = [sum(v) for v in U[u]['s']]
        prev = sum(d[7:11]) / 4
        lost = max(0, prev - x['lvl'])
        y = x['y'] if x['n'] >= 5 else GL['y']
        per = y / 3
        need = (x['R'] + lost) / per if per else 0
        sup0 = sum(e['n'] for e in E if e['uc'] == u and e['d'] in W and e['s'] in ('done', 'todo', 'cut'))
        sup1 = sum(e['n'] for e in E if e['uc'] == u and e['d'] in W and e['s'] in ('done', 'todo', 'add'))
        mult = x['y'] / GL['y']
        mx = x['yx'] / GL['y']
        dens = x['np'] / x['sh'] if x['sh'] else 0
        both = (x['rate'] or 0) < GL['rate'] and (x['cpr'] or 999) > GL['cpr']
        if x['n'] < 5:
            tag = '不判'
        elif both or (x['cpr'] or 999) > GL['cpr'] * 1.1:
            tag = '留存差'
        elif mult >= 1.3 and mx >= .8:
            tag = '加'
        elif mult >= .8 and (mx < .6 or x['top'] >= .6):
            tag = '靠一条'
        elif mult < .6 and dens >= 1:
            tag = '减'
        else:
            tag = '持平'
        cov = sup0 / need if need > .5 else 9
        lv = 'red' if cov < .5 else 'amber' if cov < 1 else ''
        X[u] = dict(mult=round(mult, 1), mx=round(mx, 1), n=x['n'], hit=x['hit'], tag=tag, need=round(need), sup0=sup0, sup1=sup1,
                    gap0=max(0, round(need - sup0)), gap1=max(0, round(need - sup1)), lv=lv, R=x['R'], lost=round(lost), chips=x['chips'],
                    top=x['top'], dens=round(dens, 1), nr=x['rate'], nc=x['cpr'])
    return X


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
    X = rule_rows(RU, U, E, GL, W)
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
             futKey={md(d): d.strftime('%m-%d') for d in fut}, today=md(T), WE=[md(d) for d in days + fut if d.weekday() >= 5],
             DIR=plan.get('DIR', []), meters=plan.get('meters', []) if in_week else [])
    asof = date(plan['asof'])
    prog = json.load(open(a.progress, encoding='utf-8')) if a.progress else None
    if a.progress is None:
        print('WARNING 没给 --progress：页面顶部没有进度那一行')
    fields = dict(
        SUB=plan.get('sub', '') if in_week else '',
        PROG=progress_html(prog, T),
        D=md(D), RET=short_range(D - dt.timedelta(days=6), D - dt.timedelta(days=1)), T4=md(fut[-1]), TW=full_range(fut[0], fut[-1]),
        PREV=short_range(D - dt.timedelta(days=6), D - dt.timedelta(days=3)), LAST2=short_range(D - dt.timedelta(days=1), D),
        FIRST=short_range(D - dt.timedelta(days=7), D - dt.timedelta(days=2)), GY=f"{GL['y']:,}",
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
    red = [u for u, x in X.items() if x['lv'] == 'red' and any(u in g[1] for g in plan['GROUPS'][:2])]
    amber = [u for u, x in X.items() if x['lv'] == 'amber' and any(u in g[1] for g in plan['GROUPS'][:2])]
    print(json.dumps(dict(date=T.isoformat(), D=D.isoformat(), latest=latest, in_week=in_week, red={u: X[u]['gap0'] for u in red}, amber={u: X[u]['gap0'] for u in amber},
                          schedules=[r['date'] for r in lst][:5]), ensure_ascii=False))


if __name__ == '__main__':
    main()
