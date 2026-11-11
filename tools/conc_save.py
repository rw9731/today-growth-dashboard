"""把 conc.js（素材 × 账户）和 conc_proj.js（素材 × 项目）的返回值存成 notes/conc-D.json（Reina 11/11，素材集中度，按项目）。

用法：python3 tools/conc_save.py --date D /tmp/linkjs/conc.json /tmp/linkjs/concp_*.json
items：{素材ID: [D 总消耗, 单项目最高消耗, 有消耗的项目数]}，只存 D 花了 ¥100 以上的素材。
总消耗用第 1 步工作台的数（和日报其他地方一致）。第 2 步查不到项目的账户整户当一个项目算，记进 warn。
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    x = json.loads(open(p).read().strip())
    return json.loads(x) if isinstance(x, str) else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('ebp')
    ap.add_argument('proj', nargs='+')
    a = ap.parse_args()
    x = load(a.ebp)
    if x.get('date') != a.date:
        raise SystemExit(f"日期对不上：{a.ebp} 是 {x.get('date')}，参数是 {a.date}")
    acc = {}  # m -> {adv: cost}
    for row in (x.get('d') or '').split(';'):
        if row:
            m, adv, c = row.split(',')
            acc.setdefault(m, {})[adv] = float(c)
    proj, miss = {}, set()  # m -> {(adv, p): cost}
    for p in a.proj:
        y = load(p)
        if y.get('date') != a.date:
            raise SystemExit(f"日期对不上：{p} 是 {y.get('date')}，参数是 {a.date}")
        miss |= {s for s in (y.get('miss') or '').split(',') if s}
        for row in (y.get('d') or '').split(';'):
            if row:
                m, adv, pid, c = row.split(',')
                proj.setdefault(m, {})[(adv, pid)] = float(c)
    items, fb, gap = {}, 0, []
    for m, by_acc in acc.items():
        tot = sum(by_acc.values())
        parts = dict(proj.get(m, {}))
        found = {adv for adv, _ in parts}
        for adv, c in by_acc.items():
            if adv not in found:  # 查不到项目：整户当一个项目
                parts[(adv, 'acct')] = c
                fb += c
        if not parts:
            continue
        top = max(parts.values())
        items[m] = [round(tot), round(min(top, tot)), len(parts)]
        ps = sum(v for k, v in parts.items() if k[1] != 'acct') + sum(v for k, v in parts.items() if k[1] == 'acct')
        if tot >= 1000 and abs(ps - tot) / tot > 0.1:
            gap.append(f'{m} 项目合计 ¥{ps:,.0f} / 总 ¥{tot:,.0f}')
    allc = sum(sum(v.values()) for v in acc.values())
    warn = []
    if x.get('total') and x.get('got') is not None and x['got'] < x['total']:
        warn.append(f"第 1 步只拿到 {x['got']}/{x['total']} 行")
    if miss:
        warn.append(f'{len(miss)} 个账户查不到项目，整户当一个项目（占 ¥{fb:,.0f} / ¥{allc:,.0f}）')
    warn += gap[:10]
    out = {'date': a.date, 'source': '总消耗：巨量升级版工作台 EBP_management_mid_analysis；项目：巨量广告智擎版 std/projects/list + std/promotion/materials/list（D 当天）',
           'fields': ['D 总消耗', '单项目最高消耗', '有消耗的项目数'], 'n': len(items), 'warn': warn, 'items': items}
    p = os.path.join(ROOT, 'notes', f'conc-{a.date}.json')
    json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'saved': p, 'n': len(items), 'warn': warn}, ensure_ascii=False))


if __name__ == '__main__':
    main()
