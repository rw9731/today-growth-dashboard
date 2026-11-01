"""周报要看的视频：生成在巨量页面里拿视频的 jl.js，和一份要看什么的清单。

Usage:
  python3 tools/week_jl.py /tmp/week.json --out /tmp/wk

写两个文件：
- /tmp/wk/jl.js：和 tools/jl_js.py 同一段 JS，只找周报要看的素材（top 全部 + bad 全部）。
  在 https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 用 javascript_tool 跑，
  再 `await __jlWait()` 到 done。之后在同一个巨量页面里跑 tools/frames.js，直接用 __jl.res[素材ID].u 当视频链接，
  不用抄长链接（离开巨量页面 __jl 就没了）。
- /tmp/wk/watch.json：要看的素材和看到什么程度。full = 全片字幕都要读（读成脚本），structure = 看结构和开头。
  full：pick=true 的、top 里周消耗最高的 3 条、bad 里多花的钱最多的 2 条（最多 7 条）；其余 top 和 bad 前 3 条 structure。
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jl_js import JS, PAGE  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('week')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    w = json.load(open(a.week))
    top, bad = w['top'], w['bad']
    full = []
    for m in [m for m in top if m.get('pick')] + top[:3] + bad[:2]:
        if m['id'] not in full:
            full.append(m['id'])
    full = full[:7]
    watch = []
    for grp, ms in (('top', top), ('bad', bad[:3])):
        for m in ms:
            watch.append({'id': m['id'], 'group': grp, 'level': 'full' if m['id'] in full else 'structure',
                          'name': m['name'], 'kind': m['kind'], 'uc': m['uc'], 'short': m['short'],
                          'spend': round(m['spend']), 'pick': bool(m.get('pick')),
                          'video_permanent': m['video'] if m['video'] and 'oceanengine' not in m['video'] else '',
                          'link': m.get('link', ''), 'link_type': m.get('link_type', '')})
    ids = sorted({m['id'] for m in top + bad})
    hubs = json.load(open(os.path.join(HERE, 'jl_hubs.json')))
    start = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 60 * 86400))
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'jl.js'), 'w').write(f'// 在这个页面跑（要已登录巨量）：{PAGE}\n' + JS % (json.dumps(ids), json.dumps(hubs), json.dumps(start)))
    json.dump(watch, open(os.path.join(a.out, 'watch.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'need': len(ids), 'full': len(full), 'structure': len(watch) - len(full), 'page': PAGE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
