"""给「投放数据_分日」里 UC 还是待对应、未标、空着的素材定 use case（Reina 11/15：日报里不能再出现「无 UC」）。

compute.load_rows 读表时调用 resolve_rows，所以日报、周报、排期、回补都会用同一套结果。
顺序：
0. 同一个素材ID 别的行已经有 UC 的直接用。
1. notes/uc_fix.json：人工定的（看过字幕或标题定的），{素材ID: {"uc": "PS03", "why": "一句依据", "checked": "日期"}}，优先级最高。
2. 同原片继承：名字去掉「推送视频_」、「_二创…」「_扩量…」「-扩量…」「-数字-」这类后缀以后，和已经有 UC 的素材同根，就用同根素材里最多的那个 UC（二创、扩量继承原片）。
3. 名字里的编号：新编号直接用；旧编号按 tools/uc_codes.json 换成新编号（这张表是从表里已标过的素材按「名字里的编号 → 实际 UC」统计出来的）。名字里只有 LG02 的不自动定（11/12 按内容拆成了 LG02、LG03、LG04）。
还定不了的留着，compute.py 输出的 unmapped 会列出来（素材ID、名字、消耗），日报那一轮要看字幕或标题定好写进 notes/uc_fix.json，再跑一次。
"""
import json, os, re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EMPTY = ('待对应', '未标', '', '无', '无 UC', '客供', '库外', 'A07')  # 库外、下线的旧编号 A07 也重定；客供（达人客供素材）也要定 UC，来源列照旧写客供
CODE = re.compile(r'(?<![A-Za-z])([A-Z]{1,2}\d{2})(?!\d)')


def _load(p, d):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return d


def root_name(n):
    n = (n or '').strip()
    n = re.sub(r'^推送视频_', '', n)
    n = re.sub(r'\s*[\(（]\d+[\)）]$', '', n)
    for pat in (r'[_-]+二创.*$', r'[_-]+扩量.*$', r'[_-]+新角度扩量.*$', r'[_-]+改素材扩量.*$', r'[_-]+换前贴.*$'):
        n = re.sub(pat, '', n)
    return n.strip('_- ')


def resolve_rows(rows, ucs):
    """就地改 rows 里待对应的 uc、l1、l2；返回 {素材ID: (uc, 来源)}。"""
    fix = _load(os.path.join(ROOT, 'notes', 'uc_fix.json'), {})
    codes = _load(os.path.join(HERE, 'uc_codes.json'), {})
    codes = {k: v for k, v in codes.items() if not k.startswith('_')}
    by_root = defaultdict(Counter)
    ok = lambda u: u in ucs and u not in EMPTY and bool(ucs[u].get('l1'))
    for r in rows:
        if ok(r['uc']) and r['name']:
            by_root[root_name(r['name'])][r['uc']] += 1
    same_id, nm = defaultdict(Counter), {}
    for r in rows:
        if ok(r['uc']):
            same_id[r['id']][r['uc']] += 1
        if r['name'] and len(r['name']) > len(nm.get(r['id'], '')):
            nm[r['id']] = r['name']
    done = {}
    for r in rows:
        if r['uc'] not in EMPTY and r['uc'] in ucs and ucs[r['uc']].get('l1'):
            continue
        if r['uc'] not in EMPTY and r['uc'] not in ucs and r['uc'] not in codes:
            continue  # 客供、库外这类保留原样（库外 compute 另有模糊归类）
        mid = r['id']
        if mid not in done:
            u, how = None, ''
            f = fix.get(mid)
            if f and f.get('uc') in ucs:
                u, how = f['uc'], '人工'
            if not u and same_id.get(mid):
                u, how = same_id[mid].most_common(1)[0][0], '同素材其他行'
            name = nm.get(mid, r['name'])
            if not u and name:
                c = by_root.get(root_name(name))
                if c:
                    u, how = c.most_common(1)[0][0], '同原片'
            if not u and name:
                for c in CODE.findall(name):
                    if c == 'LG02':
                        continue
                    if c in ucs and c[:2] in ('AI', 'WK', 'LG', 'HL', 'PS', 'FN', 'TR', 'IN', 'SH', 'NT'):
                        u, how = c, '名字编号'
                        break
                    if c in codes and codes[c] in ucs:
                        u, how = codes[c], '旧编号'
                        break
            if not u and r['uc'] in codes and codes[r['uc']] in ucs:
                u, how = codes[r['uc']], '旧编号'
            done[mid] = (u, how)
        u, how = done[mid]
        if u:
            r['uc'], r['l1'], r['l2'] = u, ucs[u].get('l1', ''), ucs[u].get('l2', '')
            r['uc_how'] = how
    return {k: v for k, v in done.items() if v[0]}
