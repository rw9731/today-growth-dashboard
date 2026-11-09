"""Save the 素材 × 账户 summary from acct.js into notes/acct-D.json (Reina 11/9).

Usage:
  python3 tools/acct_save.py --date D --wait <__acctWait() 的返回值存成的文件> <__acctGet(k) 返回值存成的文件> [...]

每个 __acctGet 的返回值原样存成一个文件（JSON 字符串 {"acck": k, "d": "id,首次展示MM-DD,有展示账户,有消耗账户,3天≥100账户,3天≥300账户,单账户3天最高,D有展示账户,D有消耗账户;..."}）。
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    s = open(p).read().strip()
    x = json.loads(s)
    return json.loads(x) if isinstance(x, str) else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--wait')
    ap.add_argument('parts', nargs='+')
    a = ap.parse_args()
    year = a.date[:4]
    items = {}
    for p in a.parts:
        for row in (load(p).get('d') or '').split(';'):
            if not row:
                continue
            f = row.split(',')
            items[f[0]] = ['%s-%s' % (year, f[1])] + [int(v) for v in f[2:]]
    w = load(a.wait) if a.wait else {}
    out = {'date': a.date, 'source': '巨量升级版工作台 视频分析 EBP_management_mid_analysis（天 × 素材 × 账户）', 'fields':
           ['首次展示日', '有展示账户', '有消耗账户', '3天≥¥100账户', '3天≥¥300账户', '单账户3天最高', 'D有展示账户', 'D有消耗账户'],
           'n': len(items), 'total': w.get('total', {}), 'err': w.get('err', []), 'items': items}
    if w.get('mats') and w['mats'] != len(items):
        print(f"WARNING 页面里有 {w['mats']} 条，存下来 {len(items)} 条，没拿全")
    p = os.path.join(ROOT, 'notes', f'acct-{a.date}.json')
    json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'saved': p, 'n': len(items), 'err': out['err']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
