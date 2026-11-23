"""刷新上一周排期页面里的「本周排期素材回收」（Reina 11/23 定）。

排期每周一个页面（schedule/<周一>/）。新一周开始后，上周的页面其他部分不动，
只用最新的投放数据重算回收那一节（以及它用到的逐日消耗 HIST），周一到周三每天跑一次：
上周末上传的素材要到周二才走完 3 天冷启窗口，周日激活的人次留周一才回传。

用法（在仓库根目录，schedule_data.py 用最新数据日 D 跑完之后）：
  python3 tools/schedule_rev_refresh.py --data-dir /tmp/sched --week 2026-11-16

只改 schedule/<week>/index.html 里 P 的 REV 和 HIST，其余原样保留。
"""
import argparse, datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schedule_build as sb  # noqa: E402
from schedule_recovery import weekly_recovery  # noqa: E402

ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True, help='schedule_data.py 的输出目录（用最新数据日 D 跑的）')
    ap.add_argument('--week', required=True, help='要刷新的那一周的周一，YYYY-MM-DD')
    ap.add_argument('--root', default=ROOT)
    a = ap.parse_args()
    mon = dt.date.fromisoformat(a.week)
    if mon.weekday() != 0:
        sys.exit(f'{a.week} 不是周一')
    sun = mon + dt.timedelta(days=6)
    S = json.load(open(os.path.join(a.data_dir, 'spend.json'), encoding='utf-8'))
    R = json.load(open(os.path.join(a.data_dir, 'roi.json'), encoding='utf-8'))
    D = dt.date.fromisoformat(S['D'])
    if D <= sun - dt.timedelta(days=1):
        sys.exit(f'数据日 {D} 还没到这周末，用不着刷新')
    page = os.path.join(a.root, 'schedule', a.week, 'index.html')
    h = open(page, encoding='utf-8').read()
    key = 'const P='
    i = h.find(key)
    if i < 0:
        sys.exit(f'{page} 里找不到 const P=')
    i += len(key)
    P, n = json.JSONDecoder().raw_decode(h[i:])
    plan = P.get('WE_PLAN') or []
    if not plan:
        sys.exit(f'{page} 没有这周的排期条目（WE_PLAN），没法算回收')
    prod_path = os.path.join(ROOT, 'notes', 'output-items.json')
    production = json.load(open(prod_path, encoding='utf-8')) if os.path.exists(prod_path) else None
    old = P.get('REV') or {}
    rev = weekly_recovery(plan, production, R.get('review_facts'), sun, D)
    diag = R.get('rev', {})
    rev.update({k: diag.get(k, d) for k, d in (('bad', []), ('nbad', 0), ('peak', []), ('npeak', 0))})
    P['REV'] = sb.with_links(rev)
    P['HIST'] = sb.hist_view(R, D)
    blob = json.dumps(P, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    open(page, 'w', encoding='utf-8').write(h[:i] + blob + h[i + n:])
    print(json.dumps(dict(page=os.path.relpath(page, a.root), through_old=old.get('through'), through=rev.get('through'),
                          items_old=len(old.get('items') or []), items=len(rev.get('items') or [])), ensure_ascii=False))


if __name__ == '__main__':
    main()
