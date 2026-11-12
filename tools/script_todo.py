"""列出今天要读全片脚本的素材，并生成在巨量页面里拿视频的 jl.js。

Usage:
  python3 tools/script_todo.py --daily /tmp/results.json --out /tmp/sc     # 日报
  python3 tools/script_todo.py --week /tmp/week.json --out /tmp/sc         # 周报

范围（Reina 11/1：条数要够多，才撑得起结论）：
- 日报：「四、昨天消耗排行」里所有素材（昨天消耗 ≥ ¥1,000）、次留差的、扩量素材和它们的原素材；
- 周报：本周消耗 ≥ ¥2,000 的所有素材（好的差的都要，才能比）。
已经在 scripts/ 里的不再读。按消耗从高到低排，一次最多 --cap 条（默认日报 60、周报 80）。

写 /tmp/sc/todo.json（[{id, name, cost, video_permanent, why}]）和 /tmp/sc/jl.js（同 tools/jl_js.py 的 JS，只找这些素材）。
读完的每条写成 scripts/<素材ID>.json（格式见 tools/scripts_lib.py）。
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jl_js import JS, PAGE  # noqa: E402
import scripts_lib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--daily')
    ap.add_argument('--week')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cap', type=int)
    a = ap.parse_args()
    links = json.load(open(os.path.join(HERE, 'links.json')))
    have = scripts_lib.load()
    cand = {}

    def add(i, name, cost, why):
        if i in have:
            return
        c = cand.setdefault(i, {'id': i, 'name': name, 'cost': 0, 'why': []})
        c['cost'] = max(c['cost'], cost or 0)
        if why not in c['why']:
            c['why'].append(why)

    if a.daily:
        r = json.load(open(a.daily))
        rank = r['th'][0].get('rank', 1000)
        for m in r['mat']:
            if m['cost27'] >= rank:
                add(m['id'], m['name'], m['cost27'], '昨天消耗排行')
            if ('次留差' in m['group'] or '次留贵' in m['group'] or m['group'] in ('拖后腿', '次留好但贵')) and m['cost27'] >= 500:
                add(m['id'], m['name'], m['cost27'], m['group'])
        for k in r.get('kl', []):
            add(k['id'], k['name'], k['cost27'], '扩量')
            for s in k.get('src_ids', []):
                add(s, k['src_name'], k['cost27'], '扩量的原素材')
        cap = a.cap or 60
    elif a.week:
        w = json.load(open(a.week))
        for m in w.get('scope', []):
            add(m['id'], m['name'], m['spend'], '周消耗 ≥ ¥2,000')
        for m in w['top']:
            add(m['id'], m['name'], m['spend'], '头部素材')
        for m in w['bad']:
            add(m['id'], m['name'], m['spend'], '拖后腿')
        cap = a.cap or 80
    else:
        sys.exit('--daily 或 --week 二选一')

    todo = sorted(cand.values(), key=lambda c: -c['cost'])
    total = len(todo)
    todo = todo[:cap]
    for c in todo:
        lk = links.get(c['id'], {})
        v = lk.get('video') or (lk.get('link') if lk.get('type') == '预览' else '')
        c['video_permanent'] = v or ''
        c['cost'] = round(c['cost'])
        c['why'] = '、'.join(c['why'])
    os.makedirs(a.out, exist_ok=True)
    json.dump(todo, open(os.path.join(a.out, 'todo.json'), 'w'), ensure_ascii=False, indent=1)
    hubs = json.load(open(os.path.join(HERE, 'jl_hubs.json')))
    start = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 60 * 86400))
    ids = [c['id'] for c in todo]
    open(os.path.join(a.out, 'jl.js'), 'w').write(f'// 在这个页面跑（要已登录巨量）：{PAGE}\n' + JS % (json.dumps(ids), json.dumps(hubs), json.dumps(start)))
    print(json.dumps({'todo': len(todo), 'not_this_run': total - len(todo), 'have_scripts': len(have),
                      'no_permanent_video': sum(1 for c in todo if not c['video_permanent']), 'page': PAGE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
