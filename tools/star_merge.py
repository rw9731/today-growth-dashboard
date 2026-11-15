"""把 star_js.py 读回来的星广视频写进 tools/links.json（video）、notes/names.json、notes/star.json。用法见 tools/star_js.py。"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    d = json.load(open(sys.argv[1]))
    if isinstance(d, str):
        d = json.loads(d)
    items = d.get('items') or []
    lp, np_, sp = os.path.join(HERE, 'links.json'), os.path.join(ROOT, 'notes', 'names.json'), os.path.join(ROOT, 'notes', 'star.json')
    links, names, star = json.load(open(lp)), json.load(open(np_)), json.load(open(sp))
    nv = nn = ns = 0
    for mid, tid, link, nick, st, title in items:
        e = links.setdefault(mid, {})
        if link.startswith('https://www.douyin.com/video/') and e.get('video') != link and not (e.get('video') or '').startswith('https://www.douyin.com/'):
            e['video'] = link; nv += 1
        if title and not names.get(mid):
            names[mid] = title; nn += 1
        if mid not in star:
            star[mid] = [title, nick, tid]; ns += 1
    json.dump(links, open(lp, 'w'), ensure_ascii=False, indent=1)
    json.dump(names, open(np_, 'w'), ensure_ascii=False, indent=0)
    json.dump(star, open(sp, 'w'), ensure_ascii=False, indent=0)
    print(json.dumps({'items': len(items), 'video_added': nv, 'names_added': nn, 'star_added': ns, 'err': d.get('err')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
