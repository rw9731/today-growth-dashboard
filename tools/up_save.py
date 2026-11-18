"""Assemble the __upGet(k) chunks from up.js into notes/uploads-D.json (Reina 11/18).

Usage:
  python3 tools/up_save.py --date D /tmp/linkjs/up_0.json /tmp/linkjs/up_1.json ...

Each file is the raw return of __upGet(k): {"k": k, "d": "<800-char slice>"}. Joins them in k order,
checks the JSON, and writes notes/uploads-D.json as {date, source, read, n, items: {素材ID: 名字}}.
If the file already exists, items are merged (old ones kept).
"""
import argparse, datetime as dt, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    parts = []
    for f in a.files:
        raw = open(f).read().strip()
        j = json.loads(raw)
        if isinstance(j, str):
            j = json.loads(j)
        parts.append((int(j['k']), j['d']))
    parts.sort()
    ks = [k for k, _ in parts]
    if ks != list(range(len(ks))):
        raise SystemExit(f'ERROR 段号不连续：{ks}')
    res = json.loads(''.join(d for _, d in parts))
    if res.get('date') != a.date:
        raise SystemExit(f"ERROR 日期不对：{res.get('date')} != {a.date}")
    if len(res['items']) != res['n']:
        raise SystemExit(f"ERROR 条数对不上：items {len(res['items'])} != n {res['n']}")
    path = os.path.join(ROOT, 'notes', f'uploads-{a.date}.json')
    items = {}
    old = json.load(open(path)) if os.path.exists(path) else None
    if old:
        items.update(old.get('items', {}))
    for i, n in res['items'].items():
        items.setdefault(i, n[0] if isinstance(n, list) else n)
    sgt = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    out = {'date': a.date, 'source': res['source'], 'read': sgt, 'n': len(items), 'items': items}
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'saved': path, 'n': len(items), 'from_page': res['n'], 'kept_old': len(items) - res['n'], 'skipped_other_product': res.get('skipped', 0)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
