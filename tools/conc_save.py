"""把 conc.js 的返回值存成 notes/conc-D.json（Reina 11/11，素材集中度）。

用法：python3 tools/conc_save.py --date D <conc.js 返回值存成的文件>
items：{素材ID: [D 总消耗, 单账户最高消耗, 有消耗的账户数]}，只存 D 花了 ¥100 以上的素材。
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('file')
    a = ap.parse_args()
    x = json.loads(open(a.file).read().strip())
    x = json.loads(x) if isinstance(x, str) else x
    if x.get('date') != a.date:
        raise SystemExit(f"日期对不上：文件是 {x.get('date')}，参数是 {a.date}")
    items = {}
    for row in (x.get('d') or '').split(';'):
        if row:
            f = row.split(',')
            items[f[0]] = [int(f[1]), int(f[2]), int(f[3])]
    warn = []
    if x.get('total') and x.get('got') is not None and x['got'] < x['total']:
        warn.append(f"只拿到 {x['got']}/{x['total']} 行")
    out = {'date': a.date, 'source': '巨量升级版工作台 视频分析 EBP_management_mid_analysis（D 当天 × 素材 × 账户）', 'fields': ['D 总消耗', '单账户最高消耗', '有消耗的账户数'],
           'n': len(items), 'warn': warn, 'items': items}
    p = os.path.join(ROOT, 'notes', f'conc-{a.date}.json')
    json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'saved': p, 'n': len(items), 'warn': warn}, ensure_ascii=False))


if __name__ == '__main__':
    main()
