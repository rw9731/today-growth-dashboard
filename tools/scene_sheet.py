"""细分场景底表（Reina 11/19 定）：唯一的权威在 Google 表「国区投放素材」的「素材场景」tab，一条素材一行，人可以直接改。
notes/scene-map.json 是它的副本，看板、路线图、排期页照常读 json。

三个子命令：
  export --sheet 分日.json   → notes/scene-tags.csv（全量，表头同 tab），只在第一次建 tab 时用：
                               tab 里 A1 写 =IMPORTDATA(看板站点上的 csv)，再用 copyPaste PASTE_VALUES 原地转成值，不经过对话，省 token。
  pull <tab 读出来的 json>   → tab 里人改过的（use case、场景编号、状态和 json 不一样的）写回 scene-map.json，依据记「表里改」。
                               读 tab 用 Google Sheets 连接器 get_values('素材场景'!A1:I5000)，返回值大会自动存成文件。
  rows --since 日期 --sheet 分日.json → 打印 scene-map.json 里这天以后新打的标，格式是 append_values 要的二维数组，
                               每天日报打完标后追加到 tab（只追加新行，不重写全表）。
列：素材ID、素材名、use case、场景编号、场景、依据、说明、状态、打标日。
状态：已对上（编号 ≥ 1）、待看片（名字看不出、没字幕）、库里没有（库里没有对应场景）。
依据：素材名、字幕、同原片、表里改。
"""
import argparse, csv, glob, io, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SMP = os.path.join(ROOT, 'notes', 'scene-map.json')
HEAD = ['素材ID', '素材名', 'use case', '场景编号', '场景', '依据', '说明', '状态', '打标日']
BY = {'name': '素材名', 'script': '字幕', 'sibling': '同原片', 'same': '同原片', 'sheet': '表里改'}
BY_R = {'素材名': 'name', '字幕': 'script', '同原片': 'sibling', '表里改': 'sheet'}
ST = {'ok': '已对上', 'tbd': '待看片', 'none': '库里没有'}
ST_R = {v: k for k, v in ST.items()}


def names(sheet):
    nm = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'notes', 'uploads-*.json'))):
        nm.update(json.load(open(f)).get('items', {}))
    if sheet:
        v = json.load(open(sheet))['values']
        h = v[0]
        ii, ni = h.index('素材ID'), h.index('素材名')
        for r in v[1:]:
            if len(r) > ni and r[ni]:
                nm[r[ii]] = r[ni]
    return nm


def row(i, t, nm, SC):
    sc = {c['n']: c['t'] for c in SC.get(t['uc'], {}).get('scenes', [])}
    s = int(t.get('s') or 0)
    return [i, nm.get(i, ''), t['uc'], s if s > 0 else '', sc.get(s, '') if s > 0 else '', BY.get(t.get('by', ''), t.get('by', '')),
            t.get('why', ''), ST.get(t.get('st', ''), '已对上' if s > 0 else '待看片'), t.get('at', '')]


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    e = sp.add_parser('export')
    e.add_argument('--sheet')
    p = sp.add_parser('pull')
    p.add_argument('dump')
    p.add_argument('--date', required=True)
    r = sp.add_parser('rows')
    r.add_argument('--since', required=True)
    r.add_argument('--sheet')
    a = ap.parse_args()
    SM = json.load(open(SMP))
    SC = json.load(open(os.path.join(HERE, 'scenes.json')))
    if a.cmd == 'export':
        nm = names(a.sheet)
        out = os.path.join(ROOT, 'notes', 'scene-tags.csv')
        with open(out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(HEAD)
            for i, t in sorted(SM.items(), key=lambda kv: (kv[1].get('uc', ''), -(kv[1].get('s') or 0) * 0, kv[0])):
                w.writerow(row(i, t, nm, SC))
        print(json.dumps({'rows': len(SM), 'csv': out}, ensure_ascii=False))
    elif a.cmd == 'rows':
        nm = names(a.sheet)
        print(json.dumps([row(i, t, nm, SC) for i, t in SM.items() if t.get('at', '') >= a.since], ensure_ascii=False))
    else:
        d = json.load(open(a.dump))
        vals = d.get('values', d) if isinstance(d, dict) else d
        h = vals[0]
        ix = {k: h.index(k) for k in HEAD if k in h}
        n = 0
        for rr in vals[1:]:
            g = lambda k: (rr[ix[k]] if ix.get(k) is not None and len(rr) > ix[k] else '')
            i = str(g('素材ID')).strip()
            if not i:
                continue
            s = int(g('场景编号') or 0) if str(g('场景编号')).strip().lstrip('-').isdigit() else 0
            st = ST_R.get(g('状态'), 'ok' if s > 0 else 'tbd')
            uc = g('use case')
            old = SM.get(i)
            if old and old.get('uc') == uc and int(old.get('s') or 0) == s and old.get('st') == st:
                continue
            SM[i] = {'uc': uc, 's': s, 'by': 'sheet', 'why': g('说明') or '表里改', 'st': st, 'at': a.date}
            n += 1
        json.dump(SM, open(SMP, 'w'), ensure_ascii=False, indent=0)
        print(json.dumps({'changed_from_sheet': n, 'total': len(SM)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
