"""把细分场景打标结果并进 notes/scene-map.json（Reina 11/9）。

用法：python3 tools/scene_merge.py --date T <打标结果.json> [...]
结果格式：{素材ID: {"uc": UC_ID, "s": 场景编号或 0, "by": "script|sibling|name", "why": "15 字以内依据"}}。
s 为 0 时：why 里有「看不出」「拿不准」「不一样」算待看片（tbd），否则算库里没有（none）。已有的标：旧的已对上且 use case 没变时，只有新结果是 script 打的才覆盖；use case 改过的、待看片、库里没有的都用新结果。
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('parts', nargs='+')
    a = ap.parse_args()
    p = os.path.join(ROOT, 'notes', 'scene-map.json')
    SM = json.load(open(p)) if os.path.exists(p) else {}
    add = upd = 0
    for f in a.parts:
        for i, x in json.load(open(f)).items():
            st = 'ok' if x.get('s') else ('tbd' if any(w in x.get('why', '') for w in ('看不出', '拿不准', '不一样')) else 'none')
            old = SM.get(i)
            # 旧标已对上、而且 use case 没变的不覆盖；use case 改过的、待看片、库里没有的都用新结果（11/19 Codex 补 393 条，名字、同原片打的也要能进）
            if old and old.get('st') == 'ok' and int(old.get('s') or 0) > 0 and old.get('uc') == x.get('uc') and x.get('by') != 'script':
                continue
            SM[i] = {'uc': x['uc'], 's': int(x.get('s') or 0), 'by': x.get('by', ''), 'why': x.get('why', ''), 'st': st, 'at': a.date}
            upd += bool(old)
            add += not old
    json.dump(SM, open(p, 'w'), ensure_ascii=False, indent=0)
    print(json.dumps({'added': add, 'updated': upd, 'total': len(SM)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
