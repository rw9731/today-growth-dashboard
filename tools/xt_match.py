#!/usr/bin/env python3
"""星图达人视频归属（Reina 11/27：「以后不要有这种问题」）。

代理在星图下单、达人本人抖音号发布、授权到巨量投的视频，投放表「来源」常写 AIGC（追踪类型 AI短剧型（唯西））或星广，
不进 tools/xingtu.json 就会被算成 AI 短剧或星广。这个脚本把代理执行表里的抖音作品 ID 和巨量素材 ID 按上传时间对上，写进 xingtu.json。

用法（仓库根目录）：
  python3 tools/xt_match.py --sheet <投放数据_分日 dump.json> --rows /tmp/xt/rows.json [--dry]

rows.json：代理执行表读出来的数组，每项 {"agency": "悦普" 或 "唯西", "name": 达人名, "aweme_id": 抖音作品ID}
（悦普 11月执行表 5cypAT 只取平台抖音、合作形式含「星图」的行；唯西付费达人执行表 L1c0HC 取合作形式「星图平台定制视频」、发布链接不为空的行；读法见 claude/flows/dashboard-daily.md 三之六）。

对法：作品 ID 和素材 ID 右移 32 位都是 unix 秒，星图视频的巨量素材 ID 比作品 ID 只差几秒到一分钟（11/27 对上的最大差 45 秒）。
只在投放表 11/01 以来出现过、来源是 AIGC 或星广、还不在 xingtu.json 的素材里找，取时间差最小且 ≤ 60 秒的那条；
同一条素材被两个作品争的，给时间差小的。已在 xingtu.json 的作品 ID 跳过。
输出 JSON：added（新加的）、unmatched（执行表里有、巨量里对不上的，写进最后回复）、suspect（还像星图但没对上的素材，见 compute.py 的 xt_suspect）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute  # noqa: E402

KIND = {'悦普': '悦普星图', '唯西': '唯西星图'}
MAX_GAP = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--rows', required=True)
    ap.add_argument('--since', default='2026-11-01')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    path = os.path.join(HERE, 'xingtu.json')
    xt = json.load(open(path))
    ids = xt.setdefault('ids', {})
    have_aw = {v[2] for v in ids.values() if len(v) > 2}

    mats = {}
    for r in compute.load_rows(a.sheet):
        if r['date'] < a.since or not r['id'].isdigit() or r['id'] in ids:
            continue
        if (r['src'] or '').strip() not in ('AIGC', '星广'):
            continue
        m = mats.setdefault(r['id'], {'cost': 0, 'name': r['name']})
        m['cost'] += r['cost']

    rows = json.load(open(a.rows))
    best = {}  # mid -> (gap, row)
    unmatched = []
    for row in rows:
        aw = str(row.get('aweme_id') or '').strip()
        ag = KIND.get(row.get('agency'))
        if not aw.isdigit() or not ag or aw in have_aw:
            continue
        t = int(aw) >> 32
        cand = sorted((abs((int(i) >> 32) - t), i) for i in mats if abs((int(i) >> 32) - t) <= MAX_GAP)
        if not cand:
            unmatched.append({'agency': row.get('agency'), 'name': row.get('name'), 'aweme_id': aw})
            continue
        gap, mid = cand[0]
        if mid not in best or gap < best[mid][0]:
            if mid in best:
                unmatched.append({'agency': best[mid][1].get('agency'), 'name': best[mid][1].get('name'), 'aweme_id': str(best[mid][1].get('aweme_id'))})
            best[mid] = (gap, row)
        else:
            unmatched.append({'agency': row.get('agency'), 'name': row.get('name'), 'aweme_id': aw})

    added = []
    for mid, (gap, row) in best.items():
        ids[mid] = [KIND[row['agency']], row.get('name', ''), str(row['aweme_id'])]
        added.append({'id': mid, 'kind': KIND[row['agency']], 'name': row.get('name'), 'gap': gap,
                      'cost': round(mats[mid]['cost']), 'title': mats[mid]['name'][:40]})
    if added and not a.dry:
        import datetime as dt
        xt['updated'] = dt.date.today().isoformat()
        open(path, 'w').write(json.dumps(xt, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'added': added, 'unmatched': unmatched, 'dry': a.dry}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
