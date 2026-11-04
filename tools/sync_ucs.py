"""从 Use case 库同步简称到 tools/ucs.json。

库里 Use case 列的写法是「简称：描述」（Reina 11/4 定），第一个冒号前就是简称，日报、周报、排期看板都用它。
用法：python3 tools/sync_ucs.py <'✅ Use case 库'!A1:G200 的 get_values 文件>
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(path):
    d = json.load(open(path, encoding='utf-8'))
    return d['values'] if isinstance(d, dict) else d


def main():
    v = rows(sys.argv[1])
    h = v[0]
    iu, ic, i1, i2 = h.index('UC_ID'), h.index('Use case'), h.index('一级分类'), h.index('二级分类')
    p = os.path.join(HERE, 'ucs.json')
    ucs = json.load(open(p, encoding='utf-8'))
    changed, odd = [], []
    for r in v[1:]:
        r = r + [''] * (len(h) - len(r))
        u, c = r[iu].strip(), r[ic].strip()
        if not u or not c:
            continue
        if '：' not in c:
            odd.append(u)
            continue
        short = c.split('：', 1)[0].strip()
        old = ucs.get(u, {}).get('short')
        if old != short:
            changed.append((u, old, short))
        ucs[u] = {**ucs.get(u, {}), 'short': short, 'l1': r[i1], 'l2': r[i2]}
    json.dump(ucs, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'changed': changed, 'no_colon': odd}, ensure_ascii=False))


if __name__ == '__main__':
    main()
