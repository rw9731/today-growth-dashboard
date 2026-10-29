"""Merge links found in the browser into tools/links.json.

Usage:
  python3 tools/links_merge.py /tmp/linkjs

Reads yuanpian.json (原片), chengpian.json (成片) and yulan.json (预览) from the folder,
whichever exist. 原片/成片 go to "link"/"type"; 预览 (the ad video itself) goes to "video".
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
    json.dump(links, open(path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'added': added, 'total': len(links)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
