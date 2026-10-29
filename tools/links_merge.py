"""Merge links found in the browser into tools/links.json.

Usage:
  python3 tools/links_merge.py /tmp/linkjs

Reads yuanpian.json (原片), chengpian.json (成片) and yulan.json (预览) from the folder,
whichever exist. 原片/成片 go to "link"/"type"; 预览 (the ad video itself) goes to "video".
Also reads jl.json (a list of {id, u, exp, ...} from tools/jl_js.py, straight from 巨量):
those go to "jl"/"jl_exp"; and jl_status.json (what __jlWait() returned) to keep
tools/jl_hubs.json pointed at the accounts that hold the most videos.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    folder = sys.argv[1]
    path = os.path.join(HERE, 'links.json')
    links = json.load(open(path))
    added = {}
    for name, kind in [('yuanpian', '原片'), ('chengpian', '成片'), ('yulan', '预览')]:
        f = os.path.join(folder, name + '.json')
        if not os.path.exists(f):
            continue
        found = json.load(open(f))
        if isinstance(found, str):
            found = json.loads(found)
        for i, url in found.items():
            if not str(url).startswith('http'):
                continue
            cur = links.setdefault(i, {})
            if kind == '预览':
                if cur.get('video') == url:
                    continue
                cur['video'] = url
            else:
                if cur.get('link') == url and cur.get('type') == kind:
                    continue
                cur['link'], cur['type'] = url, kind
            added[kind] = added.get(kind, 0) + 1
    f = os.path.join(folder, 'jl.json')
    if os.path.exists(f):
        found = json.load(open(f))
        if isinstance(found, str):
            found = json.loads(found)
        for e in found:
            if str(e.get('u', '')).startswith('http'):
                cur = links.setdefault(e['id'], {})
                cur['jl'], cur['jl_exp'] = e['u'], int(e.get('exp') or 0)
                added['巨量'] = added.get('巨量', 0) + 1
    f = os.path.join(folder, 'jl_status.json')
    if os.path.exists(f):
        st = json.load(open(f))
        if isinstance(st, str):
            st = json.loads(st)
        hits = st.get('hits') or {}
        hp = os.path.join(HERE, 'jl_hubs.json')
        old = json.load(open(hp))
        new = [a for a, _ in sorted(hits.items(), key=lambda kv: -kv[1])][:3]
        new += [a for a in old if a not in new]
        json.dump(new[:4], open(hp, 'w'))
    json.dump(links, open(path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'added': added, 'total': len(links)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
